import os
import json
import time
import requests
import psutil
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def felveteli_utemezes_scrape(url):
    file_name = 'json/felveteli_utemezes.json'
    if os.path.exists(file_name):
        print(f"A fájl már létezik: {file_name}. Semmit sem csinálok.")
        return

    # Feldolgozás kezdete és memória előtte
    start_time = time.time()
    process = psutil.Process()
    memory_before = process.memory_info().rss
    processed_items=0 # Kezdeti itemek száma
    

    # Adatok lekérése
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Nem sikerült letölteni az oldalt: {url}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Képek kigyűjtése
    image_urls = [
        urljoin('https://ms.sapientia.ro/', img['src'])
        for img in soup.find_all('img')
        if img.get('src') and ('FU_A.png' in img['src'] or 'FU_M.png' in img['src'])
    ]

    # Ütemezési információk kigyűjtése
    utemezes_info = []
    p_blocks = soup.select('div.news-descr p')
    for p in p_blocks:
        strong_content = p.find('strong')
        if strong_content:
            cim = strong_content.get_text(strip=True)
            date_span = strong_content.find('span')
            datum = date_span.get_text(strip=True) if date_span else ""
            teljes_szoveg = f"{datum}" if datum else cim
            utemezes_info.append(teljes_szoveg)

    # Cím lekérése
    header = soup.select_one('div.descr-tit.color_blue')
    header_text = header.get_text(strip=True) if header else None

    # Eredmény összeállítása
    result = {
        "cím": header_text,
        "url": url,
        "képek": image_urls,
    }

    keys = [
        "Online iratkozás alapképzés",
        "Felvételi vizsga alapképzés",
        "Online iratkozás mesterképzés",
        "Felvételi vizsga mesterképzés"
    ]
    for idx, item in enumerate(utemezes_info):
        if idx < len(keys):
            result[keys[idx]] = item
    processed_items += 1  # Minden új eredménnyel növeljük az itemek számát


    # Feldolgozás vége
    end_time = time.time()
    processing_time = end_time - start_time

    # Memóriahasználat és teljes adatméret
    memory_after = process.memory_info().rss
    memory_usage_mb = (memory_after - memory_before) / 1024 / 1024
    data_throughput = processed_items / processing_time

    # JSON mentés
    os.makedirs('json', exist_ok=True)
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # Kiírás
    print(f"\nFelvételi ütemezés adatai elmentve a '{file_name}' fájlba.")
    print("\n--- Rendszermutatók ---")
    print(f"Feldolgozott osszes item: {processed_items}")
    print(f"Feldolgozási idő: {processing_time:.2f}s")
    print(f"Adatgyűjtési sebesség: {data_throughput:.2f} elem/s")
    print(f"Memóriahasználat: {memory_usage_mb:.2f} MB")

# Használat
url = 'https://ms.sapientia.ro/hu/felveteli/felveteli-utemezes'
felveteli_utemezes_scrape(url)
