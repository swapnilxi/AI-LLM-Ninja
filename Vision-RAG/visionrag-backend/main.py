from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv


load_dotenv()

from Utils.yaml_utils import (
    load_homeobjects_3k_config,
    YAMLConfigLoader,
    create_sample_homeobjects_config,
)

# DB + pipeline imports
from RAG_Module.db import init_pool, init_db, close_pool, check_db_connection
from RAG_Module.ingest import ingest_router
from RAG_Module.retrieval import router as retrieval_router

 # Removed imports for retrieve_with_siglip and retrieve_with_google_vision (not found in retrieval.py)
from prometheus_client import generate_latest


# Ingestion pipeline imports
from RAG_Module.ingest import ingest_homeobjects_images


# ---- Lifespan handler (replaces startup/shutdown) ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup
    await init_pool()
    await init_db()
    yield
    # On shutdown
    await close_pool()


app = FastAPI(
    title="Vision-RAG Backend",
    version="0.1.0",
    description="MultiModal RAG (SigLIP + pgvector) with YAML Configuration Support",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,  # attaching lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




# ---- Health ----
@app.get("/", tags=["health"])
async def health():
    db_status = "ok" if await check_db_connection() else "error"
    return {
        "status": "ok",
        "app": app.title,
        "db_connection": db_status,
    }


# Include the ingest router for modular ingestion endpoints
app.include_router(ingest_router)

# Mount the retrieval router for /query-siglp and /query-google endpoints
app.include_router(retrieval_router)



# ---- Metrics ----
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
