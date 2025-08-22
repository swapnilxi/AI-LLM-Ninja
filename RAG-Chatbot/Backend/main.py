from fastapi import FastAPI, UploadFile, File, HTTPException, Body
import os
from db import get_pool, init_db, insert_chunks, fetch_similar,fetch_similar_simple
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

from groq_chat import get_groq_chat_response
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
    from utils import index_documents_once
    try:
        await index_documents_once(pool, DOCUMENTS_DIR)
        return {"status": "Documents ingested successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting documents: {str(e)}")


@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".txt", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files supported")
    
    # Save the file with its original name to ensure proper tracking
    safe_filename = file.filename.replace(" ", "_")
    file_path = os.path.join(DOCUMENTS_DIR, safe_filename)
    
    with open(file_path, "wb") as out_file:
        content = await file.read()
        out_file.write(content)
    
    try:
        # Use the index_documents_once function which handles the correct insert_chunks call
        from utils import index_documents_once
        await index_documents_once(pool, DOCUMENTS_DIR)
        return {"status": "File uploaded and ingested successfully", "filename": safe_filename}
    except Exception as e:
        # If there's an error, clean up the file and raise an exception
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

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

# only context without llm
@app.post("/query/")
async def query_api(query: str = Body(..., embed=True)):
    emb = embed_text(query)
    chunks = await fetch_similar_simple(pool, emb, limit=5)
    # Join the content strings directly as fetch_similar_simple returns a list of strings
    context = "\n".join(chunks)
    return {"context": context}

@app.post("/chat-openai/")
async def chat_openai(query: str = Body(..., embed=True)):
    from openai_chat import get_openai_chat_response
    context = await get_rag_context(query, pool)
    answer = await get_openai_chat_response(context, query)
    return {"answer": answer, "context": context}

@app.post("/chat-groq/")
async def chat_groq(query: str = Body(..., embed=True)):
    context = await get_rag_context(query, pool)
    answer = await get_groq_chat_response(context, query)
    return {"answer": answer, "context": context}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
