import os
<<<<<<< HEAD
import httpx
=======
import requests
>>>>>>> 339029c (first-api)
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
<<<<<<< HEAD
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")  # Use default if not available

=======
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"  # Adjust if needed
GROQ_MODEL = "llama3-70b-8192"  # or your preferred model

system_prompt = (
    "Answer as an expert using ONLY the following context. "
    "If unsure, say 'I don't know.'\n\n"
    "Context:\n{context}"
)

messages = [
    {"role": "system", "content": system_prompt.format(context=context)},
    {"role": "user", "content": user_query}
]
>>>>>>> 339029c (first-api)
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
<<<<<<< HEAD
    async with httpx.AsyncClient() as client:
        resp = await client.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
=======
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
>>>>>>> 339029c (first-api)
