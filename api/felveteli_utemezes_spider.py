import scrapy
import os

class FelveteliUtemezesSpider(scrapy.Spider):
    name = "felveteli_utemezes"
    start_urls = [
        'https://ms.sapientia.ro/hu/felveteli/felveteli-utemezes'
    ]

    if os.path.exists('felveteli_utemezes.csv'):  # Ellenőrizzük, hogy létezik-e már a CSV fájl
        print(f"A fájl már létezik: {'felveteli_utemezes.csv'}. Semmit sem csinálok.")
        exit()  # Ha létezik, nem csinál semmit

    custom_settings = {
        'FEED_FORMAT': 'csv',
        'FEED_URI': 'felveteli_utemezes.csv',
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def parse(self, response):
        # Felvételi ütemezés blokk kiválasztása
        utemezes_div = response.css('div#nright')

        # Képek kinyerése
        image_urls = utemezes_div.css('img::attr(src)').getall()
        full_image_urls = [response.urljoin(img) for img in image_urls]  # Relatív linkek teljes URL-é alakítása

        # Dátumok és vizsgák kivonása
        utemezes_info = []
        p_blocks = utemezes_div.css('div.news-descr p')

        for p in p_blocks:
            text = p.css('strong::text').get()
            if text:
                date_span = p.css('span::text').get()
                utemezes_info.append({
                    "cim": text.strip(),
                    "dátum": date_span.strip() if date_span else None
                })

        # Felvételi ütemezés címének kinyerése
        header = response.css('div.descr-tit.color_blue::text').get()

        utemezes_str = ' '.join([f"{item['cim']} {item['dátum']}" for item in utemezes_info])

        # Képek listáját egy stringgé alakítjuk, ahol a képek URL-jeit ';' karakterrel választjuk el
        images_str = ';'.join(full_image_urls)

        yield {
            "cim": header.strip() if header else None,
            "url": response.url,
            "képek": images_str,
            "ütemezés": utemezes_str  # Itt tároljuk az ütemezés listát string formájában
        }
