# rag_gemini.py
import os
import io
import base64
import asyncio
from typing import List, Dict, Optional, Tuple
import json
import time
import mimetypes

import httpx  

from .db import query_knn  
from .embed import align_vector
from google import genai  
from ..config.config import get_settings


class GeminiRetrieval:
    """
    Unified Gemini-based RAG retrieval client with embedding, captioning, and generation.
    Manages HTTP client, retries, configuration, and all Gemini API interactions.
    """

    def __init__(self, settings=None):
        """
        Initialize GeminiRetrieval with configuration.
        
        Args:
            settings: Optional GeminiSettings instance. Defaults to get_settings().gemini
        """
        if settings is None:
            _settings = get_settings() #setting from config
            settings = _settings.gemini
        
        self.settings = settings
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or settings.api_key
        self.embed_model = os.getenv("GEMINI_EMBED_MODEL", settings.embed_model)
        self.gen_model = os.getenv("GEMINI_VISION_MODEL", settings.vision_model)
        self.timeout_s = settings.timeout_seconds
        self.max_ctx_chars = settings.max_context_chars
        self.retries = settings.retries
        self.backoff_sec = settings.backoff_multiplier
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create singleton HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def _b64(self, data: bytes) -> str:
        """Encode bytes to base64 string."""
        return base64.b64encode(data).decode("utf-8")

    def _retry_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with exponential backoff retry logic."""
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self._get_client().request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_err = e
                if attempt == self.retries:
                    break
                time.sleep(self.backoff_sec ** attempt)
        raise last_err

    def _http_post_json(self, url: str, payload: dict) -> dict:
        """POST JSON payload and return parsed response."""
        resp = self._retry_request("POST", url, json=payload, headers={"Content-Type": "application/json"})
        return resp.json()

    def _guess_mime_from_path(self, path: str) -> Optional[str]:
        """Guess MIME type from file path."""
        mime, _ = mimetypes.guess_type(path)
        return mime

    def _detect_mime_from_bytes(self, data: bytes, fallback: str = "image/jpeg") -> str:
        """Detect MIME type from file header signature."""
        if len(data) >= 8:
            sig = data[:8]
            if sig.startswith(b"\x89PNG\r\n\x1a\n"):
                return "image/png"
            if sig[:3] == b"\xff\xd8\xff":
                return "image/jpeg"
            if sig[:4] == b"GIF8":
                return "image/gif"
            if sig[:4] == b"RIFF" and data[8:12] == b"WEBP":
                return "image/webp"
        return fallback

    def load_image_bytes(self, image: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Load image bytes from path, URL, or base64 data URL.
        Returns (bytes, mime_type) or (None, None) on error.
        """
        try:
            if image.startswith("data:"):
                # Handle base64 data URLs from frontend
                header, data = image.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                data_bytes = base64.b64decode(data)
                return data_bytes, mime
            elif image.startswith("http://") or image.startswith("https://"):
                r = self._retry_request("GET", image)
                data = r.content
                mime = r.headers.get("Content-Type") or self._detect_mime_from_bytes(data)
                return data, mime
            else:
                with open(image, "rb") as f:
                    data = f.read()
                mime = self._guess_mime_from_path(image) or self._detect_mime_from_bytes(data)
                return data, mime
        except Exception:
            return None, None

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for text using Gemini embedding model.
        Returns vector of ~768 dimensions for gemini-embedding-001.
        """
        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.embed_model}:embedContent?key={self.api_key}"
        payload = {
            "model": f"models/{self.embed_model}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
        }
        response = self._http_post_json(url, payload)
        emb = (
            response.get("embedding", {}).get("values")
            or response.get("embedding", {}).get("value")
            or response.get("embedding")
        )
        if not emb:
            raise RuntimeError(f"Bad embed response: {response}")
        return align_vector(emb)

    def caption_image_json(self, image_bytes: bytes, mime: str) -> dict:
        """
        Caption image with structured JSON output.
        Returns dict with keys: objects, text, attributes.
        """
        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gen_model}:generateContent?key={self.api_key}"
        prompt = (
            "You are a vision parser. Respond ONLY as strict JSON with keys: "
            '{"objects":[], "text":[], "attributes":[]}.\n'
            "Keep items short (1-3 words). No extra commentary."
        )
        contents = [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": self._b64(image_bytes)}}
            ]
        }]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 256,
                "responseMimeType": "application/json"
            }
        }
        response = self._http_post_json(url, payload)
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("Non-dict JSON")
            return {
                "objects": data.get("objects", []),
                "text": data.get("text", []),
                "attributes": data.get("attributes", [])
            }
        except Exception:
            return {"objects": [], "text": [], "attributes": []}

    def _build_query_from_detection(self, d: dict, question: str) -> str:
        """Build compact query string from detection data and question."""
        parts = []
        if d.get("objects"):
            parts.append("objects: " + ", ".join(d["objects"][:12]))
        if d.get("text"):
            parts.append("text: " + ", ".join(d["text"][:12]))
        if d.get("attributes"):
            parts.append("attrs: " + ", ".join(d["attributes"][:12]))
        parts.append("question: " + question)
        q = " | ".join(parts)
        return q[:1000]

    def generate_grounded(self, question: str, contexts: List[Dict], image_bytes: Optional[bytes] = None, mime: Optional[str] = None) -> str:
        """
        Generate grounded answer using question, context, and optional image.
        """
        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        system_rules = (
            "Answer ONLY using the provided context. "
            "If insufficient, say: \"I don't know\". "
            "Cite sources inline like [#] where # indexes the context items."
        )

        def clip(t: str) -> str:
            return (t or "")[:self.max_ctx_chars]

        ctx_parts = []
        for i, c in enumerate(contexts, start=1):
            src = c.get("source") or c.get("id") or "unknown"
            txt = clip(c.get("text", ""))
            ctx_parts.append(f"[{i}] {txt}\n(Source: {src})")
        context_block = "\n\n".join(ctx_parts)

        contents = [
            {"role": "user", "parts": [{"text": system_rules}]},
            {"role": "user", "parts": [{"text": f"Question: {question}"}]},
        ]
        if context_block.strip():
            contents.append({"role": "user", "parts": [{"text": f"Context:\n{context_block}"}]})
        if image_bytes and mime:
            contents.append({"role": "user", "parts": [{"inline_data": {"mime_type": mime, "data": self._b64(image_bytes)}}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gen_model}:generateContent?key={self.api_key}"
        payload = {"contents": contents, "generationConfig": {"temperature": 0.2}}
        response = self._http_post_json(url, payload)
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "I don't know"

    @staticmethod
    def _run_async(coro):
        """Safe async runner that works in both async and sync contexts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        else:
            return asyncio.run(coro)

    async def unified_query(
        self,
        question: str,
        image: Optional[str] = None,
        k: int = 5,
        include_segments: bool = True,
        include_text_chunks: bool = True,
        include_images: bool = True,
        enrich_with_caption: bool = True
    ) -> Dict:
        """
        UNIFIED query endpoint that retrieves from multiple sources and generates a grounded answer.
        
        Args:
            question: Natural language query
            image: Optional image (path, URL, or base64 data URL)
            k: Number of results per table
            include_segments: Search YOLO image segments
            include_text_chunks: Search text chunks
            include_images: Search full images
            enrich_with_caption: Use vision model to enhance image queries
        
        Returns:
            {
                "question": str,
                "answer": str (grounded LLM response),
                "method": str,
                "caption": dict (if image was captioned),
                "text_results": List[Dict],
                "image_results": List[Dict],
                "segment_results": List[Dict],
                "all_contexts": List[Dict],
                "stats": dict
            }
        """
        if not self.api_key:
            return {"error": "Missing GEMINI_API_KEY"}

        # (1) Process input image if provided
        img_bytes, img_mime = (None, None)
        query_text = question
        caption_data = None

        if image:
            img_bytes, img_mime = self.load_image_bytes(image)
            if img_bytes and img_mime and enrich_with_caption:
                caption_data = self.caption_image_json(img_bytes, img_mime)
                query_text = self._build_query_from_detection(caption_data, question)

        # (2) Generate query embedding
        try:
            qvec = self.embed_text(query_text)
        except Exception as e:
            return {"error": f"Gemini embedding failed: {e}"}

        # (3) Retrieve from multiple sources
        text_results = []
        image_results = []
        segment_results = []

        try:
            if include_text_chunks:
                text_results = await query_knn("vision_rag_text_chunks", qvec, k=k, extra_cols=["doc_id", "meta"])
            
            if include_images:
                image_results = await query_knn("vision_rag_images", qvec, k=k, extra_cols=["image_id", "uri", "meta"])
            
            if include_segments:
                segment_results = await query_knn("vision_rag_image_segments", qvec, k=k, extra_cols=["image_id", "bbox", "meta"])
                
        except Exception as e:
            return {"error": f"Database retrieval failed: {e}"}

        # (4) Build unified context for LLM
        all_contexts = []
        
        # Add text chunks to context
        for r in text_results:
            all_contexts.append({
                "id": f"text_{r.get('id')}",
                "text": (r.get("content") or "")[:self.max_ctx_chars],
                "source": f"text_chunk_{r.get('doc_id') or r.get('id')}",
                "type": "text_chunk",
                "score": float(r.get("score", 0))
            })
        
        # Add image captions to context
        for r in image_results:
            meta = r.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            caption = meta.get("caption", "")
            if caption:
                all_contexts.append({
                    "id": f"image_{r.get('id')}",
                    "text": caption[:self.max_ctx_chars],
                    "source": r.get("uri") or f"image_{r.get('image_id')}",
                    "type": "image",
                    "score": float(r.get("score", 0)),
                    "image_id": r.get("image_id"),
                    "uri": r.get("uri")
                })
        
        # Add segment captions to context
        for r in segment_results:
            caption = r.get("content") or ""
            meta = r.get("meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            
            if caption:
                all_contexts.append({
                    "id": f"segment_{r.get('id')}",
                    "text": caption[:self.max_ctx_chars],
                    "source": meta.get("crop_path") or f"segment_{r.get('id')}",
                    "type": "segment",
                    "score": float(r.get("score", 0)),
                    "image_id": r.get("image_id"),
                    "bbox": r.get("bbox"),
                    "cls": meta.get("cls") or meta.get("obj_class"),
                    "conf": meta.get("conf") or meta.get("obj_conf")
                })

        # Sort contexts by score (highest first)
        all_contexts.sort(key=lambda x: -x["score"])
        
        # (5) Generate grounded answer
        if not all_contexts:
            answer = "I don't know - no relevant information found in the database."
        else:
            try:
                answer = self.generate_grounded(question, all_contexts, image_bytes=img_bytes, mime=img_mime)
            except Exception as e:
                return {"error": f"Gemini generation failed: {e}"}

        return {
            "method": "unified_gemini_rag",
            "question": question,
            "answer": answer,
            "caption": caption_data,
            "caption_used": bool(image and enrich_with_caption and caption_data),
            "text_results": text_results,
            "image_results": image_results,
            "segment_results": segment_results,
            "all_contexts": all_contexts,
            "stats": {
                "text_count": len(text_results),
                "image_count": len(image_results),
                "segment_count": len(segment_results),
                "context_count": len(all_contexts)
            }
        }

    def rag_answer(
        self,
        question: str,
        image: Optional[str] = None,
        k: int = 5,
        enrich_with_caption: bool = True
    ) -> Dict:
        """
        LEGACY: One-call RAG that works for text-only (image=None) or image+text.
        Use unified_query() instead for full multi-source retrieval.
        """
        if not self.api_key:
            return {"error": "Missing GEMINI_API_KEY"}

        # (a) optional image caption (structured)
        img_bytes, img_mime = (None, None)
        query_text = question
        det = None

        if image:
            img_bytes, img_mime = self.load_image_bytes(image)
            if img_bytes and img_mime and enrich_with_caption:
                det = self.caption_image_json(img_bytes, img_mime)
                query_text = self._build_query_from_detection(det, question)

        # (b) embed query
        try:
            qvec = self.embed_text(query_text)
        except Exception as e:
            return {"error": f"Gemini embedding failed: {e}"}

        # (c) retrieve
        try:
            results = self._run_async(query_knn("vision_rag_text_chunks", qvec, k=k))
        except Exception as e:
            return {"error": f"k-NN retrieval failed: {e}"}

        if not results:
            return {
                "method": "gemini_rag_unified",
                "question": question,
                "image": image,
                "k": k,
                "caption_used": bool(image and enrich_with_caption),
                "caption": det if image and enrich_with_caption and img_bytes else None,
                "results": [],
                "answer": "I don't know"
            }

        # (d) generate grounded answer
        try:
            answer = self.generate_grounded(question, results, image_bytes=img_bytes, mime=img_mime)
        except Exception as e:
            return {"error": f"Gemini generation failed: {e}"}

        return {
            "method": "gemini_rag_unified",
            "question": question,
            "image": image,
            "k": k,
            "caption_used": bool(image and enrich_with_caption),
            "caption": det if image and enrich_with_caption and img_bytes else None,
            "results": results,
            "answer": answer
        }

    def close(self):
        """Close HTTP client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# BACKWARD COMPATIBILITY LAYER
# ============================================================================
# This allows old code to continue working WITHOUT any changes.
# 
# HOW IT WORKS:
# 1. We keep a global default instance of GeminiRetrieval
# 2. Old function names are thin wrappers that delegate to this instance
# 3. When you call gemini_embed_text("text"), it actually calls:
#    _get_default_retrieval().embed_text("text")
#
# EXAMPLE OF OLD CODE (Still Works):
#    from RAG_Module.retrieval_gemini import gemini_embed_text
#    vec = gemini_embed_text("hello")  # Works exactly as before!
#
# EXAMPLE OF NEW CODE (Recommended):
#    from RAG_Module.retrieval_gemini import GeminiRetrieval
#    retrieval = GeminiRetrieval()
#    vec = retrieval.embed_text("hello")
# ============================================================================

_default_retrieval: Optional[GeminiRetrieval] = None

def _get_default_retrieval() -> GeminiRetrieval:
    """
    Get or create the default GeminiRetrieval singleton instance.
    This ensures all legacy function calls use the same instance.
    """
    global _default_retrieval
    if _default_retrieval is None:
        _default_retrieval = GeminiRetrieval()
    return _default_retrieval


# OLD FUNCTION → NEW CLASS METHOD mapping
def gemini_embed_text(text: str) -> list[float]:
    """
    LEGACY FUNCTION (for backward compatibility).
    
    Old usage:
        from RAG_Module.retrieval_gemini import gemini_embed_text
        vec = gemini_embed_text("text")
    
    New recommended usage:
        from RAG_Module.retrieval_gemini import GeminiRetrieval
        retrieval = GeminiRetrieval()
        vec = retrieval.embed_text("text")
    """
    return _get_default_retrieval().embed_text(text)


def gemini_caption_image_json(image_bytes: bytes, mime: str) -> dict:
    """
    LEGACY FUNCTION (for backward compatibility).
    Delegates to GeminiRetrieval.caption_image_json()
    """
    return _get_default_retrieval().caption_image_json(image_bytes, mime)


def gemini_generate_grounded(question: str, contexts: List[Dict], image_bytes: Optional[bytes] = None, mime: Optional[str] = None) -> str:
    """
    LEGACY FUNCTION (for backward compatibility).
    Delegates to GeminiRetrieval.generate_grounded()
    """
    return _get_default_retrieval().generate_grounded(question, contexts, image_bytes, mime)


async def unified_query(
    question: str,
    image: Optional[str] = None,
    k: int = 5,
    include_segments: bool = True,
    include_text_chunks: bool = True,
    include_images: bool = True,
    enrich_with_caption: bool = True
) -> Dict:
    """
    LEGACY FUNCTION (for backward compatibility).
    Delegates to GeminiRetrieval.unified_query()
    """
    return await _get_default_retrieval().unified_query(
        question, image, k, include_segments, include_text_chunks, include_images, enrich_with_caption
    )


def rag_answer(
    question: str,
    image: Optional[str] = None,
    k: int = 5,
    enrich_with_caption: bool = True
) -> Dict:
    """
    LEGACY FUNCTION (for backward compatibility).
    Delegates to GeminiRetrieval.rag_answer()
    """
    return _get_default_retrieval().rag_answer(question, image, k, enrich_with_caption)

