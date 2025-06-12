from flask import Flask, jsonify, render_template, redirect, request
from upstash_vector import Index
import numpy as np
from collections import defaultdict
import os
import pandas as pd
import time
import openai
from bert_score import score
from google import genai
from upstash_vector.types import SparseVector, FusionAlgorithm, QueryMode
from concurrent.futures import ThreadPoolExecutor, wait
import threading
import requests
from dotenv import load_dotenv

# Környezeti változók betöltése
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
api_key = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

vector_db = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)
loading_done = False
loading_started = False
loading_lock = threading.Lock()


results_ = []
#lekérem az összes vektort (parhuzamosan hogy gyorsitsam a lekeresi időt) egy globalis listaba az adatbazisból ösz:1158
def load_all_vectors_to_list():
    global results_, loading_done
    start_total_load = time.time()
    results_.clear()
    loading_done = False

    def fetch_range(cursor, limit):
        return vector_db.range(cursor=cursor, limit=limit, prefix="chunk_", include_metadata=True).vectors

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(fetch_range, "0", 579),
            executor.submit(fetch_range, "579", 579)
        ]

        for future in futures:
            results_.extend(future.result())

    end_total_load = time.time()
    #print(results_)
    print(f"Betöltve {len(results_)} vektor, össz idő: {end_total_load - start_total_load:.2f} s")
    loading_done = True

# OpenAI embedding-é alakitom a felhasználó kérdését    
def get_embedding(text: str, model="text-embedding-ada-002") -> np.ndarray:
    try:
        response = openai.embeddings.create(input=text, model=model)
        # Az új API-ban a válasz egy objektum, nem közvetlenül szótár
        embedding = response.data[0].embedding
        return np.array(embedding)
    except Exception as e:
        if "503" in str(e) or "Rate limit" in str(e):
            raise RuntimeError(f"A text-embedding-ada-002 modell limitje elfogyott.")
        else:
            raise RuntimeError(f"Embedding model error:{str(e)}")

print("Warming up embedding model...")
get_embedding("warmup request", model="text-embedding-ada-002")
print("Embedding model ready.")

