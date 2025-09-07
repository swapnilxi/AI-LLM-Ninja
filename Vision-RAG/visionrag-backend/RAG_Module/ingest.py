"""
ingest.py: Handles ingestion of HomeObjects-3k-Dataset images into Neon Postgres with pgvector
"""
import os
import asyncpg
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import torch

# DB connection details (update with your Neon Postgres credentials)
DB_HOST = os.getenv("PG_HOST", "your-neon-host")
DB_PORT = int(os.getenv("PG_PORT", 5432))
DB_NAME = os.getenv("PG_DB", "your-db")
DB_USER = os.getenv("PG_USER", "your-user")
DB_PASS = os.getenv("PG_PASS", "your-password")

DATASET_PATH = "room_dataset/HomeObjects-3k-Dataset/HomeObjects-dataset/images/train"

clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

def get_image_embedding(image_path):
    image = Image.open(image_path).convert("RGB")
    inputs = clip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = clip_model.get_image_features(**inputs)
    return embedding.squeeze().cpu().numpy().tolist()

async def ingest_homeobjects_images():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS homeobjects (
            id SERIAL PRIMARY KEY,
            image_path TEXT UNIQUE,
            embedding VECTOR(512)
        )
    """)
    ingested = []
    skipped = []
    for fname in os.listdir(DATASET_PATH):
        if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            img_path = os.path.join(DATASET_PATH, fname)
            exists = await conn.fetchval("SELECT 1 FROM homeobjects WHERE image_path=$1", img_path)
            if exists:
                skipped.append(fname)
                continue
            emb = get_image_embedding(img_path)
            await conn.execute(
                "INSERT INTO homeobjects (image_path, embedding) VALUES ($1, $2)",
                img_path, emb
            )
            ingested.append(fname)
    await conn.close()
    return {"ingested": ingested, "skipped": skipped}
