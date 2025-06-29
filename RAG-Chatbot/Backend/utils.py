import os
from sentence_transformers import SentenceTransformer
from typing import List, Tuple
import pdfplumber


# ====== PARAMETERS ======
MODEL_NAME = "thenlper/gte-large"      # Change this as needed
CHUNK_SIZE = 500                       # Adjust for your use-case
CHUNK_OVERLAP = 50                     # Overlap in characters between chunks
DOCUMENTS_DIR = "backend/documents"    # Or your path

# ====== LOAD MODEL ONCE ======
model = SentenceTransformer(MODEL_NAME)

# ====== DOCUMENT LOADING ======
def load_pdf_file(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_documents(folder: str = DOCUMENTS_DIR) -> List[str]:
    docs = []
    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if fname.lower().endswith(".txt"):
            docs.append(load_txt_file(path))
        elif fname.lower().endswith(".pdf"):
            docs.append(load_pdf_file(path))
        # Skip others
    return docs

# ====== CHUNKING ======
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    chunks = []
    i = 0
    length = len(text)
    while i < length:
        end = min(i + chunk_size, length)
        chunks.append(text[i:end])
        i += chunk_size - overlap if (chunk_size - overlap) > 0 else chunk_size
    return chunks

# ====== EMBEDDING ======
def embed_text(text: str):
    # For a single string, returns a list of floats (embedding)
    return model.encode(text).tolist()

def embed_texts(texts: List[str]):
    # For a list of strings, returns list of embeddings
    return model.encode(texts).tolist()

# ====== HIGH LEVEL: PROCESS FILE TO CHUNKS + EMBEDDINGS ======
def process_file_to_chunks_and_embeddings(
    file_path: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[Tuple[str, list]]:
    if file_path.lower().endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    elif file_path.lower().endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError("Unsupported file type")
    chunks = chunk_text(text, chunk_size, overlap)
    embeddings = embed_texts(chunks)
    return list(zip(chunks, embeddings))

async def get_rag_context(query: str, pool, top_k: int = 5):
    embedding = embed_text(query)
    from db import fetch_similar
    chunks = await fetch_similar(pool, embedding, limit=top_k)
    return "\n".join(chunks)


# ====== Example usage ======
if __name__ == "__main__":
    docs = load_documents()
    for i, doc in enumerate(docs):
        chunks = chunk_text(doc)
        print(f"Doc {i}: {len(chunks)} chunks")
