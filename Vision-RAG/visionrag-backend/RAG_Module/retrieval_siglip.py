import asyncio
from .embed import embed_text_one
from .db import query_knn

def retrieve_with_siglip(question: str):
    """
    Embed the question using SigLIP and perform k-NN search on text_chunks table.
    """
    embedding = embed_text_one(question)
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(query_knn("text_chunks", embedding, k=5))
    return {"method": "siglip", "question": question, "results": results}
