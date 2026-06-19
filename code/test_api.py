import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
import os

async def main():
    try:
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-1.5-flash",
            contents="Hello, world!",
        )
        print(response.text)
    except Exception as e:
        print("ERROR:", type(e))
        print("ERROR:", e)

asyncio.run(main())
