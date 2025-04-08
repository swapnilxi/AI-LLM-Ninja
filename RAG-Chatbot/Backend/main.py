from fastapi import FastAPI
import asyncpg
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch

app = FastAPI()

# Load the embedding model (thenlper/gte-large)
tokenizer = AutoTokenizer.from_pretrained("thenlper/gte-large")
model = AutoModel.from_pretrained("thenlper/gte-large")

# Neon Database Connection String (Replace with your actual values)
DATABASE_URL = "postgresql://your_user:your_password@your_host:your_port/your_dbname"

async def connect_db():
    return await asyncpg.connect(DATABASE_URL)

# Function to Generate Embeddings (THIS WAS MISSING)
def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=512)
    
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Mean pooling to get a single vector representation
    embedding = outputs.last_hidden_state.mean(dim=1)
    return embedding.squeeze().numpy().tolist()

# API Endpoint to Store Document Chunks & Embeddings
@app.post("/store/")
async def store_document(data: dict):
    content = data["content"]
    embedding = get_embedding(content)  # Generate embedding for the content
    
    conn = await connect_db()
    await conn.execute(
        "INSERT INTO document_chunks (content, embedding) VALUES ($1, $2)", 
        content, embedding
    )
    await conn.close()
    return {"message": "Document stored successfully"}

# API Endpoint for Searching Relevant Chunks
@app.post("/search/")
async def search_embeddings(query: dict):
    user_query = query["data"]
    
    # Generate embedding for the user query
    query_embedding = get_embedding(user_query)

    conn = await connect_db()
    
    # Perform similarity search in NeonDB
    rows = await conn.fetch(
        """
        SELECT content FROM document_chunks 
        ORDER BY embedding <-> $1
        LIMIT 5;
        """,
        query_embedding
    )

    await conn.close()
    
    # Return the most relevant document chunks
    return {"results": [{"text": row["content"]} for row in rows]}
