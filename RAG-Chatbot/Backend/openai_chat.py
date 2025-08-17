import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"  # or "gpt-4o" if enabled

async def get_openai_chat_response(context: str, user_query: str):
    messages = [
        {"role": "system", "content": f"Use the following context to answer:\n{context}"},
        {"role": "user", "content": user_query}
    ]
    response = openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=512
    )
    return response.choices[0].message.content.strip()
