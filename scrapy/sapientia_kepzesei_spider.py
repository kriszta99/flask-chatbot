import scrapy
import os
import json
import time  #a time modul felhasznált idő mérésére
import psutil  # memória méréshez
import logging # ezzel logolni fogjuk a hibákat


class SapientiaKepzeseiSpider(scrapy.Spider):
    name = "sapientia_kepzesei_spider"
    
    start_urls = [
        'https://ms.sapientia.ro/hu/felveteli/alapkepzes',
        'https://ms.sapientia.ro/hu/felveteli/mesterkepzes',
    ]

    if os.path.exists('json/sapientia_kepzesei_spider.json'):  # Ellenőrizzük, hogy létezik-e már a TXT fájl
        print(f"A fájl már létezik: {'json/sapientia_kepzesei_spider.json'}. Semmit sem csinál.")
        exit()  # Ha létezik, nem csinál semmit

    custom_settings = {
        'FEED_FORMAT': 'json',  
        'FEED_URI': 'json/sapientia_kepzesei_spider.json',
        'FEED_EXPORT_ENCODING': 'utf-8',  # Speciálisan kezeli az ékezetes karaktereket
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
        # Oldal címének kinyerése
        page_title = response.css('div#pagetitle::text').get()
        if page_title:
            page_title = page_title.strip()

        # Szakok információinak kinyerése
        for link in response.css('a.szak'):
            try:
                szak_name = link.css('span::text').get()
                if szak_name:
                    szak_name = szak_name.strip()
                
                link_url = link.attrib.get('href', '')
                img_url = link.css('img::attr(src)').get()

                # Szakok adatainak átadása CSV-be
                yield {
                    'Szak': szak_name,
                    'Url': response.urljoin(link_url),  # Relatív linket teljes URL-lé alakítja
                    'Kép': response.urljoin(img_url) if img_url else None,  # Képlink validálás
                    'Képzés': page_title,
                }

            except Exception as e:
                logging.error(f"Error processing {response.url}: {e}")
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

       