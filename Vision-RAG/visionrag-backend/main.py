from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
import uvicorn
from contextlib import asynccontextmanager

from yaml_utils import (
    load_homeobjects_3k_config,
    YAMLConfigLoader,
    create_sample_homeobjects_config,
)

# DB + pipeline imports
from RAG_Module.db import init_pool, init_db, close_pool
from RAG_Module.ingest import ingest_homeobjects_images
from RAG_Module.retrieval import router as retrieval_router
from RAG_Module.retrieval import retrieve_with_siglip
from RAG_Module.retrieval import retrieve_with_google_vision
from prometheus_client import generate_latest



# Import the new retrieval router


# Ingestion pipeline imports
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
    lifespan=lifespan,  # 👈 attach lifespan
)

# Mount the retrieval router for /query-siglp and /query-google endpoints
app.include_router(retrieval_router)


# ---- Health ----
@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "app": app.title}


# ---- YAML config endpoints ----
@app.get("/config/homeobjects-3k", tags=["configuration"])
def get_homeobjects_3k_config():
    try:
        config = load_homeobjects_3k_config()
        return {
            "status": "success",
            "message": "HomeObjects-3K configuration loaded successfully",
            "config": config,
        }
    except FileNotFoundError as e:
        sample_config = create_sample_homeobjects_config()
        return {
            "status": "warning",
            "message": "Original configuration not found, using sample configuration",
            "error": str(e),
            "config": sample_config,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")


@app.get("/config/dataset/{dataset_name}", tags=["configuration"])
def get_dataset_config(dataset_name: str):
    try:
        loader = YAMLConfigLoader()
        config = loader.load_ultralytics_dataset_config(dataset_name)
        return {
            "status": "success",
            "message": f"{dataset_name} configuration loaded successfully",
            "config": config,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")





# ---- NEW: Ingest & Query endpoints ----
@app.post("/ingest/image", tags=["ingest"])
async def ingest_image(file: UploadFile = File(...)):
    try:
        data = await file.read()
        await ingest_image_bytes(data, image_id=file.filename)
        return {"status": "ingested", "image_id": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


# ---- NEW: Ingest all HomeObjects images ----

@app.post("/ingest/homeobjects", tags=["ingest"])
async def ingest_homeobjects():
    """
    Ingest all images from HomeObjects-3k-Dataset, skipping those already in vector DB.
    """
    try:
        result = await ingest_homeobjects_images()
        return {"status": "completed", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion error: {str(e)}")


@app.post("/query", tags=["retrieval"])
async def query(payload: dict):
    q = payload.get("question") if isinstance(payload, dict) else None
    if not q:
        return JSONResponse({"error": "question required"}, status_code=400)
    try:
        result = retrieve_with_siglip(q)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


# ---- Metrics ----
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
