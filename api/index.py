from flask import Flask, jsonify, render_template, request
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from upstash_vector import Index
import numpy as np
import os
from dotenv import load_dotenv
import requests

# Környezeti változók betöltése
load_dotenv()

UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

app = Flask(__name__)

vector_db = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)


# Kérdés-válasz modell betöltése
qa_model = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")

# ingyenes előre betanított modellt használunk a vectorokká alakitáshoz 
embedding_model  = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')


#Hasonlóság keresés a vektoradatbázisban beepitett 
def search_similar_vectors(query_embedding):
    #print(query_embedding)
    results = vector_db.query(vector=query_embedding,include_metadata=True)
    #results[0].metadata['text']
    return results  # Ez egy lista lesz, amely tartalmazza a legközelebbi találatokat

def get_context_text(search_results):
    if not search_results:  # Ha üres a lista
        return "Nincs találat."

    # Metadata "text" mezőinek összefűzése
    context = " ".join([result.metadata["text"] for result in search_results])
    print(context)
    
    return context


def generate_answer(context, user_query):
    result = qa_model(question=user_query, context=context)
    return result['answer']  

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Ha POST kérés érkezik, beágyazást (embedding) generálunk
        data = request.get_json()
        user_question = data.get("question", "").strip()

        if not user_question:
            return jsonify({"error": "Nincs megadva kérdés"}), 400

        # 1. Kérdés beágyazása
        embedding = embedding_model.encode(user_question).tolist()

        # 2. Hasonló vektorok keresése az Upstash Vector adatbázisban
        search_results = search_similar_vectors(embedding)
        
        # 3. Talált szövegrészek összefűzése


        context = get_context_text(search_results)

        # 4. Válasz generálása
        #answer = generate_answer(context, user_question)
        return jsonify({"answer": context})

    # Ha GET kérés érkezik, visszaadjuk az index.html-t
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
