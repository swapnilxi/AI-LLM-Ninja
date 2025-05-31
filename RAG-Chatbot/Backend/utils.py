import os
from sentence_transformers import SentenceTransformer
from typing import List, Tuple

# ====== PARAMETERS ======
MODEL_NAME = "thenlper/gte-large"      # Change this as needed
CHUNK_SIZE = 500                       # Adjust for your use-case
CHUNK_OVERLAP = 50                     # Overlap in characters between chunks
DOCUMENTS_DIR = "backend/documents"    # Or your path

# ====== LOAD MODEL ONCE ======
model = SentenceTransformer(MODEL_NAME)

# ====== DOCUMENT LOADING ======
def load_documents(folder: str = DOCUMENTS_DIR) -> List[str]:
    docs = []
    for fname in os.listdir(folder):
        if fname.endswith(".txt"):
            with open(os.path.join(folder, fname), "r", encoding="utf-8") as f:
                docs.append(f.read())
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
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_text(text, chunk_size, overlap)
    embeddings = embed_texts(chunks)
    return list(zip(chunks, embeddings))

# ====== Example usage ======
if __name__ == "__main__":
    # Example: process all .txt files in DOCUMENTS_DIR
    for fname in os.listdir(DOCUMENTS_DIR):
        if fname.endswith(".txt"):
            path = os.path.join(DOCUMENTS_DIR, fname)
            results = process_file_to_chunks_and_embeddings(path)
            print(f"Processed {fname}, got {len(results)} chunks.")
