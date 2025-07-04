import os
import openai
import json
import os
import requests
import numpy as np
from dotenv import load_dotenv
from upstash_vector import Index
import tiktoken
from upstash_vector import Vector
from upstash_vector.types import SparseVector

# betölttöm a környezeti változókat
load_dotenv()

UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

# inicializálom az Upstash Index-et
index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)
#szöveg beágyazásának lekérése OpenAI modellel.
def get_embedding(text: str, model="text-embedding-ada-002") -> np.ndarray:
    response = openai.embeddings.create(input=text, model=model)
    #embedding = response['data'][0]['embedding']
    # Az új API-ban a válasz egy objektum, nem közvetlenül szótár
    embedding = response.data[0].embedding
    return np.array(embedding)

# tokeneket kiszámolom
def count_tokens(text, encoder):
    return len(encoder.encode(text))

# Markdown fájlt beolvasom ezzel a fügvénnyel
def read_markdown_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# a sorokat feldolgozom
def split_lines(text):
    return text.split('\n')

# a chunkolási allgoritmus
def chunk_text_by_line_with_headers_to_embedding(file_path, max_tokens=256, encoding_name='cl100k_base', start_chunk_id=0):
    encoder = tiktoken.get_encoding(encoding_name)
    text = read_markdown_file(file_path)
    lines = split_lines(text)

    chunks, current_chunk, current_token_count = [], [], 0
    current_header = None
    chunk_index = 1
    header_chunk_id_counter = start_chunk_id  

    current_chunk_id = f"chunk_{header_chunk_id_counter}"
    order_counter = 1  # a chunk_id-n belüli sorszámozás

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('# '):
            if current_chunk:
                embedded = get_embedding(current_chunk)
                chunks.append({
                    "chunk_index": f"chunk_{chunk_index}",
                    "chunk_id": current_chunk_id,
                    "order": order_counter,
                    "header": current_header,
                    "text": '\n'.join(current_chunk),
                    "embedding": embedded.tolist(),
                    "token_count": current_token_count
                })
                chunk_index += 1
                order_counter += 1
                current_chunk, current_token_count = [], 0

            current_header = line
            header_chunk_id_counter += 1
            current_chunk_id = f"chunk_{header_chunk_id_counter}"
            order_counter = 1  # új chunk_id → újraindítjuk az order számozást

        token_count = count_tokens(line, encoder)

        if token_count > max_tokens:
            if current_chunk:
                embedded = get_embedding(current_chunk)
                chunks.append({
                    "chunk_index": f"chunk_{chunk_index}",
                    "chunk_id": current_chunk_id,
                    "order": order_counter,
                    "header": current_header,
                    "text": '\n'.join(current_chunk),
                    "embedding": embedded.tolist(),
                    "token_count": current_token_count
                })
                chunk_index += 1
                order_counter += 1
                current_chunk, current_token_count = [], 0

            embedded = get_embedding([line])
            chunks.append({
                "chunk_index": f"chunk_{chunk_index}",
                "chunk_id": current_chunk_id,
                "order": order_counter,
                "header": current_header,
                "text": line,
                "embedding": embedded.tolist(),
                "token_count": token_count
            })
            chunk_index += 1
            order_counter += 1
            continue

        if current_token_count + token_count > max_tokens:
            if current_chunk:
                embedded = get_embedding(current_chunk)
                chunks.append({
                    "chunk_index": f"chunk_{chunk_index}",
                    "chunk_id": current_chunk_id,
                    "order": order_counter,
                    "header": current_header,
                    "text": '\n'.join(current_chunk),
                    "embedding": embedded.tolist(),
                    "token_count": current_token_count
                })
                chunk_index += 1
                order_counter += 1
                current_chunk, current_token_count = [], 0

        current_chunk.append(line)
        current_token_count += token_count

    if current_chunk:
        embedded = get_embedding(current_chunk)
        chunks.append({
            "chunk_index": f"chunk_{chunk_index}",
            "chunk_id": current_chunk_id,
            "order": order_counter,
            "header": current_header,
            "text": '\n'.join(current_chunk),
            "embedding": embedded.tolist(),
            "token_count": current_token_count
        })

    return chunks
# API hívás a sparse vektor lekéréséhez egy darabolt szöveghez
def get_sparse_vector_from_api(text_chunk):
    url = "https://api.deepinfra.com/v1/inference/BAAI/bge-m3-multi"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer GPdqwIzw3NsvoJiynSDGrO9C0HjQ1X2t"
    }
    data = {
        "inputs": [text_chunk],
        "dense": False,
        "sparse": True,
        "colbert": False
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        json_resp = response.json()
        sparse_vec_full = json_resp['sparse'][0]
        # csak a nem nulla elemeket vesszük, index és érték párban
        indices = [int(i) for i, v in enumerate(sparse_vec_full) if v != 0]
        values = [float(v) for v in sparse_vec_full if v != 0]
        return {"indices": indices, "values": values}
    else:
        raise Exception(f"API hiba: {response.status_code} - {response.text}")

def chunk_to_insert_to_vectorDB(file_path, max_tokens=256, encoding_name='cl100k_base'):
    # meghivom a darabolási függvényemet ami egy listát ad vissza
    chunks = chunk_text_by_line_with_headers_to_embedding(file_path, max_tokens, encoding_name)

    # inditok egy for ciklust, végigmegyek minden feldarabolton
    for i, chunk in enumerate(chunks):
        try:
        # lekérem az adott chunk sparse vektorát az API-ból
            sparse_vector_resp = get_sparse_vector_from_api(chunk['text'])
        except Exception as e:
                print(f"Hiba az API hívásnál: {e}")
                break

        try:
            # SparseVector obijektumba rakom az Uptash adatázis szintaxia miadt
            sparse_vector = SparseVector(
                indices=sparse_vector_resp['indices'],
                values=sparse_vector_resp['values']
            )
            
            # dense + sparse + metadata összevonása egy Vektor objektumba amit feltöltöm a vektoradatbázisba
            vector_data = Vector(
                id=f"{chunk['chunk_index']}",  
                vector=chunk['embedding'],
                sparse_vector=sparse_vector,
                metadata={
                    "text": chunk['text'],
                    "chunk_id": chunk['chunk_id'],
                    "chunk_order": chunk['order'],
                    "header": chunk['header']
                }
            )

            print(f"\nIndex: {chunk['chunk_index']}, Chunk_id: {chunk['chunk_id']},sparseVector: {sparse_vector}, chunk_order: {chunk['order']}, Header: {chunk['header']}")
            print(f"Szöveg: {chunk['text'][:20]}...")  # csak rövid előnézetre kell
            # adatbázisba való feltöltés
            index.upsert([vector_data])
            print(f"Sikeres feltöltés: {i}")
        except Exception as e:
            print(f"Hiba a feltöltésnél: {i}, {str(e)}")

# meghivom az adatbázisba való feltöltési metodusomat, 2 paraméter: útvonal, maximális chunkolási értek  
chunk_to_insert_to_vectorDB('../markdown/markdown_output.md',max_tokens=256)
