# RAG Chatbot — generic, configurable reference module

Put documents in a profile folder under `rag-data/`, sync, chat. Every profile is isolated. Every moving part is swappable from the UI **or** the backend `.env`.

| Layer | Options |
|---|---|
| LLM | Ollama (local, free) · Google Gemini · DeepSeek · OpenRouter · Groq · OpenAI |
| Embeddings | sentence-transformers (local) · Ollama · Gemini (online) · OpenAI (online) · `hash` (offline demo) |
| Vector DB | Chroma (local, embedded) · Postgres + pgvector (local Docker **or** Neon) |

```
rag-data/       one folder per profile: rag-data/company1/, rag-data/common/ ...  (.txt .md .pdf .csv .json .html .docx)
rag-be/     FastAPI backend  (app/llm, app/embeddings, app/vectorstores, app/ingestion, app/rag.py)
rag-ui/     Next.js UI       (Chat · Documents · Settings)
```

## Quick start (fully local)

```bash
# backend
cd rag-be
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt    # everything (incl. local embeddings); or: pip install -e ".[local]"
cp .env.example .env               # optional: everything is also editable in the UI
uvicorn app.main:app --port 8000

# ui (new terminal)
cd rag-ui && npm install && npm run dev      # http://localhost:3000

# local LLM (optional)
ollama pull llama3.2
```

Open http://localhost:3000 → **Settings** (choose a preset, paste keys, *Test connection*, Save) → **Profiles** (create one, or just make a folder in `rag-data/`) → **Documents** (upload into the profile, *Sync now*) → **Chat**.

## The UI

Left sidebar (collapsible; a slide-in drawer on phones) with light / dark / system themes and live backend + database status.

- **Overview** — health dashboard: getting-started checklist, index stats, active LLM / embedding / vector-DB with one-click "Test", last sync, documents by type.
- **Profiles** — create / edit / delete profiles, per-profile instructions, the *include common* switch, document + indexing counts, re-index. A profile switcher sits in the top bar of every screen.
- **Chat** — always scoped to the active profile (shown in the top bar and the input placeholder); conversations are saved per profile. Conversations saved in your browser, streaming answers with clickable `[1]` citations that jump to the source card (PDF sources open at the cited page), copy / regenerate / export as Markdown, a per-chat model picker (any provider, no restart), and **Search only** mode (retrieval without an LLM call).
- **Documents** — per profile, with a folder tree, new folder, per-document status (`DISCOVERED PENDING INDEXING INDEXED STALE FAILED`), re-index, drag-and-drop upload with instant client-side validation, search, status / type filters, sorting, a details drawer (PDF pages, scanned-PDF warning, Word author...), open / download / delete, live sync progress.
- **Settings** — tabs for LLM, Embeddings, Vector DB, RAG and Access; presets; "Fetch list" of real model names; per-section "Test connection"; unsaved-change tracking; "Copy as .env".

## Presets

| Preset | LLM | Embeddings | Vector DB | Needs |
|---|---|---|---|---|
| Local | Ollama | sentence-transformers | Chroma | nothing online |
| Advanced | Gemini | Gemini | local Postgres (`docker compose up -d`) | Gemini key |
| Production | OpenRouter / Gemini | Gemini | Neon | keys + Neon URL, `ALLOW_UI_CONFIG=false`, `ADMIN_TOKEN` |

Neon: create a project, copy the connection string (keep `?sslmode=require`) into `DATABASE_URL` or the Settings page. pgvector is available on Neon by default.

## Configuration model

Precedence: built-in defaults < `.env` < UI overrides (`rag-be/data/settings.json`, chmod 600, git-ignored). `Reset to .env` in the UI removes overrides. Secrets are masked in API responses. See `rag-be/.env.example` for every variable.

Production hardening (environment only, not changeable from the UI): `ALLOW_UI_CONFIG=false`, `ALLOW_UI_UPLOAD=false`, `ADMIN_TOKEN=…` (all `/api` calls require `Authorization: Bearer …`), `CORS_ORIGINS`, `MAX_UPLOAD_MB`.

## RAG Architecture

```
Frontend (active profile_id)
   → POST /api/chat {profile_id, message}
   → Profile resolver (SQLite: does the profile exist and is it active?)     app/rag.py  resolve_context
   → RAGContext(profile_id, include_common, instructions)                     explicit, never a global
   → Retriever: embed query → vector search WHERE profile_id IN (allowed)     app/rag.py  retrieve
   → (score threshold)
   → Context builder: system + common instr. + profile instr. | <documents>   app/rag.py  build_messages
   → LLM (streamed)
   → Citations: source, page, profile_id, scope = profile | common
```

