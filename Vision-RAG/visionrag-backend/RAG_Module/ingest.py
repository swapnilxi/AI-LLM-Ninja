"""
ingest.py: Handles ingestion of HomeObjects-3k-Dataset images into Neon Postgres with pgvector
"""
import json
import os
import io
from typing import List, Dict
from . import db
from PIL import Image
from transformers import SiglipProcessor, SiglipModel
import google.generativeai as genai 
import torch
from fastapi import APIRouter, HTTPException, UploadFile, File

DATASET_PATH = "room_dataset/HomeObjects-3k-Dataset/HomeObjects-dataset/images/train"
GEMINI_VISION_MODEL = "gemini-1.5-flash"
GEMINI_EMBEDDING_MODEL = "text-embedding-004"
siglip_model = SiglipModel.from_pretrained("google/siglip-base-patch16-224")
siglip_processor = SiglipProcessor.from_pretrained("google/siglip-base-patch16-224")

def get_gemini_image_embedding(image_data: bytes) -> List[float]:
    """Generate embedding from Gemini by describing the image and embedding the text."""
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    img = Image.open(io.BytesIO(image_data))
    prompt = "Generate a detailed description of this image for use in a retrieval-augmented generation system."
    response = model.generate_content([prompt, img])
    description = response.text if response.text else "No description generated"
    
    embedding_response = genai.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        content=description,
        task_type="RETRIEVAL_DOCUMENT"
    )
    embedding = embedding_response['embedding']
    return embedding + [0.0] * (768 - len(embedding)) if len(embedding) < 768 else embedding[:768]

def get_siglip_image_embedding(image_data: bytes) -> List[float]:
    """Generate image embedding using SigLIP (image-only)."""
    import io
    import torch
    image = Image.open(io.BytesIO(image_data)).convert("RGB")
    inputs = siglip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = siglip_model.get_image_features(**inputs)
    emb = embedding.squeeze().cpu().numpy().tolist()
    return emb + [0.0] * (768 - len(emb)) if len(emb) < 768 else emb[:768]


##----segmentation and embedding functions using gemini and siglip----
def get_gemini_segmentation(image_data: bytes) -> List[Dict]:
    """Generate segmentation data (bbox, caption) using Gemini 1.5 Pro."""
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    img = Image.open(io.BytesIO(image_data))
    prompt = """
    Analyze this image and provide a list of objects with their approximate bounding boxes and captions. 
    For each object, return:
    - Caption: A brief description (e.g., "a dog").
    - Bounding box: [x1, y1, x2, y2] as percentages of image width/height (0-100).
    Format the output as a JSON array of objects, e.g., [{"caption": "a dog", "bbox": [10, 20, 30, 40]}, ...].
    """
    response = model.generate_content([prompt, img])
    try:
        segments = json.loads(response.text.strip('```json\n').strip('```'))
        return segments
    except Exception:
        return [{"caption": "No segments detected", "bbox": [0, 0, 0, 0]}]

def get_gemini_segment_embedding(caption: str) -> List[float]:
    """Generate embedding for a segment caption using text-embedding-004."""
    embedding_response = genai.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        content=caption,
        task_type="RETRIEVAL_DOCUMENT"
    )
    embedding = embedding_response['embedding']
    return embedding + [0.0] * (768 - len(embedding)) if len(embedding) < 768 else embedding[:768]

##---- image analyze -----
async def analyze_image_with_gemini(image_data: bytes) -> Dict:
    """Analyze image using Gemini 1.5 Pro for RAG-friendly descriptions."""
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    img = Image.open(io.BytesIO(image_data))
    prompt = "Generate a detailed description of this image for use in a retrieval-augmented generation system."
    response = model.generate_content([prompt, img])
    description = response.text if response.text else "No description generated"
    return {"description": description}

async def analyze_image_with_siglip(image_data: bytes) -> Dict:
    """Analyze image using SigLIP for zero-shot classification."""
    image = Image.open(io.BytesIO(image_data)).convert("RGB")
    labels = ["a dog", "a cat", "a car", "a tree", "a person"]
    inputs = siglip_processor(text=labels, images=image, return_tensors="pt", padding=True)
    
    with torch.no_grad():
        outputs = siglip_model(**inputs)
    
    logits = outputs.logits_per_image
    probs = torch.sigmoid(logits).detach().numpy()[0]
    return {label: float(prob) for label, prob in zip(labels, probs)} 




async def ingest_homeobjects_images():
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_rag_homeobjects (
                id SERIAL PRIMARY KEY,
                image_path TEXT UNIQUE,
                embedding VECTOR(512)
            )
        """)
        ingested = []
        skipped = []
        for fname in os.listdir(DATASET_PATH):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                img_path = os.path.join(DATASET_PATH, fname)
                exists = await conn.fetchval("SELECT 1 FROM vision_rag_homeobjects WHERE image_path=$1", img_path)
                if exists:
                    skipped.append(fname)
                    continue
                emb = analyze_image_with_gemini(img_path)
                await conn.execute(
                    "INSERT INTO vision_rag_homeobjects (image_path, embedding) VALUES ($1, $2)",
                    img_path, emb
                )
                ingested.append(fname)
        return {"ingested": ingested, "skipped": skipped}

# FastAPI router for ingestion endpoints
ingest_router = APIRouter(prefix="/ingest", tags=["ingest"])

@ingest_router.post("/homeobjects")
async def ingest_homeobjects_api():
    """
    Ingest all images from HomeObjects-3k-Dataset, skipping those already in vector DB.
    """
    try:
        result = await ingest_homeobjects_images()
        return {"status": "completed", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion error: {str(e)}")






async def ingest_image_siglip_local(data, image_id):
    from io import BytesIO
    image = Image.open(BytesIO(data)).convert("RGB")
    inputs = siglip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = siglip_model.get_image_features(**inputs)
    emb = embedding.squeeze().cpu().numpy().tolist()
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO vision_rag_images (image_id, uri, embedding, meta) VALUES ($1, $2, $3::vector, $4::jsonb)",
            image_id, None, db._format_vector(emb), db._as_json({"source": "siglip-local"})
        )
    return {"status": "ingested", "image_id": image_id}

async def ingest_image_gemini(data, image_id):
    emb = get_gemini_image_embedding(data)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO vision_rag_images (image_id, uri, embedding, meta) VALUES ($1, $2, $3::vector, $4::jsonb)",
            image_id, None, db._format_vector(emb), db._as_json({"source": "gemini"})
        )
    return {"status": "ingested using gemini", "image_id": image_id}

@ingest_router.post("/image-gemini")
async def ingest_image_gemini_api(file: UploadFile = File(...)):
    try:
        data = await file.read()
        return await ingest_image_gemini(data, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

@ingest_router.post("/image-local")
async def ingest_image_api(file: UploadFile = File(...)):
    """
    Ingest a single image using SigLIP and return analysis along with ingestion status.
    """
    try:
        data = await file.read()
        # Get SigLIP embedding and analyze the image
        emb = get_siglip_image_embedding(data)
        analysis = await analyze_image_with_siglip(data)
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO vision_rag_images (image_id, uri, embedding, meta) VALUES ($1, $2, $3::vector, $4::jsonb)",
                file.filename, None, db._format_vector(emb), db._as_json({"source": "siglip-local"})
            )
        return {
            "status": "ingested",
            "image_id": file.filename,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")