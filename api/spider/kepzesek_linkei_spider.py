import scrapy
import os
import json

class KepzesekLinkeisSpider(scrapy.Spider):
    name = "kepzesek_linkei_spider"
    allowed_domains = ["sapientia.ro"]
    start_urls = [
        "https://ms.sapientia.ro/hu/felveteli/alapkepzes",
        "https://ms.sapientia.ro/hu/felveteli/mesterkepzes"
    ]
    
    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'kepzesek_linkei.json',
        'FEED_EXPORT_ENCODING': 'utf-8',  # Speciálisan kezeli az ékezetes karaktereket
    }

    def parse(self, response):
        szakok = []

        # Alapképzés és mesterképzés linkek gyűjtése
        alapkepzes_links = response.css("a[href*='/felveteli/alapkepzes/']::attr(href)").getall()
        mesterkepzes_links = response.css("a[href*='/felveteli/mesterkepzes/']::attr(href)").getall()

        # A linkek egyesítése és tisztítása
        for link in alapkepzes_links + mesterkepzes_links:
            # Tisztítjuk a linkeket, hogy csak az URL maradjon
            if link.startswith('http'):
                full_link = link  # Ha már teljes URL
            else:
                full_link = response.urljoin(link)  # Ha relatív URL

            szakok.append({"link": full_link})

        # Kiírjuk a Scrapy pipeline-ba is (felülírja a fájlt)
        #yield -> biztosítja, hogy az adatokat a megfelelő formátumban a Scrapy kimeneti fájlba kerüljenek
        for item in szakok:
            yield item
