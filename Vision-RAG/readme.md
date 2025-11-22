# Vision-RAG

Multimodal Retrieval-Augmented Generation (RAG) system that lets you **ingest images, search with text or images, and interact with results using hand gestures**. The project is split into a FastAPI backend and a Next.js frontend.

> Branch: `hand-gesture` – includes experimental hand-gesture control for interacting with images and the application.

---

## High-level overview

### What you can do

- **Ingest images** (e.g., room / home objects datasets or your own uploads) into Postgres + pgvector
- **Query with text** ("show me living rooms with a sofa near the window")
- **Query with images** (find similar scenes or objects)
- **YOLO-based object & segment search** – retrieve images and specific regions
- **Gemini & SigLIP embeddings** – flexible multimodal retrieval
- **Hand gesture interaction** (experimental) – use webcam gestures to:
  - Navigate search results (next / previous image)
  - Approve / reject images (thumbs up / fist)
  - Toggle focus / selection of regions (peace / open hand)

### Architecture

- **Backend** (`visionrag-backend/`)

  - `main.py` – FastAPI app with health and metrics endpoints; mounts ingestion and unified query routes
  - `RAG_Module/ingest.py` – unified ingestion pipeline, YOLO segmentation, Gemini/SigLIP embeddings, Postgres/pgvector writes
  - `RAG_Module/retrieval.py` – unified `/query` endpoint combining:
    - text & image embeddings (Gemini/SigLIP)
    - YOLO segment search
    - DB retrieval from `vision_rag_images` and `vision_rag_image_segments`
  - `GestureDetection/HandGestures.py` – webcam-based hand-gesture recognizer using MediaPipe + OpenCV
  - `yolo_module/` – YOLOv8/YOLO11 segmentation utilities
  - `config/`, `DataLoader/`, `services/`, `Utils/` – DB, ingestion helpers, Gemini utilities, etc.

- **Frontend** (`visionrag-frontend/`)
  - Next.js 15 app (`app/page.tsx`) with a polished UI for ingest + query
  - `components/vision-rag/` – forms and result viewer
  - `lib/api/client.ts` – typed client for calling backend `/query` and ingestion endpoints

---

## Backend – setup & run

### 1. Requirements

- Python $\geq 3.12$
- Postgres with `pgvector` extension
- GPU recommended (for YOLO + Torch), but CPU also works

Core Python dependencies are defined in `visionrag-backend/pyproject.toml`, including:

- `fastapi`, `uvicorn`
- `asyncpg`, `python-dotenv`
- `torch`, `torchvision`, `ultralytics`
- `opencv-python`, `mediapipe`
- `google-generativeai` / `google-genai`, `transformers`

### 2. Environment & configuration

From `visionrag-backend/`, create a `.env` file with (example):

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/visionrag
GEMINI_API_KEY=your_gemini_key
YOLO_DEVICE=cuda       # or "cpu"
UPLOAD_DIR=uploads
HOMEOBJECTS_DATASET_PATH=room_dataset/HomeObjects-3k-Dataset/HomeObjects-dataset/images/train
```

Additional configuration (e.g. Gemini model) is in `config/gemini_config.yaml` and `config/config.py`.

### 3. Install & run

From the project root:

```bash
cd visionrag-backend
pip install -e .

# Or using uv / pipx / poetry as you prefer, guided by pyproject.toml

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will expose:

- `GET /` – health check
- `GET /metrics` – Prometheus metrics
- `POST /ingest/...` – ingestion endpoints (see `ingest.py`)
- `POST /query` – unified multimodal query endpoint

---

## Frontend – setup & run

### 1. Requirements

- Node.js (LTS) and npm / pnpm

### 2. Install & run

From the project root:

```bash
cd "visionrag-frontend "
npm install
npm run dev
```

Then open `http://localhost:3000` in your browser.

The frontend expects the backend at `http://localhost:8000`. If your backend is elsewhere, update the API base URL in `visionrag-frontend/lib/api/config.ts`.

---

## Using the system

### 1. Ingest images

There are two common ways to ingest images:

1. **Via API / UI uploads**

   - Go to the frontend home page and click **Start Chat**
   - Switch to the **Ingest** tab
   - Upload one or more images
   - Choose YOLO / Gemini / SigLIP pipeline as supported by the form

2. **Dataset ingestion (HomeObjects / SUNRGBD)**
   - Use scripts under `Room_Dataset/` and `RAG_Module/ingest.py` to ingest existing room datasets.
   - The ingestion pipeline will:
     - Embed full images (Gemini or SigLIP)
     - Optionally run YOLO for object/segment embeddings
     - Store everything in Postgres tables: `vision_rag_images`, `vision_rag_image_segments`.

