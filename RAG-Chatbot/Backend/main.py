from fastapi import FastAPI, UploadFile, File, HTTPException, Body
import os
from db import get_pool, init_db, insert_chunk, fetch_similar
from utils import (
    DOCUMENTS_DIR, 
    load_documents, 
    chunk_text, 
    embed_text, 
    get_rag_context,
    process_file_to_chunks_and_embeddings
)
from embedding_openai import (
    process_file_to_chunks_and_embeddings_openai, 
    insert_chunk_openai
)

app = FastAPI()
pool = None

@app.on_event("startup")
async def startup():
    global pool
    pool = await get_pool()
    await init_db(pool)

@app.get("/")
async def ragApp():
    print("welcome to rag chat bot application!")
    return {"message": "Welcome to RAG Chat Bot Application!"}

@app.post("/ingest/")
async def ingest_documents():
    files = [os.path.join(DOCUMENTS_DIR, fname) for fname in os.listdir(DOCUMENTS_DIR)
             if fname.lower().endswith((".txt", ".pdf"))]
    added = 0
    for path in files:
        for chunk, embedding in process_file_to_chunks_and_embeddings(path):
            await insert_chunk(pool, chunk, embedding)
            added += 1
    return {"status": "Documents ingested", "chunks_added": added}

@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".txt", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files supported")
    temp_path = os.path.join(DOCUMENTS_DIR, "_temp_upload" + ext)
    with open(temp_path, "wb") as out_file:
        content = await file.read()
        out_file.write(content)
    try:
        count = 0
        for chunk, embedding in process_file_to_chunks_and_embeddings(temp_path):
            await insert_chunk(pool, chunk, embedding)
            count += 1
    finally:
        os.remove(temp_path)
    return {"status": "File uploaded and ingested", "chunks_added": count}

@app.post("/openai-embedding/")
async def openai_embedding(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".txt", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files supported")
    temp_path = os.path.join(DOCUMENTS_DIR, "_temp_upload_openai" + ext)
    with open(temp_path, "wb") as out_file:
        content = await file.read()
        out_file.write(content)
    try:
        count = 0
        # This function should be defined in embedding_openai.py (see note below)
        for chunk, embedding in process_file_to_chunks_and_embeddings_openai(temp_path):
            await insert_chunk_openai(pool, chunk, embedding)
            count += 1
    finally:
        os.remove(temp_path)
    return {"status": "File uploaded and OpenAI embedded", "chunks_added": count}

@app.post("/query/")
async def query_api(query: str = Body(..., embed=True)):
    emb = embed_text(query)
    chunks = await fetch_similar(pool, emb, limit=5)
    context = "\n".join(chunks)
    return {"context": context}

@app.post("/chat-openai/")
async def chat_openai(query: str = Body(..., embed=True)):
    context = await get_rag_context(query, pool)
    answer = await get_openai_chat_response(context, query)
    return {"answer": answer}

@app.post("/chat-groq/")
async def chat_groq(query: str = Body(..., embed=True)):
    context = await get_rag_context(query, pool)
    answer = await get_groq_chat_response(context, query)
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
