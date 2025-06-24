import os
import json
import time
import requests
import psutil
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def alap_mester_kepzes_informaciok(url):
    response = requests.get(url)
    if response.status_code != 200:
        return {"error": f"Nem sikerült letölteni az oldalt: {url}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    page_title = soup.find('div', id='pagetitle').get_text(strip=True)

    szakok_info = []
    szak_links = soup.find_all('a', class_='szak')
    for link in szak_links:
        link_url = link.get('href')
        img_tag = link.find('img')
        img_url = img_tag.get('src') if img_tag else None
        kep_url = urljoin('https://ms.sapientia.ro/', img_url) if img_url else None

        szak_name_tag = link.find('span')
        szak_name = szak_name_tag.get_text(strip=True) if szak_name_tag else 'Ismeretlen szak'

        szakok_info.append({
            'Szak': szak_name,
            'Url': urljoin('https://ms.sapientia.ro/', link_url),
            'Kép': kep_url,
            'Képzés': page_title,
        })

    return szakok_info  # Csak a listát adja vissza

# URL-ek listában
url_list = [
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes",
    "https://ms.sapientia.ro/hu/felveteli/mesterkepzes"
]

# Fájl neve
file_name = 'json/sapientia_kepzesi.json'

# Ha a fájl nem létezik, csak akkor írjuk bele az adatokat
if not os.path.exists(file_name):
    osszes_kepzes = []
    # Feldolgozás kezdete és memória előtte
    start_time = time.time()
    process = psutil.Process()
    memory_before = process.memory_info().rss
    processed_items = 0  # Kezdeti itemek száma
    for url in url_list:
        kepzesek = alap_mester_kepzes_informaciok(url)
        osszes_kepzes.extend(kepzesek)  # Listák összefűzése
        processed_items += 1  # Feldolgozott elemek számának növelése
    # Feldolgozás vége
    end_time = time.time()
    processing_time = end_time - start_time

    # Memóriahasználat és teljes adatméret
    memory_after = process.memory_info().rss
    memory_usage_mb = (memory_after - memory_before) / 1024 / 1024
    data_throughput = processed_items / processing_time

    # Kiírás
    print(f"\nFelvételi ütemezés adatai elmentve a '{file_name}' fájlba.")
    print("\n--- Rendszermutatók ---")
    print(f"Feldolgozott összes item: {processed_items}")
    print(f"Feldolgozási idő: {processing_time:.2f}s")
    print(f"Adatgyűjtési sebesség: {data_throughput:.2f} elem/s")
    print(f"Memóriahasználat: {memory_usage_mb:.2f} MB")

    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(osszes_kepzes, f, ensure_ascii=False, indent=4)
    
    

    print(f"A képzések adatai elmentve a '{file_name}' fájlba.")
else:
    print(f"A '{file_name}' már létezik, nem történt írás.")