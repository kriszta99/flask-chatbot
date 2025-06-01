import os
import requests
import sys
from upstash_vector import Index
from dotenv import load_dotenv

load_dotenv()
def main():
    # a környezeti változókat beolvasom
    UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
    UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
    index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)

    if not UPSTASH_VECTOR_REST_URL or not UPSTASH_VECTOR_REST_TOKEN:
        print("❌ Hiba: Az UPSTASH_URL vagy UPSTASH_TOKEN nincs beállítva környezeti változóként.")
        sys.exit(1)
    vector_id = "chunk_238"
    new_metadata = {
            "text": "# Felvételi ütemezés\nAlapképzés: Online iratkozás: 2025. július 1 - július 13\nAlapképzés: Felvételi vizsga: 2025. július 15., kedd, 10 óra\nMesterképzés: Online iratkozás: 2025. július 1 - július 15\nMesterképzés: Felvételi vizsga: 2025. július 17., csütörtök"
    }
    response = index.update(
        id= vector_id, metadata={"text": new_metadata}
    )

    print("Response:", response)

if __name__ == "__main__":
    main()
