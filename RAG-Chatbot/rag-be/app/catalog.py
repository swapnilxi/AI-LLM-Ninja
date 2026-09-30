"""Static description of what the UI can offer: providers, suggested models, and presets."""

from .llm import llm_catalog

CATALOG = {
    "llm": llm_catalog(),  # generated from app/llm/<provider>/spec.py
    "embedding": {
        "sentence-transformers": {
            "label": "Sentence-Transformers (local, in-process)",
            "default_model": "sentence-transformers/all-MiniLM-L6-v2",
            "models": [
                "sentence-transformers/all-MiniLM-L6-v2",
                "BAAI/bge-small-en-v1.5",
                "intfloat/multilingual-e5-small",
                "sentence-transformers/all-mpnet-base-v2",
            ],
            "fields": [],
        },
        "ollama": {
            "label": "Ollama embeddings (local server)",
            "default_model": "nomic-embed-text",
            "models": ["nomic-embed-text", "mxbai-embed-large", "bge-m3"],
            "fields": ["ollama_base_url"],
        },
        "gemini": {
            "label": "Google Gemini embeddings (online)",
            "default_model": "gemini-embedding-001",
            "models": ["gemini-embedding-001"],
            "fields": ["gemini_api_key", "embedding_dimensions"],
        },
        "openai": {
            "label": "OpenAI embeddings (online, paid)",
            "default_model": "text-embedding-3-small",
            "models": ["text-embedding-3-small", "text-embedding-3-large"],
            "fields": ["openai_api_key", "openai_base_url", "embedding_dimensions"],
        },
        "hash": {
            "label": "Hashing (offline demo, lexical only)",
            "default_model": "hash-256",
            "models": ["hash-256"],
            "fields": [],
        },
    },
    "vector_store": {
        "chroma": {"label": "Chroma (local, embedded)", "fields": ["chroma_path", "vector_table"]},
        "postgres": {"label": "Postgres + pgvector (local or Neon)", "fields": ["database_url", "vector_table"]},
    },
    "presets": {
        "local": {
            "label": "Local (offline, no keys)",
            "values": {
                "llm_provider": "ollama", "llm_model": "llama3.2",
                "embedding_provider": "sentence-transformers", "embedding_model": "", "embedding_dimensions": 0,
                "vector_store": "chroma",
            },
        },
        "advanced": {
            "label": "Advanced (Gemini + local Postgres)",
            "values": {
                "llm_provider": "gemini", "llm_model": "",
                "embedding_provider": "gemini", "embedding_model": "", "embedding_dimensions": 768,
                "vector_store": "postgres",
                "database_url": "postgresql://rag:rag@localhost:5432/rag",
            },
        },
        "production": {
            "label": "Production (OpenRouter/Gemini + Neon)",
            "values": {
                "llm_provider": "openrouter", "llm_model": "",
                "embedding_provider": "gemini", "embedding_model": "", "embedding_dimensions": 768,
                "vector_store": "postgres",
            },
        },
    },
}