Reused unchanged from the original design: loaders and file-type registry, the recursive chunker, the embedder providers, the Chroma / pgvector stores (extended, not replaced), the LLM providers and the SSE protocol. Hybrid (BM25) search and reranking were not part of the original pipeline and are not included; the retrieval step is the single place they would be added.

## Profile Architecture

**Every folder directly inside `rag-data/` is one profile.** `rag-data/company1/` is profile `company1`; its display name, description, instructions and settings live in SQLite.

### Folder Structure

```
rag-data/
├── common/            shared knowledge (special profile, always exists)
│   ├── handbook.pdf
│   └── faq.md
├── company1/
│   ├── contracts/
│   ├── policies/
│   └── reports/
├── company2/
│   ├── contracts/
│   └── reports/
├── personal/
│   └── notes/
└── acme/
    ├── technical/
    └── business/
```

Folder names must be lowercase letters, digits, `-` or `_` (a folder like `My Docs` is listed under "skipped", not registered). Creating a profile in the UI slugs the name (`Acme Corp!` → `acme-corp`) and creates the folder. Nested folders inside a profile are just organisation: every document below `rag-data/company1/` belongs to `company1`.

### Retrieval Isolation

```
Active profile: company1
Allowed retrieval:   company1/**   +   common/**   (only if include_common)
Forbidden retrieval: company2/**  personal/**  acme/**  (everything else)
```

How this is enforced, in layers:

1. **The vector store has no unscoped search.** `VectorStore.search(vector, k, profile_ids)` requires a non-empty list and applies it inside the query (`WHERE profile_id = ANY(...)` in pgvector, a `where` filter in Chroma) — results are never fetched first and filtered afterwards.
2. **Every chunk carries `profile_id`, `document_id`, `source` (relative path)** plus the embedding signature.
3. **The scope is derived server-side.** The client sends only `profile_id`; `resolve_context` loads the profile from SQLite (unknown / removed → 404) and computes the allowed ids `[profile] (+ common)`. No path or extra id from the client is ever used.
4. **A guard in `retrieve()`** raises if a chunk outside the allowed set ever comes back.
5. **Documents are addressed by id within a profile.** `/api/profiles/company1/documents/<id-of-a-company2-doc>` is a 404.
6. **Tests** (`tests/test_profiles.py`) index `ALPHA-123` in company1 and `BETA-456` in company2 and assert company1 never sees BETA-456 — in the results, the citations and the text sent to the LLM.

### Common Knowledge Base

`rag-data/common/` is profile `common`. When another profile is active and its **include common** switch is on (default), retrieval searches `[profile, common]`. Turn it off per profile in *Profiles → Edit*. Selecting `common` itself searches only common. It cannot be deleted. Citations from it are labelled *Common*.

### Profile Instructions

The system message is assembled in fixed order: base system prompt (Settings → RAG) → a notice that retrieved text is untrusted → **Common instructions** (the `instructions` field of the `common` profile) → **Profile instructions**. Retrieved chunks go into the *user* message inside `<documents>…</documents>`, so they cannot masquerade as instructions.

## SQLite Schema

`rag-be/data/app.db` (`DB_FILE`). The filesystem holds the documents, the vector store holds the chunks, SQLite holds the app's metadata and indexing state.

```
profiles                                   documents
--------                                   ---------
id (slug, PK)   == folder name             id (uuid, PK)  == document_id in the vector store
name                                       profile_id → profiles.id
folder_path                                file_path       absolute managed path (never sent to the browser)
description                                relative_path   inside the profile folder (unique per profile)
instructions                               filename, extension, file_size, mtime_ns
is_common                                  file_hash       sha256 of the file on disk
include_common                             indexed_hash    sha256 of the content that produced the chunks
status  active | missing | removed         status          DISCOVERED PENDING INDEXING INDEXED STALE FAILED DELETED
last_sync_at                               chunk_count, indexed_at, error_message
created_at, updated_at                     embedding_model  (provider|model|dims), embedding_version,
                                           chunking_version, embedding_dimension
                                           created_at, updated_at
```

## Profile Discovery

`Filesystem → profile scanner → SQLite`. On startup, on `GET /api/profiles` and at the start of every full sync, each top-level folder of `rag-data/` that is not yet in SQLite is registered as a profile (`rag-data/newcompany/` appears as "Newcompany"). A registered profile whose folder disappeared is marked `missing` (its index is kept, and it is not re-scanned so an unmounted drive cannot wipe the index). Symlinked folders are ignored. `rename` only changes the display name — the id equals the folder name and never changes.

