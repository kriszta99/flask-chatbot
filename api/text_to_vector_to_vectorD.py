import requests
import json
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
from upstash_vector import Index


# Környezeti változók betöltése
load_dotenv()

UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")


# Inicializálom az Upstash Index-et
index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)

# Embedding model betöltése
model = SentenceTransformer("all-MiniLM-L6-v2")

#Generálás és feltöltés soronként
def generate_and_upload_vectors(file_name):
    with open(file_name, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
    
        # Embedding generálása
        embedding = model.encode(line).tolist()

        # Vektor adatainak előkészítése
        vector_data = {
            "id": f"vector_{i}",
            "vector": embedding,  # "vector" helyett "values"
            "metadata": {"text": line}
        }

        # Feltöltés az adatbázisba soronként
        try:
            index.upsert([vector_data])  # Feltöltés egyetlen vektorra
            print(f"✅ Feltöltés sikeres: {i}")
        except Exception as e:
            print(f"❌ Hiba a feltöltésnél: {i}, {str(e)}")

# Fájl olvasása és feltöltés indítása
generate_and_upload_vectors("sapientia_kepzesei.txt")
