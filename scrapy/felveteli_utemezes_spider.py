import scrapy
import os
import json
import time  #a time modul felhasznált idő mérésére
import psutil  # memória méréshez
import logging # ezzel logolni fogjuk a hibákat



class FelveteliUtemezesSpider(scrapy.Spider):
    name = "felveteli_utemezes_spider"
    start_urls = [
        'https://ms.sapientia.ro/hu/felveteli/felveteli-utemezes'
    ]

    if os.path.exists('json/felveteli_utemezes_spider.json'):
        print(f"A fájl már létezik: {'json/felveteli_utemezes_spider.json'}. Semmit sem csinal.")
        exit()

    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'json/felveteli_utemezes_spider.json',
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def start_requests(self):    
        # Kezdeti memóriahasználat mérés
        self.process = psutil.Process(os.getpid())
        self.memory_before = self.process.memory_info().rss  # Memóriahasználat az elején    
        # bețlláitjuk a kezdő időpontot
        self.start_time = time.time()
        self.processed_items = 0  # Hány itemet dolgoztunk fel
        yield scrapy.Request(url=self.start_urls[0], callback=self.parse)

    def parse(self, response):
        #try-except blokk → ha bármi elromlik, nem omlik össze az egész
        try:
            self.processed_items +=1
            # Oldal feldolgozása után mérjük az időt
            utemezes_div = response.css('div#nright')

            # Képek kinyerése
            image_urls = utemezes_div.css('img::attr(src)').getall()
            full_image_urls = [response.urljoin(img) for img in image_urls]




            # Ütemezés kinyerése
            utemezes_info = []
            p_blocks = utemezes_div.css('div.news-descr p')

            for p in p_blocks:
                #try-except minden p elem feldolgozásánál → ha egy bekezdés hibás, csak azt hagyjuk ki
                try:
                    # A teljes HTML tartalom kinyerése a <strong> elemből
                    #strong_content = p.css('strong').get()
                    strong_content = p.css('strong::text').get()
                    if strong_content:
                        # Az adatainkat kinyerjük a <strong> tag-ból
                        cim = strong_content.split('<span')[0].replace('<strong>', '').replace('</strong>', '').strip()

                        # A teljes dátum kinyerése a span elemből
                        date_span = p.css('strong span::text').getall()
                        datum = ' '.join(date_span).strip() if date_span else ""

                        
                        # A szöveg összeállítása
                        teljes_szoveg = f"{datum}" if datum else cim
                        utemezes_info.append(teljes_szoveg)

                except Exception as e:
                        logging.error(f"Hiba egy bekezdés feldolgozásakor: {e}")


            # Felvételi ütemezés címének kinyerése
            header = response.css('div.descr-tit.color_blue::text').get()



            # Végigmegyünk az utemezes_info listán és mindegyik elemet felhasználjuk
            result = {
                "cím": header.strip() if header else None,
                "url": response.url,
                "képek": full_image_urls,
            }

            # Iterálunk az utemezes_info listán és hozzárendeljük az értékeket
            for idx, item in enumerate(utemezes_info):
                # A kulcsok listája, ami alapján elmentjük az adatokat
                keys = [
                    "Online iratkozás alapképzés",
                    "Felvételi vizsga alapképzés",
                    "Online iratkozás mesterképzés",
                    "Felvételi vizsga mesterképzés"
                ]
                if idx < len(keys):
                    result[keys[idx]] = item
            

            yield result
            print("\n--- Rendszermutatók ---")
            print(f"Feldolgozott osszes item: {self.processed_items}")

            
            end_time = time.time()
            #Feldolgozási idő
            processing_time = end_time - self.start_time  # teljes futás idő
            data_throughput = self.processed_items / processing_time  # adatgyűjtési sebesség (items per second)
            # Memóriahasználat mérés
            memory_after = self.process.memory_info().rss  # Memóriahasználat a végén
            memory_usage_mb = (memory_after - self.memory_before) / 1024 / 1024  # MB-ban
            print(f"Feldolgozási idő: {processing_time:.2f}s")
            print(f"Adatgyűjtés sebessége: {data_throughput:.2f} elem/s")

            print(f"\n Memóriahasználat: {memory_usage_mb:.2f} MB\n")
        except Exception as e:
            self.logger.error(f"Hiba történt a feldolgozás során: {e}")
