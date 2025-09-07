# app/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Literal

SourceType = Literal["google", "siglip"]

class Document(BaseModel):
    id: str
    source: SourceType
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None  # snippet / caption / text
    score: float

class QueryRequest(BaseModel):
    query: str
    k: int = 10

class QueryResponse(BaseModel):
    query: str
    results: List[Document]
