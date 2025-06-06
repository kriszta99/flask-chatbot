import json
import os
import openai
import re
import json
import os
import numpy as np
from dotenv import load_dotenv
from upstash_vector import Index
import tiktoken
from upstash_vector import Vector
from upstash_vector.types import SparseVector
from FlagEmbedding import BGEM3FlagModel

# Környezeti változók betöltése
load_dotenv()

UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")
sparse_model = BGEM3FlagModel('BAAI/bge-m3',  use_fp16=True) 
# Inicializálom az Upstash Index-et
index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)
#szöveg beágyazásának lekérése OpenAI modellel.
def get_embedding(text: str, model="text-embedding-ada-002") -> np.ndarray:
    response = openai.embeddings.create(input=text, model=model)
    #embedding = response['data'][0]['embedding']
    # Az új API-ban a válasz egy objektum, nem közvetlenül szótár
    embedding = response.data[0].embedding
    return np.array(embedding)

# Tokenek számolása
def count_tokens(text, encoder):
    return len(encoder.encode(text))

# Markdown fájl beolvasása
def read_markdown_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Sorok feldolgozása
def split_lines(text):
    return text.split('\n')

# Chunkolás és JSON mentés
def chunk_text_by_line_with_headers_to_embedding(file_path, max_tokens=256, encoding_name='cl100k_base', start_chunk_id=0):
    encoder = tiktoken.get_encoding(encoding_name)
    text = read_markdown_file(file_path)
    lines = split_lines(text)

    chunks, current_chunk, current_token_count = [], [], 0
    current_header = None
    chunk_index = 1
    header_chunk_id_counter = start_chunk_id  # csak fejléc váltáskor nő

    current_chunk_id = f"chunk_{header_chunk_id_counter}"
    order_counter = 1  # a chunk_id-n belüli sorszámozáshoz

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


def chunk_to_insert_to_vectorDB(file_path, max_tokens=256, encoding_name='cl100k_base'):
    chunks = chunk_text_by_line_with_headers_to_embedding(file_path, max_tokens, encoding_name)

    for i, chunk in enumerate(chunks):


        # sparse vector 
        sparse_vectorResp = sparse_model.encode(chunk['text'], return_dense=False, return_sparse=True, return_colbert_vecs=False)
        #print(sparse_model.convert_id_to_token(sparse_vectorResp['lexical_weights']))

        sparse_vector = SparseVector(
            indices=[int(k) for k in sparse_vectorResp['lexical_weights'].keys()],
            values=[float(v) for v in sparse_vectorResp['lexical_weights'].values()]
        )
        
         # dense + sparse + metadata összevonása egy Vector objektumba
        vector_data = Vector(
            id=f"{chunk['chunk_index']}",  # ugyanaz az ID, így nem írja felül, csak bővíti
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
        print(f"Szöveg: {chunk['text'][:20]}...")  # csak rövid előnézet

        try:
            index.upsert([vector_data])
            print(f"✅ Feltöltés sikeres: {i}")
        except Exception as e:
            print(f"❌ Hiba a feltöltésnél: {i}, {str(e)}")



chunk_to_insert_to_vectorDB('../markdown/markdown_output.md',max_tokens=256)
