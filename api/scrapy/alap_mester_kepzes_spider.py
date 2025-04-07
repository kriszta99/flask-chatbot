import scrapy
import os
import json
import time  #a time modul felhasznált idő mérésére
import psutil  # memória méréshez
import logging # ezzel logolni fogjuk a hibákat



class AlapMesterKepzesSpider(scrapy.Spider):
    name = "alap_mester_kepzes_spider"
    start_urls = [
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
    ]
    if os.path.exists('json/alap_mester_kepzes_spider.json'):
        print(f"A fájl már létezik: {'json/alap_mester_kepzes_spider.json'}. Semmit sem csinálok.")
        exit()

    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'json/alap_mester_kepzes_spider.json',
        'FEED_EXPORT_ENCODING': 'utf-8',
        'CLOSESPIDER_ITEMCOUNT': len(start_urls),  # Várjuk, hogy 2 item/url

    }
    def start_requests(self):
        # Kezdeti memóriahasználat mérés
        self.process = psutil.Process(os.getpid())
        self.memory_before = self.process.memory_info().rss  # Memóriahasználat az elején 
        # beállítjuk a kezdő időpontot
        self.start_time = time.time()
        self.processed_items = 0  # hány itemet dolgoztunk fel
        self.start_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB-ban


        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        self.processed_items += 1  # Növeljük a feldolgozott elemek számát
        data = {}
        helyek = []
        koltsegek = {}
        felveteli_osszetevok = []
        original_link = "https://ms.sapientia.ro/"

        image_div = response.css("div.insimgbg")
        try:
            data["szak"] = image_div.attrib.get("title", "") if image_div else ""
        except Exception as e:
            logging.error(f"Hiba történt a 'szak' adat kinyerésekor: {e}")
            data["szak"] = ""

        for f in response.css("div.szakrinfo"):
            try:
                title = f.css("span.color_blue::text").get()
                if not title:
                    continue
                title = title.strip()
                #Helyek szama
                if title == "Helyek száma":
                    for place in f.css("div.f"):
                        count = place.css("span.ba::text").get(default="").strip()
                        place_type = place.css("span.bc::text").get(default="").strip()
                        helyek.append({"szam": count, "tipus": place_type})
                #Költség-hozzájárulás összege
                elif title == "Költség-hozzájárulás összege":
                    ertek = f.css("span.ba::text").get(default="").strip()
                    egyseg = f.css("span.bc::text").get(default="").strip()
                    koltsegek["költség_hozzájárulás_összege"] = f"{ertek} {egyseg}"
                #Teljes tandíj összege    
                elif title == "Teljes tandíj összege":
                    ertek = f.css("span.ba::text").get(default="").strip()
                    egyseg = f.css("span.bc::text").get(default="").strip()
                    koltsegek["Teljes_tandíj_összege"] = f"{ertek} {egyseg}"
                #Differenciált költség-hozzájárulás összege
                elif title == "Differenciált költség-hozzájárulás összege":
                    ertek = f.css("span.ba::text").get(default="").strip()
                    egyseg = f.css("span.bc::text").get(default="").strip()
                    koltsegek["Differenciált_költség_hozzájárulás_összege"] = f"{ertek} {egyseg}"
                #Képzés időtartama
                elif title == "Képzés időtartama":
                    duration_number = f.css("span.ba::text").get(default="").strip()
                    duration_unit = f.css("span.bc::text").get(default="").strip()
                    data["Képzés_időtartama"] = f"{duration_number} {duration_unit}".strip()
                #A felvételi jegy összetétele
                elif title == "A felvételi jegy összetétele":
                    for item in f.css("div.f"):
                        percentage = item.css("span.ba::text").get(default="").strip()
                        description = item.css("span.bc::text").get(default="").strip()
                        felveteli_osszetevok.append({"szazalek": percentage, "leiras": description})
                #Beiratkozási időszak
                elif title == "Beiratkozási időszak":
                    data["Beiratkozási_időszak"] = f.css("span.ba::text").get(default="").strip()
            except Exception as e:
                logging.error(f"Hiba történt a {title} adatainak feldolgozása közben: {e}")


        data["helyek"] = helyek
        data["költségek"] = koltsegek
        data["felvetéli_összetevök"] = felveteli_osszetevok
        try:     
            szukseges_iratok = response.css("div.sziratok a::attr(href)").get()
            if szukseges_iratok:
                data["szükseges_iratok_url"] = szukseges_iratok
        except Exception as e:
            logging.error(f"Hiba történt a szükséges iratok linkjének kinyerése közben: {e}")

        try:
            ul = response.css("div.news-descr ul")
            p_elem = response.css("div.news-descr > p")
            if p_elem.css("strong::text").get() == "Saját, nemzetköziesített mesteri szak":
                data["sajat_nemzetközi_mesteri"] = p_elem.css("strong::text").get()
            for item in ul.css("li"):
                key = item.css("strong::text").get(default="").strip(":")
                value = item.css("::text").getall()
                value = ''.join(value).replace(key, '').strip()
                data[key] = value
        except Exception as e:
            logging.error(f"Hiba történt a lista adatok kinyerése közben: {e}")

        try:
            online = response.css("a[href='https://felveteli.sapientia.ro/']")
            if online:
                data["Online iratkozás"] = online.attrib['href']
        except Exception as e:
            logging.error(f"Hiba történt az online iratkozás link kinyerése közben: {e}")
   

            # Roman nyelvű tanterv link kinyerése
        try:
            roman_link = response.css("a.details::attr(href)").get()
            if roman_link:
                data["Roman nyelvű tanterv link"] = original_link + roman_link
        except Exception as e:
            logging.error(f"Hiba történt a roman nyelvű tanterv link kinyerése közben: {e}")

        # Tematika linkek kinyerése
        try:
            tematika_links = response.css("a.details::attr(href)").getall()
            if len(tematika_links) > 1:
                data["Felvételi tematika"] = original_link + tematika_links[1]
            else:
                data["Felvételi tematika"] = "null"
        except Exception as e:
            logging.error(f"Hiba történt a tematika linkek feldolgozása közben: {e}")

        # Egyéb szekciók kinyerése
        try:
            for section, label in [("Neked ajánljuk, ha...", "Neked ajánljuk, ha..."),
                                ("Főbb tantárgyak:", "Főbb tantárgyak"),
                                ("Elhelyezkedési lehetőségek:", "Elhelyezkedési lehetőségek"),
                                ("Tudod-e, hogy…?", "Tudod-e, hogy…?"),
                                ("A felvételi jegy összetétele:", "Felvételi jegy összetétele (szöveges)")]:
                ul = response.xpath(f"//h3[text()='{section}']/following-sibling::ul[1]/li/text()").getall()
                if ul:
                    data[label] = [item.strip() for item in ul]
        except Exception as e:
            logging.error(f"Hiba történt a szekciók adatainak kinyerése közben: {e}")

        # Felvételi kedvezmények és megjegyzések kinyerése
        try:
            adv_section = response.xpath("//h3[text()='Felvételi kedvezmények és megjegyzések']")
            if adv_section:
                ps = adv_section.xpath("following-sibling::p")[:2]
                adv_texts = []
                for p in ps:
                    link = p.css("a::attr(href)").get()
                    if link:
                        adv_texts.append({"text": p.css("::text").get(default="").strip(), "link": original_link + link})
                    else:
                        adv_texts.append(p.css("::text").get(default="").strip())
                data["Felvételi kedvezmények és megjegyzések"] = adv_texts
        except Exception as e:
            logging.error(f"Hiba történt a felvételi kedvezmények és megjegyzések kinyerése közben: {e}")

        # Felvételi mappa szükséges iratok kinyerése
        try:
            docs_sec = response.xpath("//h3[text()='Mi szükséges a felvételi mappához?']/following-sibling::p[1]")
            if docs_sec:
                link = docs_sec.css("a::attr(href)").get()
                if link:
                    data["Mi szükséges a felvételi mappához?"] = {
                        "text": docs_sec.css("::text").get(default="").strip(),
                        "link": link
                    }
        except Exception as e:
            logging.error(f"Hiba történt a felvételi mappa szükséges iratok kinyerése közben: {e}")

        # További információk kinyerése
        try:
            info_sec = response.xpath("//h3[text()='További információk']/following-sibling::p")[:2]
            if info_sec:
                data["További információk"] = [p.css("::text").get(default="").strip() for p in info_sec]
        except Exception as e:
            logging.error(f"Hiba történt a további információk kinyerése közben: {e}")

        yield data
    def closed(self, reason):
        # Miután az összes URL feldolgozásra került, itt történik az összegzés
        end_time = time.time()
        processing_time = end_time - self.start_time  # teljes futás idő
        data_throughput = self.processed_items / processing_time  # adatgyűjtési sebesség (items per second)

        # Feldolgozási idő és sebesség kiírása egyszer
        print(f"Feldolgozott osszes item: {self.processed_items}")
        print(f"Feldolgozási idő: {processing_time:.2f}s")
        print(f"Adatgyűjtés sebessége: {data_throughput:.2f} elem/s")

        # Memóriahasználat mérés
        memory_after = self.process.memory_info().rss  # Memóriahasználat a végén
        memory_usage_mb = (memory_after - self.memory_before) / 1024 / 1024  # MB-ban
        print(f"\n Memóriahasználat: {memory_usage_mb:.2f} MB\n")
       