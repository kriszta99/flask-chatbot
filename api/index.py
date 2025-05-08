from flask import Flask, jsonify, render_template, request 
from upstash_vector import Index
import numpy as np
from functools import lru_cache
from collections import defaultdict
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

# -----Caching eszközök -----
_query_cache = {}

def embedding_to_tuple(embedding: list[float]):
    return tuple(round(x, 3) for x in embedding)

def cached_vector_query(query_embedding,top_k=1000):
    key = embedding_to_tuple(query_embedding)
    if key in _query_cache:
        return _query_cache[key]
    results = vector_db.query(vector=query_embedding, include_metadata=True, top_k=top_k)
    _query_cache[key] = results
    return results

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
def get_chunk_id_from_embedding(query_embedding):
    results = vector_db.query(vector=query_embedding, include_metadata=True)
    chunk_ids = [result.metadata.get('chunk_id') for result in results]
    return chunk_ids

def query_by_chunk_id(query_embedding, chunk_ids):
    results = cached_vector_query(query_embedding, 1000)

    # Szűrés a chunk_id alapján
    filtered_results = [
        result for result in results
        if result.metadata.get('chunk_id') in chunk_ids
    ]

    if not filtered_results:
        print("\nNincs találat.")
        return {}

    # Csoportosítás chunk_id szerint
    grouped_by_chunk_id = defaultdict(list)
    for result in filtered_results:
        chunk_id = result.metadata.get('chunk_id')
        grouped_by_chunk_id[chunk_id].append(result)

    # Rendezés minden chunk_id csoporton belül chunk_order szerint
    for chunk_id in grouped_by_chunk_id:
        grouped_by_chunk_id[chunk_id].sort(key=lambda r: r.metadata.get('chunk_order', 0))

    return grouped_by_chunk_id

def get_context_text(query_embedding):
    chunk_ids = get_chunk_id_from_embedding(query_embedding)
    if not chunk_ids:
        return "Nem található chunk_id."

    grouped_results = query_by_chunk_id(query_embedding, chunk_ids)
    if not grouped_results:
        return f"Nincs találat a(z) {chunk_ids} chunk_id-re."

    # Minden chunk_id-hoz tartozó szöveg összefűzése, chunk_order szerint
    context_parts = []
    for chunk_id in sorted(grouped_results.keys()):
        texts = [r.metadata.get('text') for r in grouped_results[chunk_id]]
        context_parts.append("\n".join(texts))

    # chunk_id csoportokat elválasztjuk dupla sortöréssel
    context = "\n\n".join(context_parts)
    return context



def get_llm_response(context, question):
    client = genai.Client(api_key=api_key)

    full_prompt = f"Context: {context}\nQuestion: {question}"

    response = client.models.generate_content(
        #model="gemini-2.0-flash-thinking-exp-01-21",
        model = "gemini-2.0-flash",
        contents=[full_prompt]
    )
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
