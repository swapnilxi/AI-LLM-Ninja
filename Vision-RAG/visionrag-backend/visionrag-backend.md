`# VisionRAG Backend

**VisionRAG** is a **Vision + Retrieval-Augmented Generation (RAG)** system to answer questions over room datasets. It leverages YOLO-seg for fine-grained segmentation, Gemini for captions and embeddings, and **PostgreSQL + pgvector (Neon)** as the unified datastore for efficient multimodal retrieval.

---

## 1. Project Structure & Data Flow

```
visionrag-backend/
├── Dataloader/                  # PyTorch loading and annotation logic (YOLO-style)
├── Room_Dataset/HomeObjects-Dataset #HomeObject-dataset images and labels                   
├── RAG_Module/                    # FastAPI service
|   ├── db.py                     # Database connection with neon postgres
│   ├── ingest.py                 # PDF and image ingestion + YOLO segmentation
│   ├── MS-Graph-Ingestion.py     # Ingesting Data stored in teams and Sharepoint
│   ├── retrieval.py              # common retrival logic for gemini and sigLip and to import in main.py
│   ├── retrieval_google.py       # pgvector k-NN logic and answer with gemini LLM
|   ├── retrieval_siglip.py       # pgvector k-NN logic with siglip
│   ├── rag.py                    # Gemini LLM integration
│   ├── embed.py                  # Gemini embedding APIs
│   └── main.py                   # FastAPI endpoints (ingest, query, query-google, query-sigLip, serve images)
├── room_dataset/                  # Local data storage
│   ├── train/                    # Training images
│   ├── val/                      # Validation images
│   ├── test/                     # Test images
│   └── annotation/               # YOLO-format label files
├── pyproject.toml                 # uv / project config
├── .env                           # API key & DB credentials
└── README.md                      # This file
```

---

## 2. Core Features

- **YOLO-seg based segmentation** — custom object detection + pixel masking.
- **Gemini Vision** for captioning segments and generating embeddings (`text-embedding-004`, 768-d). and for augmentation the answers 
**free-embeddin**-- sigLip
- **Neon (PostgreSQL + pgvector)** as a unified vector store for:
  - `text_chunks` (text embeddings)
  - `images` (page-level images + embeddings)
  - `image_segments` (YOLO crops + embeddings)
- **Pure backend retrieval** via IVFFlat ANN with similarity fusion (text + images + segments).
- **FastAPI interface** for ingestion, querying, and serving media directly from the database.

---

## 3. Supported Public Datasets

We focus on room‑centric datasets to bootstrap VisionRAG. These provide annotated data for both objects and room layouts:

| Dataset           | Format & Scale                                         | Annotation Type                                               | Ideal Use Case                       |
|------------------|--------------------------------------------------------|---------------------------------------------------------------|--------------------------------------|
| **HomeObjects‑3K** | ~3,000 real indoor images, YOLO format                 | 12 indoor classes (e.g., bed, sofa, lamp) | Object detection and segmentation (YOLO-ready)        |
SUNRGBD | 10335 | 
| **ZInD**           | ~67,000 360° panoramas from 1,500 homes, layouts      | 3D room layouts + windows/doors in floorplans | Global layout parsing & room structure understanding |
| **InteriorNet**    | ~20M synthetic interior images                        | Layout + furniture semantics | Pretraining or synthetic augmentation |
| **CubiCasa5K**     | 5K floorplan images                                   | Polygonal annotations | Layout parsing and floorplan tasks |

---

## 4. Example Recovery Flow (Text + Image)

1. **Ingest & Segment**
   - Run YOLO segmentation on PDFs or uploaded images.
   - Crop segments → caption via Gemini → embed → store in PostgreSQL.

2. **Query Workflow**
   - User asks: “Where is the lamp near the window?”
   - Embed question (768-d) → query `text_chunks`, `images`, `image_segments`.
   - Use **Reciprocal Rank Fusion (RRF)** to merge modalities.
   - Send top snippets/images back to Gemini for final answer with citations.

---

## 5. Environment & Setup

```ini
# .env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_VISION_MODEL=gemini-1.5-flash
GEMINI_EMBED_MODEL=text-embedding-004
DB_DSN=postgresql://user:password@host/db?sslmode=require
YOLO_WEIGHTS=/path/to/your_custom_yolo-seg.weights
```

- Run ingest: `POST /ingest/pdf` or `/ingest/segments`
- Run query: `POST /query` with `{"question":"...", "image_base64": ...}`

---