#BGE-M3 sparse embedding modell segitségével atalakitom a felhasznaló kérdését Sparse vectorrá s visszatéritem 
def get_sparse_vector_from_query(user_query: str) -> SparseVector:
    url = "https://api.deepinfra.com/v1/inference/BAAI/bge-m3-multi"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer GPdqwIzw3NsvoJiynSDGrO9C0HjQ1X2t"
    }
    data = {
        "inputs": [user_query],
        "dense": False,
        "sparse": True,
        "colbert": False
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            json_resp = response.json()
            sparse_vec_full = json_resp['sparse'][0]

            arr = np.array(sparse_vec_full)
            nonzero_indices = np.nonzero(arr)[0]
            nonzero_values = arr[nonzero_indices].astype(float)

            indices = nonzero_indices.tolist()
            values = nonzero_values.tolist()

            return SparseVector(indices=indices, values=values)

        elif response.status_code == 503:
            raise RuntimeError("A bge-m3 modell túlterhelt. Próbáld meg később újra.")
        else:
            raise Exception(f"API hiba: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        # hálózati hiba vagy timeout
        raise RuntimeError(f"Hálózati vagy kapcsolat hiba: {str(e)}")    

print("Warming up sparse  model...")
get_sparse_vector_from_query("warmup request")
print("sparse model is ready.")  

"""
#dense vector lekerdezese
def get_chunk_id_from_embedding(query_embedding):
    #legközelebbi vektorok lekérdezése
    results = vector_db.query(vector=query_embedding, include_metadata=True,top_k=50,query_mode=QueryMode.DENSE)    
    chunk_ids = [result.metadata.get('chunk_id') for result in results]
    sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
    chunk_ids = []
    for result in sorted_results:
        if result.score >= 0.86:
            #print(f"chunk_id: {result.metadata.get('chunk_id')}\nText: {result.metadata.get('text')}\nScore: {result.score}\n\n")
            chunk_ids.append(result.metadata.get('chunk_id'))

    print(len(chunk_ids)) 
    #print(chunk_ids)
    return chunk_ids"""
#hibrid lekerdezes: dense (sűrű) + sparse (ritka) vectorok és a függvny visszaadja a chunk_id-ket
def get_chunk_id_from_embedding(query_embedding, query_sparse_vector):
    # hibrid lekérdezés: dense + sparse
    results = vector_db.query(
        vector=query_embedding,
        sparse_vector=query_sparse_vector,
        fusion_algorithm=FusionAlgorithm.RRF,  # vagy FusionAlgorithm.DBSF
        include_metadata=True,
        top_k=50,
        query_mode=QueryMode.HYBRID
    )

    # Szűrés pontszám alapján
    #sorted_results = sorted(results, key=lambda r: r.score, reverse=True)

    """sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
    chunk_ids = [
        result.metadata.get('chunk_id')
        for result in sorted_results
        if result.score >= 0.86
    ]"""
    # chunk_id-k kiszűrése, duplikációk eltávolítása
    chunk_ids = list(dict.fromkeys(
        result.metadata.get('chunk_id') for result in results
    ))
    #print(chunk_ids)
    print(len(chunk_ids))
    return chunk_ids

def query_by_chunk_id(chunk_ids): 

    # Szűrés a chunk_id alapján
    filtered_results = [
        r for r in results_
        if r.metadata.get("chunk_id") in chunk_ids
    ]
  
    if not filtered_results:
        print("\nNincs találat.")
        return {}

     #csoportosítom chunk_id szerint a kontextus megmaradása érdekében
    grouped_by_chunk_id = defaultdict(list)
    for r in filtered_results:
        cid = r.metadata.get("chunk_id")
        grouped_by_chunk_id[cid].append(r)

    #rendezem minden csoporton belül chunk_order szerint hogy a kontextusban a megfeleő sorendben legyenek összeallitva a szövegek
    for cid in grouped_by_chunk_id:
        grouped_by_chunk_id[cid].sort(key=lambda r: r.metadata.get("chunk_order", 0))

    return grouped_by_chunk_id,len(chunk_ids)

def get_context_text(query_embedding,query_sparse_vector):
    try:
        #chunk_ids = get_chunk_id_from_embedding(query_embedding,user_question)
        chunk_ids = get_chunk_id_from_embedding(query_embedding,query_sparse_vector)
        if not chunk_ids:
            # nincs releváns chunk — fallback szöveg
            return (
                "Figyelem: Nem áll rendelkezésre releváns kontextus. "
                "Kérlek, válaszolj a saját tudásod alapján, ha tudsz, vagy jelezd, hogy nem tudsz válaszolni."
            ), 0

        grouped_results, top_k_size = query_by_chunk_id(chunk_ids)
        if not grouped_results:
            # nincs találat — fallback szöveg
            return (
                "Figyelem: Nem áll rendelkezésre releváns kontextus. "
                "Kérlek, válaszolj a saját tudásod alapján, ha tudsz, vagy jelezd, hogy nem tudsz válaszolni."
            ), 0

        # minden chunk_id-hoz tartozó szöveg összefűzése, chunk_order szerint
        context_parts = []
        for chunk_id in sorted(grouped_results.keys()):
            texts = [r.metadata.get('text','') for r in grouped_results[chunk_id]]
            text_joined = "\n".join(texts)
            context_parts.append(f"{chunk_id}\n{text_joined}")

        # chunk_id csoportokat elválasztjuk dupla sortöréssel
        context = "\n\n".join(context_parts)
        return context, top_k_size
    except Exception as e:
        print(f"Hiba a kontextus összeállítása során: {e}")
        # hiba esetén is fallback szöveg, a rendszer ne essen szét 
        return (
            "Figyelem: Nem áll rendelkezésre releváns kontextus (hiba történt a kontextus generálásakor). "
            "Kérlek, válaszolj a saját tudásod alapján, ha tudsz, vagy jelezd, hogy nem tudsz válaszolni."
        ), 0



#az LLM model segitségével választ generalok a feltett kérdésre
def get_llm_response(context, question):
    
    client = genai.Client(api_key=api_key)

    full_prompt = f"<context>{context}</context>Kérem, válaszoljon az alábbi kérdésre a fent megadott kontextus alapján, vedd ki a markdown formátumot:<user_query>{question}</user_query>\nVálasz:"
    try:
        response = client.models.generate_content(
            #model="gemini-2.0-flash-thinking-exp-01-21",
            model = "gemini-2.0-flash",
            #model="gemini-1.5-flash",
            #model="gemini-2.0-flash",
            #model = "gemini-2.5-flash-preview-05-20",


            contents=[full_prompt]
        )
        return response.text
    except Exception as e:
        if "503" in str(e):
            raise RuntimeError(f"Az LLM modell túlterhelt. Próbáld meg később újra.")
        else:
            raise RuntimeError(f"LLM error:{str(e)}")

def save_timings_to_excel(filepath, question, t_embed,t_sparse_embed, t_ctx, t_llm, t_total,bertscore_f1,top_k_size):
    new_row = {
        "felhasznaló kérdése": question,
        "embedding generálásai idő": round(t_embed, 3),
        "sparse embedding generálási idő": round(t_sparse_embed,3),
        "kontextus összeállitási idő": round(t_ctx, 3),
        "LLM feldolgozási idő": round(t_llm, 3),
        "teljes feldoldozási idő": round(t_total, 3),
        "szemantikus hasonlóság méréke(BERTScore F1)": round(bertscore_f1,3),
        "top_k darab száma":top_k_size


     }


    # ha létezik a fájl beolvasom, ha nem létrehozom az új DataFrame-et
    if os.path.exists(filepath):
        df = pd.read_excel(filepath)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])

    df.to_excel(filepath, index=False)
    