### 2. Query

From the **Query** tab on the frontend, you can:

- Ask natural language questions about your image corpus
- Upload a query image to find visually similar content
- Choose an engine (e.g. `gemini`, `siglip`, `yolo`) as wired in `QueryForm`

Under the hood, the backend `/query` endpoint:

- Builds text or image embeddings
- Optionally runs YOLO-based region search
- Queries `vision_rag_images` and `vision_rag_image_segments` with pgvector KNN
- Merges and returns the most relevant results

Results display includes image thumbnails, captions, and metadata when available.

---

## Hand-gesture interaction (experimental)

The `hand-gesture` branch adds a **webcam-based hand gesture interface** implemented in `visionrag-backend/GestureDetection/HandGestures.py`.

### How it works

- Uses **MediaPipe Hands** + **OpenCV** to detect a single hand from your webcam
- Classifies simple gestures based on which fingers are raised:
  - `Fist` (0 fingers)
  - `One` (index)
  - `Peace` (index + middle)
  - `Three`, `Four`, `Five`
  - `Thumbs Up` (thumb raised, others down)
- The gesture classifier is encapsulated in:
  - `fingers_up(landmarks, handedness)`
  - `classify_gesture(landmarks, handedness)`

The script opens a window showing:

- Your webcam feed
- Hand landmarks and current gesture label overlayed on the image

### Mapping gestures to actions

You can wire gestures to **application actions** such as image navigation or selection. A typical mapping is:

- `Thumbs Up` → Approve / select current image or bounding box
- `Fist` → Reject / skip current image
- `One` → Move to **next** result
- `Peace` → Move to **previous** result
- `Five` → Toggle **gesture control mode** on/off

This mapping is not yet hard-coded into the FastAPI API, but can be integrated in two primary ways:

1. **Backend control loop (Python-side)**

   - Extend `HandGestures.py` to call backend or database APIs when a gesture is detected (e.g., via `requests` or WebSocket client).
   - Example (pseudo-flow):
     - On `Thumbs Up` → POST to `/api/gesture/approve` with current image ID
     - On `One` → POST to `/api/gesture/next` to advance selection

2. **Frontend integration (recommended for UI)**
   - Expose a small WebSocket or REST endpoint from backend that streams current gesture
   - The Next.js app subscribes to this stream and updates UI state:
     - `Thumbs Up` → highlight and pin image
     - `One` / `Peace` → navigate carousel

Because every project’s interaction model is slightly different, this repo focuses on **gesture detection and classification** as a building block, which you can compose with your own UX.

### Running the gesture demo

From `visionrag-backend/`:

```bash
python -m GestureDetection.HandGestures
```

Press `ESC` to close the window.

---

## Project structure

```text
Vision-RAG/
├── readme.md                 # This file
├── visionrag-backend/        # FastAPI backend and RAG pipelines
│   ├── main.py               # App entrypoint
│   ├── pyproject.toml        # Backend dependencies
│   ├── GestureDetection/     # Hand gesture recognition (MediaPipe + OpenCV)
│   ├── RAG_Module/           # Ingestion + retrieval + DB
│   ├── yolo_module/          # YOLO segmentation utilities
│   └── ...
└── visionrag-frontend /     # Next.js UI
        ├── app/page.tsx          # Main landing + chat/ingest/query UI
        ├── components/vision-rag/# Query / ingest / results components
        ├── lib/api/              # Typed client configuration
        └── ...
```

---

## Development tips

- Run backend and frontend in parallel during development:

```bash
# Terminal 1
cd visionrag-backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd "visionrag-frontend "
npm run dev
```

- For YOLO performance, ensure you have a proper Torch install with GPU support and set `YOLO_DEVICE=cuda`
- For Gemini calls, keep an eye on rate limits; retry behavior is configured in `ingest.py`

---

## Roadmap (suggested)

- [ ] Full wiring of gesture events to backend `/query` and selection state
- [ ] WebSocket-based gesture stream for the Next.js UI
- [ ] More advanced segment interaction (drawn bounding boxes, drag-select)
- [ ] Additional embedding backends (OpenCLIP variants, etc.)
- [ ] Pre-built dashboards for metrics and monitoring

---

## License

Check the root repository `LICENSE` (or add one if missing) for licensing terms.

---

## Acknowledgements

- Ultralytics YOLO
- MediaPipe Hands
- Google Gemini / Generative AI APIs
- FastAPI, Next.js, and the open-source ecosystem that makes this stack possible.
