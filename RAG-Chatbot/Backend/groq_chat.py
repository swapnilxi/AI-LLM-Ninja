import os
import httpx
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

async def get_groq_chat_response(context: str, user_query: str):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": f"Use the following context to answer:\n{context}"},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.2,
        "max_tokens": 512
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