## Document Synchronization

`scan_profile()` compares the files under `rag-data/<profile>/**` with the `documents` table (cheap: it only re-hashes a file whose size or mtime changed):

| Filesystem | SQLite | Result |
|---|---|---|
| new file | no row | `DISCOVERED` |
| content changed | `INDEXED`, hash differs | `STALE` |
| same content, but embedding model / dimension / chunking / pipeline version differs | `INDEXED` | `STALE` |
| same content, same configuration | `INDEXED` | unchanged — **not re-embedded** |
| file gone | any | `DELETED` → chunks removed, row dropped |
| file that had `FAILED`, then changed | `FAILED` | `PENDING` (unchanged failures are not retried on every sync) |

## Indexing Lifecycle

```
Profile → filesystem scanner → document registry (SQLite) → parser → chunker → embedder → vector store
                                  DISCOVERED/STALE/PENDING → INDEXING → INDEXED   (or FAILED + error_message)
```

Indexing runs on one background worker (`IndexManager`), never inside a chat request. Requests are queued per profile and coalesced; a request that arrives while that profile is being indexed schedules a follow-up run. Each `INDEXED` document records `embedding_model`, `embedding_version`, `chunking_version`, `embedding_dimension`, `file_hash`/`indexed_hash`, `indexed_at` and `profile_id`, so a config change shows up as `STALE` documents. `Rebuild` (full or per profile) drops the vector data and re-embeds. Changing the embedding model still answers chat with `409 index_mismatch` until you rebuild. **Upgrading from the pre-profile version:** the old index has no `profile_id`, so the first chat returns `index_mismatch` — run *Rebuild index* once.

Every chunk also records the embedding model that produced it. Switching embedding model/dimensions (or changing chunk size) makes the index stale.

## API Architecture

All under `/api`, all behind `ADMIN_TOKEN` when set. Profile / config writes need `ALLOW_UI_CONFIG`, file writes need `ALLOW_UI_UPLOAD`.

```
GET    /profiles                              list (also discovers new folders) + sync status
POST   /profiles                              create {name, description, instructions, include_common}
GET    /profiles/{pid}                        details + stats
PATCH  /profiles/{pid}                        edit name / description / instructions / include_common
DELETE /profiles/{pid}[?delete_files=true&confirm={pid}]
POST   /profiles/sync[?rebuild=true]          discover + index every profile (background)
POST   /profiles/{pid}/sync[?rebuild=true]    scan + index one profile
DELETE /profiles/{pid}/index                  drop this profile's vector index only

GET    /profiles/{pid}/documents              documents (with status) + folders + stats
POST   /profiles/{pid}/documents              upload (multipart: files, folder)
GET    /profiles/{pid}/documents/{id}[/info|/file]
POST   /profiles/{pid}/documents/{id}/index   force re-index of one document
POST   /profiles/{pid}/documents/reindex      re-embed the whole profile
DELETE /profiles/{pid}/documents/{id}         delete file + chunks
GET/POST /profiles/{pid}/folders              list / create {path}
DELETE /profiles/{pid}/folders/{path}[?recursive=true&confirm=true]

POST   /chat  {profile_id, message, history, stream}      SSE: sources → token… → done
POST   /query-context {profile_id, query, limit}          retrieval only
GET    /ingest/status                                     background job status
GET    /health  /catalog  /status  /config …              unchanged
```

**Delete safety.** `DELETE /profiles/{pid}` removes the profile from the app and drops its vector index, but **keeps the files** (the profile becomes hidden and is not re-discovered; creating it again brings it back). Deleting the files as well needs `delete_files=true` *and* `confirm=<profile id>` (the UI makes you type the id). Deleting a non-empty folder needs `recursive=true&confirm=true`. `DELETE …/index` only clears the vectors.

## UI Architecture

`app/page.tsx` owns the shell state: the profile list (polled with the status), the active profile (`localStorage rag.profile`) and the conversations, which are stored per profile. `ProfileSwitcher` (top bar) → `Profiles` (management screen + edit/create/delete dialog) → `Documents` (folder tree, statuses, upload into the current folder) → `Chat` (receives the active `Profile`; sends its id with every request; citations are grouped by profile / Common and open the source through the document id). All server calls go through `lib/api.ts`.

## Troubleshooting

