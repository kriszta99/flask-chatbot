from flask import Flask, jsonify, render_template, request 
from upstash_vector import Index
import numpy as np
import os
import openai
from google import genai
from dotenv import load_dotenv

# Környezeti változók betöltése
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
api_key = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)
vector_db = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)

# OpenAI embedding generálás
def get_embedding(text: str, model="text-embedding-ada-002") -> list:
    response = openai.embeddings.create(input=text, model=model)
    return response.data[0].embedding
"""
# Legközelebbi vektorok lekérdezése
def query_nearest_neighbors_of_a_vector(query_embedding):
    results = vector_db.query(vector=query_embedding, include_metadata=True)
    return results

# Kontextus összeállítása
def get_context_text(search_results):
    if not search_results:
        return "Nincs találat."
    context = " ".join([result.metadata['text'] for result in search_results])

    return context
"""
"""
def get_chunk_id_from_embedding(query_embedding):
    results = vector_db.query(vector=query_embedding, include_metadata=True)
    chunk_id = results[0].metadata.get('chunk_id')
    #chunk_header = results[0].metadata.get('header')
    return chunk_id

# Ellenőrző kiírás
def query_by_chunk_id(query_embedding, chunk_id):
    # Első lépés: Kérjük le az összes vektort (szűrés nélkül)
    results = vector_db.query(vector=query_embedding, include_metadata=True,top_k=1000)
    
    # Második lépés: Szűrés a chunk_id és header alapján
    filtered_results = [
        result for result in results
        if result.metadata.get('chunk_id') == chunk_id 
    ]

    # Rendezés chunk_order szerint
    filtered_results.sort(key=lambda r: r.metadata.get('chunk_order', 0))
    
    # Ellenőrizzük, hogy van-e találat
    if not filtered_results:
        print("\nNincs találat.")
        return []
    
    # Az összes szöveg összegyűjtése
    chunk_texts = [result.metadata.get('text', '') for result in filtered_results]
    print(f"\nSzövegek: {chunk_texts}")
    return chunk_texts  # Az összes szöveg visszaadása


def get_context_text(query_embedding):
    chunk_id = get_chunk_id_from_embedding(query_embedding)
    if not chunk_id:
        return "Nem található chunk_id."

    relevant_results = query_by_chunk_id(query_embedding, chunk_id)
    if not relevant_results:
        return f"Nincs találat a(z) {chunk_id} chunk_id-re."

    #context = "\n".join([result.metadata.get('text', '') for result in relevant_results])
    context = "\n".join(relevant_results)

    return context

"""

def get_chunk_id_from_embedding(query_embedding):
    results = vector_db.query(vector=query_embedding, include_metadata=True)  # Több találatot keresünk 
    # Az összes chunk_id 
    chunk_ids = [result.metadata.get('chunk_id') for result in results]
    return chunk_ids


def query_by_chunk_id(query_embedding, chunk_ids):
    # Első lépés: Kérjük le az összes vektort (szűrés nélkül)
    results = vector_db.query(vector=query_embedding, include_metadata=True, top_k=1000)
    
    # Második lépés: Szűrés a chunk_id és header alapján
    filtered_results = [
        result for result in results
        if result.metadata.get('chunk_id') in chunk_ids 
    ]

    # Rendezés chunk_order szerint
    filtered_results.sort(key=lambda r: r.metadata.get('chunk_order', 0))
    
    # Ellenőrizzük, hogy van-e találat
    if not filtered_results:
        print("\nNincs találat.")
        return []
    
    # Az összes szöveg összegyűjtése
    chunk_texts = [result.metadata.get('text') for result in filtered_results]
    print(f"\nSzövegek: {chunk_texts}")
    return chunk_texts  # Az összes szöveg visszaadása


def get_context_text(query_embedding):
    chunk_ids = get_chunk_id_from_embedding(query_embedding)
    
    if not chunk_ids:
        return "Nem található chunk_id."

    # Több chunk_id-t és chunk_header-t használunk szűréshez
    relevant_results = query_by_chunk_id(query_embedding, chunk_ids)
    
    if not relevant_results:
        return f"Nincs találat a(z) {chunk_ids} chunk_id-re."
    
    # Kontextus összeállítása
    context = "\n".join(relevant_results)
    return context
def get_llm_response(context, question):
    client = genai.Client(api_key=api_key)

    full_prompt = f"Context: {context}\nQuestion: {question}"

    response = client.models.generate_content(
        model="gemini-2.0-flash-thinking-exp-01-21",
        contents=[full_prompt]
    )
    
    print(response.text)
    return response.text

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json()
        user_question = data.get("question", "").strip()

        if not user_question:
            return jsonify({"error": "Nincs megadva kérdés"}), 400

        embedding = get_embedding(user_question)
        
        #search_results = query_nearest_neighbors_of_a_vector(embedding)
        #context = get_context_text(search_results)
        # Kontextus összeállítása a lekérdezett embedding alapján
        context = get_context_text(embedding)
        resp = get_llm_response(context,user_question)

        # (Opcionálisan itt jönne a válasz generálás LLM-mel)
        return jsonify({"answer": resp})

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