ground_truths_vector_by_search_20 = [
    "2018-ban egy újabb szárny nyílt meg a Campuson, a C épület, amelyben két amfiteátrum, számos terem és laboratórium is létesült.",
    "dr. Horobeț Emil, egyetemi docens",
    """Vakációban (a nyári szünet alatt is):
    *   hétfő – péntek: 8:00 – 15:00
    *   szombat – vasárnap: zárva.""",
    "Ungvári Zsuzsi, PR-felelős",
    "Dr. Suba Réka - docens, tanszékvezető-helyettes, szakkoordinátor (Fordító és tolmács szak)",
    "A Mechatronika képzési szak 1990 után jelent meg a romániai felsőoktatásban, az ipar által támasztott igények kielégítésére, azon szakterületeken, ahol a szakember gépészmérnöki, villamosmérnöki és informatikai alapismeretekkel kell rendelkezzen.",
    "Dr. Márton Gyöngyvér, adjunktus, szakkoordinátor (Szoftverfejlesztés)",
    "helyben olvasás a 72 férőhelyes szabadpolcos olvasóteremben",
    """További nem kölcsönözhető dokumentumaink:
      *   tájékoztató segédkönyvek (szótárak, lexikonok),
      *   folyóiratok,
      *   szakdolgozatok (raktárból felkérhető).""",
    "Ha az Ön jövedelme csak fizetésből (egy vagy több) származik, akkor a **230**-as formanyomtatványt kell kitöltenie.",
    "Babos Annamária gazdasági igazgató",
    "* A Varjútábort, amit a már elballagott diákoknak szervezünk, hogy együtt tölthessünk egy hétvégét a régi idők emlékére.",
    """Feladatkör: Iroda felelős
    * Név: Ozsváth-Berényi Attila""",
    "A kar főépületét körülvevő 27 hektáros területen a kertészmérnöki szakos diákok gyakorlatoznak, akik parkosítják a terület egy részét.",
    "**Elnök:**\n* dr. Szabó László-Zsolt, egyetemi adjunktus",
    "Kölcsönözni csak személyesen, érvényes könyvtári igazolvánnyal lehet.",
    "A HÖK három legfontosabb feladata:\n* Információ továbbítás\n* Érdekképviselet\n* Rendezvényszervezés",
    "Vizsgaidőszakban szombat délelőttönként is nyitva tartunk, a pontos dátumokat előzőleg hirdetjük a Hírek, közlemények almenüben.",
    "Matematika-Informatika Tanszék (https://ms.sapientia.ro/hu/a-karrol/tanszeke/matematika-informatika-tanszek)",
    """## Marosvásárhelyi Kar
       Târgu-Mureş/Corunca (Marosvásárhely/Koronka), Calea Sighișoarei nr. 2.
       (26, 27, 44-es közszállítási vonal végállomása)
       Tel: +40 265 206 210
       fax: +40 265 206 211
       Postacím: 540485 Târgu-Mureş, O.p. 9, C.p. 4
       E-mail: office@ms.sapientia.ro
       Weboldal (http://ms.sapientia.ro/)"""
]

