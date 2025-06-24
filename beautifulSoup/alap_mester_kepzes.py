import os
import json
import time
import psutil
import requests
from bs4 import BeautifulSoup
import json

def kepzes_adatai_egyben(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data = {}
    helyek = []
    koltsegek = {}
    felveteli_osszetevok = []

    # Alap linkek
    original_link = "https://ms.sapientia.ro/"

    # Szak neve a képből
    image_div = soup.find("div", class_="insimgbg")
    data["szak"] = image_div.get("title", "") if image_div else ""

    # Szakinfo adatok
    for f in soup.find_all("div", class_="szakrinfo"):
        title = f.find("span", class_="color_blue")
        if title:
            title_text = title.get_text(strip=True)
            if title_text == "Helyek száma":
                for place in f.find_all("div", class_="f"):
                    count = place.find("span", class_="ba").get_text(strip=True)
                    place_type = place.find("span", class_="bc").get_text(strip=True)
                    helyek.append({"szam": count, "tipus": place_type})
            elif title_text == "Költség-hozzájárulás összege":
                koltsegek["hozzajarulas"] = f.find("div", class_="f").get_text(strip=True)
            if title_text == "Teljes tandíj összege":
                    koltsegek["teljes_tandíj_összege"] = f.find("div", class_="f").get_text(strip=True)
            elif title_text == "Differenciált költséghozzájárulás összege":
                    koltsegek["ifferenciált_költséghozzájárulás_összege"] = f.find("div", class_="f").get_text(strip=True)   
            elif title_text == "Képzés időtartama":
                data["ido_tartam"] = f.find("div", class_="f").get_text(strip=True)
            elif title_text == "A felvételi jegy összetétele":
                for item in f.find_all("div", class_="f"):
                    percentage = item.find("span", class_="ba").get_text(strip=True)
                    description = item.find("span", class_="bc").get_text(strip=True)
                    felveteli_osszetevok.append({"szazalek": percentage, "leiras": description})
            elif title_text == "Beiratkozási időszak":
                data["beiratkozas_idoszak"] = f.find("div", class_="f").get_text(strip=True)

    data["helyek"] = helyek
    data["koltsegek"] = koltsegek
    data["felveteli_osszetevok"] = felveteli_osszetevok

    # Szükséges iratok linkje
    szukseges_iratok = soup.find("div", class_="sziratok")
    if szukseges_iratok and szukseges_iratok.find("a"):
        data["szukseges_iratok_url"] = szukseges_iratok.find("a")["href"]

    

    # Lista adatok: Képzési ág, szak, stb.
    ul = soup.find('div', class_='news-descr').find('ul')
    p_elem = soup.find('div', class_='news-descr').find('p')
    if p_elem  and p_elem.find('strong') and p_elem.find('strong').text.strip() == 'Saját, nemzetköziesített mesteri szak':
            data["sajat_nemzetkozi_mesteri"] = p_elem.find('strong').text.strip()
    if ul:
        for item in ul.find_all('li'):
            strong = item.find('strong')
            if strong:
                key = strong.text.strip(':')
                value = item.text.replace(strong.text, '').strip()
                data[key] = value

    # Online iratkozás
    online = soup.find('a', string="https://felveteli.sapientia.ro/")
    if online:
        data["Online iratkozás"] = online['href']

    # ROMÁN NYELVŰ TANTERV
    roman_link = soup.find('a', class_='details', href=True)
    if roman_link:
        data["Roman nyelvu tanterv link"] = original_link + roman_link['href']

    # felveteli tematika
    felveteli_tematika = soup.find_all('a', class_='details', href=True)
    if len(felveteli_tematika) > 1:
        data["Felvételi tematika"] = original_link + felveteli_tematika[1]['href']
    else :
        data["Felvételi tematika"] = "null"
    # "Neked ajánljuk, ha..."
    rec_sec = soup.find('h3', string="Neked ajánljuk, ha...")
    if rec_sec:
        ul = rec_sec.find_next('ul')
        if ul:
            data["Neked ajánljuk, ha..."] = [li.text.strip() for li in ul.find_all('li')]

    # "Főbb tantárgyak"
    subj_sec = soup.find('h3', string="Főbb tantárgyak:")
    if subj_sec:
        ul = subj_sec.find_next('ul')
        if ul:
            data["Főbb tantárgyak"] = [li.text.strip() for li in ul.find_all('li')]

    # "Elhelyezkedési lehetőségek"
    job_sec = soup.find('h3', string="Elhelyezkedési lehetőségek:")
    if job_sec:
        ul = job_sec.find_next('ul')
        if ul:
            data["Elhelyezkedési lehetőségek"] = [li.text.strip() for li in ul.find_all('li')]

    # "Tudod-e, hogy…?"
    trivia_sec = soup.find('h3', string="Tudod-e, hogy…?")
    if trivia_sec:
        ul = trivia_sec.find_next('ul')
        if ul:
            data["Tudod-e, hogy…?"] = [li.text.strip() for li in ul.find_all('li')]

    # "A felvételi jegy összetétele:"
    adm_sec = soup.find('h3', string="A felvételi jegy összetétele:")
    if adm_sec:
        ul = adm_sec.find_next('ul')
        if ul:
            data["Felvételi jegy összetétele (szöveges)"] = [li.text.strip() for li in ul.find_all('li')]

    # Felvételi kedvezmények és megjegyzések
    adv_sec = soup.find('h3', string="Felvételi kedvezmények és megjegyzések")
    if adv_sec:
        ps = adv_sec.find_all_next('p', limit=2)
        text = []
        for p in ps:
            link = p.find('a', href=True)
            if link:
                text.append({'text': p.text.strip(), 'link': original_link + link['href']})
            else:
                text.append(p.text.strip())
        data["Felvételi kedvezmények és megjegyzések"] = text

    # Mi szükséges a felvételi mappához?
    docs_sec = soup.find('h3', string="Mi szükséges a felvételi mappához?")
    if docs_sec:
        p = docs_sec.find_next('p')
        if p:
            link = p.find('a', href=True)
            if link:
                data["Mi szükséges a felvételi mappához?"] = {
                    "text": p.text.strip(),
                    "link": link['href']
                }

    # További információk
    info_sec = soup.find('h3', string="További információk")
    if info_sec:
        ps = info_sec.find_all_next('p', limit=2)
        data["További információk"] = [p.text.strip() for p in ps]

    #return json.dumps(data, ensure_ascii=False, indent=4)
    return data

#Több URL feldolgozása
url_lista = [
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/fordito-es-tolmacs-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/kerteszmernoki-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/tajepiteszet-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/kommunikacio-es-kozkapcsolatok-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/kozegeszsegugyi-szolgaltatasok-es-politikak-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/informatika-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/automatika-es-alkalmazott-informatika-mernok-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/gepeszmernoki-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/infokommunikacios-halozatok-es-rendszerek-tavkozles-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/mechatronika-szak",
    "https://ms.sapientia.ro/hu/felveteli/alapkepzes/szamitastechnika-szak",
    "https://ms.sapientia.ro/hu/felveteli/mesterkepzes/fejlett-mechatronikai-rendszerek-szak",
    "https://ms.sapientia.ro/hu/felveteli/mesterkepzes/novenyorvos-szak",
    "https://ms.sapientia.ro/hu/felveteli/mesterkepzes/szamitogepes-iranyitasi-rendszerek-szak",
    "https://ms.sapientia.ro/hu/felveteli/mesterkepzes/szoftverfejlesztes-szak"
    # ide jöhet több link is
]

osszes_adat = []
# Feldolgozás kezdete és memória előtte
start_time = time.time()
process = psutil.Process()
memory_before = process.memory_info().rss
processed_items = 0  # Kezdeti itemek száma
for url in url_lista:
    try:
        adat = kepzes_adatai_egyben(url)
        osszes_adat.append(adat)
        processed_items += 1
        #print(f"Sikeresen feldolgozva: {url}")
    except Exception as e:
        print(f"Hiba történt a(z) {url} feldolgozásakor: {e}")
# Feldolgozás vége
end_time = time.time()
processing_time = end_time - start_time
# Memóriahasználat és teljes adatméret
memory_after = process.memory_info().rss
memory_usage_mb = (memory_after - memory_before) / 1024 / 1024
data_throughput = processed_items / processing_time

# Kiírás
print("\n--- Rendszermutatók ---")
print(f"Feldolgozott összes item: {processed_items}")
print(f"Feldolgozási idő: {processing_time:.2f}s")
print(f"Adatgyűjtési sebesség: {data_throughput:.2f} elem/s")
print(f"Memóriahasználat: {memory_usage_mb:.2f} MB")
#JSON fájlba írás
with open("json/alap_mester_kepzes.json", "w", encoding="utf-8") as f:
    json.dump(osszes_adat, f, ensure_ascii=False, indent=4)

print("Az adatok mentve lettek a 'json/alap_mester_kepzes.json' fájlba.")