- **409 `index_mismatch`** — the index was built with another embedding model (or before profiles existed). Documents → *Rebuild index* (or `POST /api/profiles/sync?rebuild=true`).
- **A folder in `rag-data/` is not a profile** — its name must match `[a-z0-9][a-z0-9_-]*`; see `skipped` in the discovery result. Symlinks are ignored.
- **A new file is not searchable** — it must reach `INDEXED`. Press *Sync now* (or set `AUTO_SYNC_INTERVAL` / `SYNC_ON_STARTUP`). `FAILED` documents show the reason (e.g. scanned PDF without text).
- **Profile shows "folder missing"** — the folder was renamed or removed outside the app; restore it, or create the profile again.
- **A deleted profile keeps coming back / stays hidden** — deleting keeps files on purpose. Create a profile with the same name to restore it, or delete with `delete_files=true`.
- **Chat says "Unknown profile"** — the profile was deleted in another tab; pick another one.
- **Reset everything** — stop the backend and delete `rag-be/data/app.db` and `rag-be/data/chroma`; profiles are re-discovered from `rag-data/` on the next start.

## How ingestion works (summary)

The app hashes files (SHA-256) and compares them with SQLite: new files are added, changed files replaced, deleted files removed, unchanged files skipped. Runs in the background (progress shown in the UI) and can also run on startup (`SYNC_ON_STARTUP`) or on a timer (`AUTO_SYNC_INTERVAL`).

## Extending (using this as a template)

- LLM providers live in one folder each, `rag-be/app/llm/<provider>/` (`openai`, `gemini`, `groq`, `deepseek`, `openrouter`, `ollama`), with the same three files:
  `spec.py` (default model, env vars, base URL, quirks — **read this first**), `llm.py` (the API code) and `chat.py` (`get_<provider>_chat_response(context, question)`).
  Changing what OpenAI needs means editing only `app/llm/openai/`; the UI dropdown is generated from the specs.
- New LLM: copy a provider folder, edit `spec.py`/`llm.py`, add it to `PROVIDERS` in `app/llm/__init__.py` and its key/URL fields plus the `llm_provider` Literal in `app/config.py` (a test fails if they disagree).
- New embedder / vector store: same pattern in `app/embeddings/` and `app/vectorstores/`.
- The UI is driven by `/api/catalog`, so a new provider appears in the dropdowns automatically once it is in the catalog.

## File utilities (PDF, DOCX, ... — read these when building the next RAG)

| What | Backend (`rag-be/app/utils/`) | Frontend (`rag-ui/utils/files/`) |
|---|---|---|
| Registry: which types exist, validation, safe names | `filetypes.py` | `filetypes.ts` |
| PDF: validate, per-page text, header/footer cleanup, scanned detection, metadata, split/merge | `pdf.py` | `pdf.ts` (pre-upload check, open at cited page, download, doc info) |
| Word: validate (zip-bomb guard), headings/tables → text, metadata | `docx.py` | `docx.ts` |
| HTML, CSV/JSON → text | `html.py`, `tabular.py` | — |

Each module starts with a checklist of decisions for that format. To add a type: write the module, register it in `filetypes.py` and `filetypes.ts`, add a test. Uploads are validated in the browser (instant feedback) **and** again on the server (real header, corrupt/encrypted PDFs, fake extensions, size). Citations for PDFs are page-accurate and clickable (`manual.pdf · p.7` opens the file at page 7). API: `GET /api/documents/info?name=` and `GET /api/documents/file?name=`.

## Learning references (raw, commented versions)

- `rag-be/app/core/db.py` — hand-written asyncpg + pgvector: pool, schema, HNSW index, idempotent inserts, cosine search. Demo: `python -m app.core.db`.
- `rag-be/app/embeddings/embedding_openai.py` — the whole load → chunk → OpenAI-embed → store → search flow in one file. Run: `python -m app.embeddings.embedding_openai <file-or-folder>`.
- Both need `pip install -e ".[learning]"`; the running app uses the sync `pgvector_store.py` / `OpenAIEmbedder` instead.

## Tests

```bash
cd rag-be && pip install -e ".[dev]" && pytest      # offline: hash embedder + Chroma + stubbed LLM
```

## What was audited / fixed from the previous version

- Every Python file contained unresolved git merge-conflict markers (`<<<<<<<`), including in committed history → the old backend could not start.
- Embedding model was loaded at import time; DB dimension was a hand-kept env var that could silently mismatch.
- Providers hard-wired (OpenAI, Groq), keys only via env, no UI, no incremental ingestion, upload path used the client filename unchecked, `__pycache__` and a personal résumé PDF were committed.
- Replaced with the layered, tested design above.