ground_truths_vector_by_search_40 = [
    "https://sapientia.ro/hu/az-egyetemrol/akkreditacio/akkreditacios-felmeresek-dokumentumai",
    """Főbb tantárgyak:
        - algoritmusok és adatstruktúrák
        - programozási nyelvek
        - szoftvertechnológiák
        - mesterséges intelligencia
        - informatikai biztonság""",
    "4 év",
    """Fejlett mechatronikai rendszerek szak 
        Növényorvos szak
        Számítógépes irányítási rendszerek szak 
        Szoftverfejlesztés szak""",
    "15",
    "2025. július 15., kedd, 10 óra",
    "2025. július 1 - július 15",
    "https://ms.sapientia.ro/hu/felveteli/felveteli-tudnivalok_/felveteli-szabalyzatok",
    "https://sapientia.ro/hu/felveteli/szukseges-iratok",
    "https://ms.sapientia.ro/content/docs/MS/Felveteli/2023/Felveteli_Matek2023SZEPT-B-Varians_1.pdf (javítókulcs) https://ms.sapientia.ro/content/docs/MS/Felveteli/2023/Felveteli_Matek2023SZEPT-B-VariansJAVITOKULCS_1.pdf",
    "https://issuu.com/sapientiaemte/docs/sap_felveteli-taj-2025_online",
    "https://ms.sapientia.ro/hu/hallgatoknak/hallgatoi-tajekoztato/gyakorlati-orak-potlasa",
    "Románia parlamentjének képviselőháza 2012. február 28-i ülésén megszavazta a Sapientia Erdélyi Magyar Tudományegyetem akkreditálását.",
    "Fő célja, hogy lehetővé tegye a munkaerőpiacon való elhelyezkedést biztosító diploma megszerzését, ezért az alapképzés során a gyakorlati képzés kap nagyobb hangsúlyt.",
    "Dr. Farkas Csaba, egyetemi tanár, a Sapientia EMTE általános rektorhelyettese",
    "- Informatika: dr. Jánosi-Rancz Tünde Katalin, adjunktus, tsuto@ms.sapientia.ro",
    "Az ösztöndíjat a hallgató egy összegben kapja meg a tanév elején az előző évi teljesítménye függvényében.",
    "Befizetési határidő: július 28.",
    "100 lej",
    "Adminisztratív díjak bankon keresztül utalhatóak a következő bankszámlára: RO48BTRLRONCRT0039221810 UNIVERSITATEA SAPIENTIA, CORUNCA, CF: RO14645945",
    "A felvételi jegy összetétele: 100% érettségi átlag",
    "Kari Erasmus Koordinátor: Biblia Csilla (sapierasmus@ms.sapientia.ro)",
    """Egyetem neve: Budapest University of Technology and Economics(Műszaki és Gazdaságtudományi Egyetem)
       Egyetem neve: Budapest University of Technology and Economics(Műszaki és Gazdaságtudományi Egyetem)
       Egyetem neve: University of Debrecen (Debreceni Egyetem)
       Egyetem neve: Eötvös Loránd University (Eötvös Loránd Tudományegyetem)
       Egyetem neve: Eszterházy Károly University(Eszterházy Károly Főiskola)
       Egyetem neve: Károli Gáspár University of The Refomed Church In Hungary (Károli Gáspár Református Egyetem)
       Egyetem neve: College of Nyíregyháza (Nyíregyházi Egyetem)
       Egyetem neve: University of Pannonia (Pannon Egyetem)
       Egyetem neve: University of Pécs (Pécsi Tudományegyetem)
       Egyetem neve: Semmelweis University (Semmelweis Egyetem)
       Egyetem neve: Szegedi Tudományegyetem
       Egyetem neve: Szent István Egyetem, Gödöllő
       Egyetem neve: Széchenyi István Egyetem, Győr""",
    "https://ms.sapientia.ro/content/2011-2021/nemzetkozi-hallgatok/International-student-guide-Sapientia.pdf",
    "Sapientia Erdélyi Magyar Tudományegyetem az oktatás megszervezésében az Európai Kreditátviteli Rendszert (ECTS) alkalmazza, amely által az egyetemi képzésben a végzettséget igazoló oklevél megszerzésének feltételéül előírt minden, tanulmányi munkaidő ráfordítással járó követelmény teljesítését kreditben méri.",
    "Vegyes intenzív programok (BIP)",
    "A Sapientia szó bölcsességet jelent, más szóval értő tanulmányozást és a tudásmegfontolt alkalmazását.",
    "A hátrányos helyzetű hallgatók hosszú mobilitás esetén havi 250 euró kiegészítő támogatást kapnak, úgy tanulmányi mobilitás, mind szakmai gyakorlat mobilitás esetén;",
    "A ***rövid vegyes mobilitás*** időtartama 5-30 nap, és ki kell egészülnie egy olyan **kötelező virtuális komponenssel**, amely lehetővé teszi az együttműködésen alapuló online tanulást és csapatmunkát – ösztöndíj azonban csak a fizikai mobilitási napokra jár.",
    "A Kiss Elemér Szakkollégium 2010. novemberében alakult a Sapientia Erdélyi Magyar Tudományegyetem Marosvásárhelyi Karán a MITIS Egyesület keretében.",
    "**Senior ösztöndíj** elnyerésére pályázatot nyújthatnak be az Akadémiának az Alapszabály 12. § (3) bekezdése szerinti Kárpát-medencei külső tagjai, valamint az Alapszabály 23. § (1) bekezdése szerinti Kárpát-medencei köztestületi külső tagok.",
    "Dr. Kelemen András egyetemi adjunktus - a kutatócsoport vezetője",
    "Fontosabb kutatási témáink: klaszterező és részlegesen felügyelt klaszterező algoritmusok, evolúciós algoritmusok, digitális jel- és képfeldolgozás, beszédtechnológia: folyamatos beszédfelismerés, beszédszintézis, nyelvi erőforrások fejlesztése, alkalmazások nagy adatbázisokkal, élettani rendszerek modellezése és szimulációja, protein együtthatási hálózatainak tanulmányozása, virtualizációs technikák.",
    """Bartha Zsolt, tanársegéd
       Vekov Géza Károly, tanársegéd
       Zsombori Gabriella, tanársegéd
       Garda-Mátyás Edit, tanársegéd""",
    "https://ms.sapientia.ro/content/docs/MS/TST-20230616T072159Z-001.zip",
    "https://ms.sapientia.ro/hu/oktatas/oktatoi-versenyvizsgak",
    """**Beiratkozáshoz szükséges iratok:**
    * **Beiratkozási kérvény** (alapképzés (https://ms.sapientia.ro/content/docs/MS/Zarovizsga/2025/cerere_alap_2025.docx) -, mesterképzés (https://ms.sapientia.ro/content/docs/MS/Zarovizsga/2025/cerere_mesteri_2025.docx) formanyomtatványa), amelyet a témavezető láttamoz;
    * Szakdolgozat/diplomaterv/disszertáció, elektronikusan PDF formátumban;
    * A témavezető/elővédési bizottság **referátuma**, amelynek tartalmaznia kell a dolgozat tartalmi értékelését és az ajánlott jegyet;
    * A *Turnitin*rendszerből generált **report**;
    * **2 db papír alapú**, útlevél típusú (3x4) **színes fénykép;**
    * A **szerző nyilatkozata** a dolgozat eredetiségéről;
    A dékáni hivatal az alábbi dokumentumokkal egészíti ki a végzettek beiratkozási iratcsomóját:
    * A **témavezető** **nyilatkozata** a vezetett dolgozat eredetiségére vonatkozóan;
    * A születési bizonyítvány **eredeti példánya** és a beiratkozás során **hitelesített másolata.**
    Az eredeti példányt a másolat helyszínen történő hitelesítése nyomán a jelentkező visszakapja.
    * **Érettségi oklevél eredetije**, valamint a **melléklet eredetije (törzskönyvi kivonat)** és a beiratkozás során hitelesített másolata, valamint esetenként a honosítási okirat;
    * **Egyetemi oklevél eredetije és a beiratkozás során hitelesített másolata** (mesteri szakok végzettjei esetében), valamint esetenként a **honosítási okirat**;
    * **Idegennyelvvizsga-bizonyítvány másolata.**
    Más nyelvvizsgaközpontok által kibocsátott bizonyítványok esetében a LinguaSap Központ általi elismerés is szükséges.""",
    "A nyelvvizsga két, egy írásbeli és egy szóbeli részből áll.",
    "A záróvizsga időpontja: 2025. július 7., 129-es terem",
    "A bentlakásban 3 szobatípus van: apartman, garzon, tetőtéri szoba."
]

