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
    vector_id = "chunk_253"


    response = index.update(
        id= vector_id, metadata={"text": "# Lapozható tájékoztató füzet\nA Sapientia EMTE minden évben kiadja felvételi tájékoztató füzetét, mellyel a pályaválasztás előtt állókat szeretné segíteni.\nA kiadványban az egyetemi felvételire készülő diákok megtalálhatják a számukra leginkább tetsző szakot és sok fontos információt a felvételiről.\nLapozható tájékoztató füzet (https://issuu.com/sapientiaemte/docs/sap_felveteli-taj-2025_online)",
        "chunk_id": "chunk_78",
        "chunk_order": 1,
        "header": " Lapozható tájékoztató füzet"
        }
    )

    print("Response:", response)

if __name__ == "__main__":
    main()
