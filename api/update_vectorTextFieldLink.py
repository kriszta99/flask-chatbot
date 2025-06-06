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
    vector_id = "chunk_477"


    response = index.update(
        id= vector_id, metadata={"text": "# Fordító és tolmács szak\nAlkalmazott Nyelvészeti Tanszék útmutatója (https://ms.sapientia.ro/content/docs/MS/Zarovizsga/2025/03%20Szakdolgozat-keszitesi%20utmutato%202025.pdf)",
        "chunk_id": "chunk_140",
        "chunk_order": 1,
        "header": "# Fordító és tolmács szak"
        }
    )

    print("Response:", response)

if __name__ == "__main__":
    main()