ground_truths_vector_by_search_60 =[
    "https://sapientia.ro/hu/nemzetkozi-kapcsolatok/erasmus/hallgatok/erasmus-hallgatoi-palyazati-felhivas-szakmai-gyakorlat-mobilitas-2025-nyara-es-tanulmanyi-mobilitas-202526-os-tanev",
    "Hasznos információk https://ms.sapientia.ro/hu/nemzetkozi-kapcsolatok/erasmus/hasznos-informaciok",
    "Makovecz Hallgatói Ösztöndíjprogram teljes szemeszteres részképzéseket, valamint részképzős tanulmányutakat kínál a hallgatók számára más, határon túli magyar nyelvű felsőoktatási intézményekben.",
    "Dokumentumok, formanyomtatványok https://sapientia.ro/hu/nemzetkozi-kapcsolatok/makovecz-program/dokumentumok-formanyomtatvanyok",
    "Mechatronika https://ms.sapientia.ro/content/2011-2021/nemzetkozi-hallgatok/curriculum-mech.pdf",
    "Páll Zita",
    "Az MTA Domus ösztöndíjprogramja senior és junior ösztöndíjakkal kívánja támogatni a külföldi kutatók szakmai munkásságát, magyarországi tevékenységét, segítve bekapcsolódásukat a magyarországi tudományos életbe, akadémiai és egyetemi kutatásokba, magyarországi szakmai partnerek, témavezetők közreműködésével.",
    """dr. Kenéz Lajos- a kutatócsoport vezetője
	  dr.ing. Kutasi Dénes Nimród""",
    """Szakterületek:
        -teljesítményelektronika, rezonáns áramirányítók, indukciós hevítés
        -magnetronos porlasztás
        -elektronsugaras hegesztés
        -villamos hajtások vektoriális szabályozása
        -rendszerek modellezése és optimális szabályozása""",
    """Faculty of Information Technology, Pannon University, Veszprém, Magyarország
       SZTAKI - INSTITUTE FOR COMPUTER SCIENCE AND CONTROL, Budapest, Magyarország""",
    """Főbb tantárgyak:
        - anyagtudományok
        - számítógépes tervezés
        - ipari elektronika
        - gép-, szerszám- és készüléktervezés
        - ipari robotok
        - műanyagtechnológiák és fröccsentő szerszámok.
        - CNC-programozás és gyártás
        - gyártáselmélet""",
    "Kertészmérnöki Tanszékhez",
    "Alkalmazott Fizika és Gépészeti Tudományok Kutatóközpont",
    "Kommunikáció és közkapcsolatok szak",
    """Dr. Benő Attila
       Dr. Zsemlyei Borbála""",
    "Kutatási terv https://ms.sapientia.ro/content/docs/MS/Kutatokozpontok/ACFA/ACFA_Plan_de_cercetare.pdf",
    """Dr. Szász Róbert, docens
        Dr. Kátai Zoltán, docens
        Dr. Pál László, docens
        Dr. Kupán Pál, docens
        Dr. Antal Margit, docens""",
    "https://ms.sapientia.ro/hu/oktatas/tantargyi-leirasok",
    "https://ms.sapientia.ro/content/docs/MS/Tantervek/MBMech_2024_Magyar.pdf",
    "https://ms.sapientia.ro/content/docs/MS/Tantervek/MMNOV_2023_SZL%20m%C3%A1rc.27.pdf",
    "https://ms.sapientia.ro/content/docs/MS/TST-20230616T072159Z-001.zip",
    "https://ms.sapientia.ro/hu/oktatas/orarend",
    "András Csaba",
    """dr. Juhász Imre
       dr. Nagy Bernadett
       dr. Kis Anna-Bernadett""",
    "0744-339-765",
    """Rendelési időpontok:
        hétfő, szerda: 9-14 óra
        kedd, csütörtök: 14-18 óra
        péntek: 9-13 óra""",
    """Az oklevél átvételéhez szükséges:
        1. előzetes emailes időpont foglalás (a diploma@sapientia.ro e-mail-címen)
        2. személyazonossági igazolvány
        3. születési bizonyítvány eredetije és egyszerű másolata (ha hiányzik a dossziéból – erről az időpont egyeztetéskor értesítjük a végzettet)
        4. névváltoztatás esetén az ezt igazoló dokumentum (házasságlevél vagy egyéb okirat) eredetije és egyszerű másolata
        5. 2 db. aktuális, színes, 3x4 cm-es fénykép (ha hiányzik a dossziéból, vagy nem megfelelő – erről az időpont egyeztetéskor értesítjük a végzettet)
        6. Alumni kérdőív kitöltve (a kérdőív végén kapott kódot küldjék el az időpont egyeztetéskor e-mailben; posztgraduális tanárképző esetén: Alumni kérdőív - Tanárképző)""",
    """1. a portfólió bemutatása;
       2. kérdések az értékelők és a bizottság részéről.""",
    """A záróvizsga menete:
        1. a portfólió leadása;
        2. a benyújtott portfólió nyilvános védése.""",
    "https://ms.sapientia.ro/data/Szakdolgozat%20VMT%20Szamitastechnika.doc",
    "https://ms.sapientia.ro/content/2011-2021/Szakdolgozat%20MIT%20Informatika.pdf",
    "https://drive.google.com/file/d/1NHt8QHPZ2-5U44-RYeKB76ylNOkq3zr0/view?usp=sharing",
    "https://ms.sapientia.ro/content/docs/MS/Zarovizsga/2025/03%20Szakdolgozat-keszitesi%20utmutato%202025.pdf",
    """ÍRÁSBELI (24 pont)
        Hallott szövegértés (6 pont)
        Olvasott szövegértés (6 pont)
        Nyelvtan és nyelvhelyességi gyakorlat (6 pont)
        Fogalmazás (6 pont)""",
    "A tanszékeken kell iratkozni.",
    "2025. július 8.",
    "231-es terem",
    """A disszertáció vizsga a mesteri disszertáció bizottság előtt történő bemutatásából és védéséből áll.
        A mesteri disszertáció védése nyilvános, a bizottság és a vizsgázó ugyanazon helyen való egyidejű jelenlétében történik.""",
    "https://ms.sapientia.ro/hu/hallgatoknak/zarovizsga/mesterkepzes-utemezes-20242025",
    """Középiskolai szakasz:
        1.1. Óralátogatási lap
        1.2. Lecketerv a megtartott órákról
        Ajánlott: Tantárgy féléves/1-2 tematikus terve (planificare pe unități de învățare); lecketerv a hospitált órákról
        1.3. Jegyzőkönyv a vizsgatanításról (tanár végzi)
        1.4. Pszichopedagógiai jellemzés: középiskolás-korú diákról""",
    "50",
    "230-as terem",
    "213, 217, 230-as termek",
    "https://ms.sapientia.ro/content/docs/MS/Zarovizsga/2024/K%C3%B6zeg%C3%A9szs%C3%A9g%C3%BCgy_%C3%81llamvizsga_tematika_2023_2024.pdf",
    "A záróvizsga végső jegye: az írásbeli vizsgán szerzett jegy és a szakdolgozat védésére kapott jegy számtani középarányosa.",
    """Kötelező tantárgyak:
        1. Neveléspszichológia (4 óra, 5 kredit)
        2. Pedagógia I.: A pedagógia alapjai + Tantervelmélet (4 óra, 5 kredit)
        3. Pedagógia II.: Oktatáselmélet + Értékeléselmélet (4 óra, 5 kredit)
        4. Szakmódszertan (4 óra, 5 kredit); (dupla szakosok esetében 2x5 kredit)
        5. Számítógéppel támogatott oktatás (2 óra, 2 kredit)
        6. Osztályvezetés (2 óra, 3 kredit)
        7. Pedagógiai gyakorlat I, II (5 kredit)""",
    "Departamentul de Specialitate cu Profil Psihopedagogic – DSPP",
    "200 lej/fő",
    """Szükséges iratok:
    1. a szülők részéről az adóhivatal által kibocsátott igazolás arra vonatkozóan, hogy van-e vagy nincs megadózandó jövedelmük (Adeverință de venit).
    2. a szülők részéről a Polgármesteri Hivatal által kiadott bizonyítvány a tulajdonban lévő földterületről vagy ennek hiányáról.
    Elvált szülők esetén a bírósági végzés másolata, illetve annak a szülőnek az 1., 2. pontban megjelölt iratai, akinek a gyermeket nevelésre odaítélték.
    3. testvérekkel (ha vannak) kapcsolatos iratok: a 18 éven aluli testvérek esetén óvodai vagy iskolai igazolvány, illetve születési bizonyítvány másolata, ha nem óvodás, és nem iskolás.
    A 18 éven felüli testvérek esetén főiskolai vagy egyetemi igazolvány, illetve ha igazoltan munkaképtelen, rokkantsági nyugdíj igazolása.
    4. betegség esetén a törvényben előírt, családorvos/szakorvos által kiállított, 3 hónaposnál nem régebbi bizonyítvány
    5. félárvák esetében az elhunyt szülő halotti bizonyítványának másolata
    6. árvák esetében a szülők halotti bizonyítványának másolata
    7. gyermekotthonban nevelkedők esetében azon intézet által kiállított bizonyítvány, ahol utoljára tartózkodott
    9. személyi igazolvány másolata
    10. születési bizonyítvány másolata
    11. orvosi igazolás a háziorvostól, ami tartalmazza, hogy lakhat bentlakásban (hiánya kizáró jellegű)
    12. erkölcsi bizonyítvány („priusz”, románul „cazier”, hiánya kizáró jellegű)
    13. Felvételi díj befizetése 200 lej,
    Beiratkozási díj a bentlakásba 200 lej.""",
    "https://tdk.sapientia.ro/",
    "tanévkezdés - 1 hét",
    "napi 0,5% késedelmi kamat, ösztöndíjletiltás",
    "https://ms.sapientia.ro/content/docs/MS/Felveteli/2022/SZF_Tematika_2022_2023_HU.pdf / RO https://ms.sapientia.ro/content/docs/MS/Tematica_2022_2023_RO.pdf",
    """Elhelyezkedési lehetőségek:
            programtervező
            szoftver-projektmenedzser
            információtechnológiai szakértő, tanácsadó
            informatikatanár
            kutató""",
    "3 év",
    "6",
    "Dr. Domokos József",
    "dr. Antal Margit",
    "https://ms.sapientia.ro/hu/a-karrol/karrieriroda/allasajanlatok-es-szakmai-gyakorlat/internship-ajanlatok",
    """Időszakos rendezvényeink:
        Karácsonyi ajándékozás
        Sapi Slam
        Film maraton
        Klasszikus és néptánc oktatás
        Nyílt napok
        Quiz Night
        Egészségnap"""


    ]

