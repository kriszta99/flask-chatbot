from flask import Flask, jsonify, render_template, request
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

# ingyenes előre betanított modellt használunk a vectorokká alakitáshoz 
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Ha POST kérés érkezik, beágyazást (embedding) generálunk
        data = request.get_json()
        user_question = data.get("question", "").strip()

        if not user_question:
            return jsonify({"error": "Nincs megadva kérdés"}), 400

        embedding = model.encode(user_question).tolist()
        return jsonify({"embedding": embedding})

    # Ha GET kérés érkezik, visszaadjuk az index.html-t
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
