# rag_gemini_unified.py
import os
import io
import base64
import asyncio
from typing import List, Dict, Optional, Tuple
import json
import time
import mimetypes

import httpx  # CHANGED: USE HTTPX FOR CONSISTENT, FASTER HTTP CLIENT

from .db import query_knn  # your existing async kNN helper

# ---------- CONFIG ----------
# CHANGED: USE GEMINI_API_KEY (STANDARD NAME) AND VALIDATE EARLY
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
EMBED_MODEL    = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
GEN_MODEL      = os.getenv("GEMINI_GEN_MODEL",   "gemini-1.5-flash")  # try "gemini-2.5-flash" if enabled

TIMEOUT_S      = 30
MAX_CTX_CHARS  = 2000           # CHANGED: CAP CONTEXT SIZE PER CHUNK
RETRIES        = 3              # CHANGED: SIMPLE BACKOFF RETRIES
BACKOFF_SEC    = 1.5            # CHANGED: BACKOFF MULTIPLIER

# ---------- HTTP CLIENT WITH RETRIES ----------
# CHANGED: SINGLETON-LIKE CLIENT + RETRY WRAPPER
_client: Optional[httpx.Client] = None

def _client_get() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=TIMEOUT_S)
    return _client

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")

def _retry_request(method: str, url: str, **kwargs) -> httpx.Response:
    # CHANGED: SIMPLE EXPONENTIAL BACKOFF
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = _client_get().request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
            if attempt == RETRIES:
                break
            time.sleep(BACKOFF_SEC ** attempt)
    raise last_err

def _http_post_json(url: str, payload: dict) -> dict:
    # CHANGED: UNIFIED JSON POST USING HTTPX + RETRIES
    resp = _retry_request("POST", url, json=payload, headers={"Content-Type": "application/json"})
    return resp.json()

# ---------- IMAGE HELPERS ----------
def _guess_mime_from_path(path: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(path)
    return mime

def _detect_mime_from_bytes(data: bytes, fallback: str = "image/jpeg") -> str:
    # CHANGED: LIGHTWEIGHT MIME DETECTION (HEADER SNIFF)
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

def _load_image_bytes(image: str) -> Tuple[Optional[bytes], Optional[str]]:
    # CHANGED: RETURN (BYTES, MIME)
    try:
        if image.startswith("http://") or image.startswith("https://"):
            r = _retry_request("GET", image)
            data = r.content
            mime = r.headers.get("Content-Type") or _detect_mime_from_bytes(data)
            return data, mime
        else:
            with open(image, "rb") as f:
                data = f.read()
            mime = _guess_mime_from_path(image) or _detect_mime_from_bytes(data)
            return data, mime
    except Exception:
        return None, None

# ---------- Gemini API wrappers ----------
def gemini_embed_text(text: str) -> List[float]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedText?key={GEMINI_API_KEY}"
    data = {"text": text}
    j = _http_post_json(url, data)  # --- LLM CALL HERE ---
    return j["embedding"]["values"]

def gemini_caption_image_json(image_bytes: bytes, mime: str) -> dict:
    """
    CHANGED: ASK FOR STRUCTURED JSON (objects, text, attributes).
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEN_MODEL}:generateContent?key={GEMINI_API_KEY}"
    prompt = (
        "You are a vision parser. Respond ONLY as strict JSON with keys: "
        '{"objects":[], "text":[], "attributes":[]}.\n'
        "Keep items short (1-3 words). No extra commentary."
    )
    contents = [{
        "role": "user",
        "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": mime, "data": _b64(image_bytes)}}
        ]
    }]
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 256,
            "responseMimeType": "application/json"  # CHANGED: REQUEST JSON DIRECTLY
        }
    }
    j = _http_post_json(url, payload)  # --- LLM CALL HERE ---
    # CHANGED: ROBUST JSON PARSE
    try:
        text = j["candidates"][0]["content"]["parts"][0]["text"]
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

def _build_query_from_detection(d: dict, question: str) -> str:
    # CHANGED: STRUCTURED → COMPACT QUERY STRING
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

def gemini_generate_grounded(question: str, contexts: List[Dict], image_bytes: Optional[bytes] = None, mime: Optional[str] = None) -> str:
    """
    Send (system rules + question + context + optional image) to Gemini for final answer.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")

    system_rules = (
        "Answer ONLY using the provided context. "
        "If insufficient, say: \"I don't know\". "
        "Cite sources inline like [#] where # indexes the context items."
    )

    # CHANGED: SAFELY COMPACT CONTEXT
    def clip(t: str) -> str:
        return (t or "")[:MAX_CTX_CHARS]

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
        contents.append({"role": "user", "parts": [{"inline_data": {"mime_type": mime, "data": _b64(image_bytes)}}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEN_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": contents, "generationConfig": {"temperature": 0.2}}
    j = _http_post_json(url, payload)  # --- LLM CALL HERE ---
    try:
        return j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return "I don't know"

# ---------- Async bridge ----------
# CHANGED: SAFE RUNNER THAT WORKS IN SYNC CONTEXTS (NOTE: NO NESTED RUN)
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # CHANGED: IF ALREADY IN EVENT LOOP, CREATE A NEW TASK AND WAIT
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        return asyncio.run(coro)

# ---------- Unified RAG entrypoint ----------
def rag_answer(
    question: str,
    image: Optional[str] = None,
    k: int = 5,
    enrich_with_caption: bool = True
) -> Dict:
    """
    One-call RAG that works for text-only (image=None) or image+text.

    Steps:
      (a) Optional: caption image -> enrich query text
      (b) Embed (question [+ caption]) with Gemini Embedding
      (c) k-NN retrieve top-k from your `text_chunks`
      (d) Generate grounded answer with Gemini (optionally vision-aware)
    """
    if not GEMINI_API_KEY:
        return {"error": "Missing GEMINI_API_KEY"}

    # (a) optional image caption (structured)
    img_bytes, img_mime = (None, None)
    query_text = question

    if image:
        img_bytes, img_mime = _load_image_bytes(image)
        if img_bytes and img_mime and enrich_with_caption:
            det = gemini_caption_image_json(img_bytes, img_mime)
            # CHANGED: USE STRUCTURED CUES FOR BETTER RETRIEVAL
            query_text = _build_query_from_detection(det, question)

    # (b) embed query
    try:
        qvec = gemini_embed_text(query_text)
    except Exception as e:
        return {"error": f"Gemini embedding failed: {e}"}

    # (c) retrieve
    try:
        results = _run_async(query_knn("text_chunks", qvec, k=k))  # CHANGED: SAFE ASYNC BRIDGE
    except Exception as e:
        return {"error": f"k-NN retrieval failed: {e}"}

    # CHANGED: NO-CONTEXT GUARD
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
        answer = gemini_generate_grounded(question, results, image_bytes=img_bytes, mime=img_mime)
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

# ---------- Example usage ----------
if __name__ == "__main__":
    # TEXT-ONLY
    resp1 = rag_answer("Summarize our warranty policy for routers.")
    print("TEXT-ONLY ANSWER:\n", resp1.get("answer"))

    # IMAGE + TEXT (optional)
    # resp2 = rag_answer(
    #     "What model is this device and how do I reset it according to our docs?",
    #     image="/path/to/device.jpg",  # or "https://example.com/device.jpg"
    #     k=5
    # )
    # print("\nVISION-AWARE ANSWER:\n", resp2.get("answer"))