@app.route("/")
def init_load():
    global loading_started
    with loading_lock:
        if not loading_started:
            loading_started = True
            # Futtasd háttérszálban, hogy ne blokkolja a válaszadást
            threading.Thread(target=load_all_vectors_to_list).start()
        if not loading_done:
                return render_template('loading.html')
    return redirect("/chatbot")
@app.route("/status")
def status():
    return jsonify({"done": loading_done})
# index, melyik ground truth-t hasonlítjuk össze az adott kérdésnél
current_gt_index = 0

@app.route('/chatbot', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_total = time.time()
        global current_gt_index

        data = request.get_json()
       
        user_question = data.get("question", "").strip()

        if not user_question:
            return jsonify({"error": "Nincs megadva kérdés"}), 400
        try:
            start_embed = time.time()
            embedding = get_embedding(user_question) #OpenAI API-val átalakítja a szöveget embedding-gé (vektorrá)
            end_embed = time.time()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            return jsonify({"error": "Ismeretlen hiba: " + str(e)}), 500
        try:
            start_sparse_embed = time.time()
            query_sparse_vector = get_sparse_vector_from_query(user_question)
            end_sparse_embed = time.time()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            return jsonify({"error": "Ismeretlen hiba: " + str(e)}), 500
        try:
            start_ctx = time.time()
            # kontextus összeállítása a lekérdezett embedding alapján
            context, top_k_size = get_context_text(embedding,query_sparse_vector)
            end_ctx = time.time()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            return jsonify({"error": "Ismeretlen hiba: " + str(e)}), 500
        
        try:
            start_llm = time.time()
            resp = get_llm_response(context, user_question)
            end_llm = time.time()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            return jsonify({"error": "Ismeretlen hiba: " + str(e)}), 500

        end_total = time.time()

        if current_gt_index >= len(ground_truths_vector_by_search_60):
            return jsonify({"error": "Nincs több ground truth válasz teszteléshez."}), 400
        ground_truth = ground_truths_vector_by_search_60[current_gt_index]

        # szematikus hasonlosot mérek BERTScore-dal
        P, R, F1 = score([resp], [ground_truth], lang="hu")
        bertscore_f1 = F1.mean().item()

        # növelem a ground truth indexet a következő kérdéshez
        current_gt_index += 1

        print(f"\n--- Időmérések (másodpercben) ---")
        t_embed = end_embed - start_embed
        print(f"Embedding generálás:     {t_embed:.3f}s")
        t_sparse_embed = end_sparse_embed - start_sparse_embed
        print(f"Sparse Embedding generálás: {t_sparse_embed:3f}s")
        t_ctx = end_ctx - start_ctx
        print(f"Kontextus összeállítás:  {t_ctx:.3f}s")
        t_llm = end_llm - start_llm
        print(f"Gemini válasz:           {t_llm:.3f}s")
        t_total = end_total - start_total
        print(f"TELJES kérés feldolgozás: {t_total:.3f}s")
        print(f"Szemantikus hasonlóság méréke (bertscore_f1):{bertscore_f1}")
        print(f"top_k száma: {top_k_size}")

        #proba_valasz,p_context  = curent_context_from_context(embedding,user_question)
        #save_timings_to_excel("../vectorSearchTesting/timings_60_questionScore0_90.xlsx", user_question, t_embed,t_sparse_embed, t_ctx, t_llm, t_total,bertscore_f1)
        #save_timings_to_excel("../vectorSearchTesting/timings_60_question_score0_86.xlsx", user_question, t_embed,t_sparse_embed, t_ctx, t_llm, t_total,bertscore_f1)
        save_timings_to_excel("../hybrid_searchTesting/timings_60_question_RRF.xlsx", user_question, t_embed,t_sparse_embed, t_ctx, t_llm, t_total,bertscore_f1,top_k_size)
        #save_timings_to_excel("../hybrid_searchTesting/timings_20_question_DBSF.xlsx", user_question, t_embed,t_sparse_embed, t_ctx, t_llm, t_total,bertscore_f1,top_k_size)
        
        return jsonify({"answer": resp})
        #return jsonify({"answer": resp, "LLM_time": t_llm, "beckend_time":t_total,"bertscore_f1":bertscore_f1})
    

    return render_template('index.html')

if __name__ == '__main__':
    #load_all_vectors_to_list()
    #app.run(debug=True)
    app.run()
