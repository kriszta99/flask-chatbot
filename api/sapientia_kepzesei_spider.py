import scrapy

class SapientiaKepzeseiSpider(scrapy.Spider):
    name = "sapientia_kepzesei"
    
    start_urls = [
        'https://ms.sapientia.ro/hu/felveteli/alapkepzes',
        'https://ms.sapientia.ro/hu/felveteli/mesterkepzes',
    ]

    custom_settings = {
        'FEED_FORMAT': 'csv',  
        'FEED_URI': 'sapientia_kepzesei.csv',
        'FEED_EXPORT_ENCODING': 'utf-8',  # Speciálisan kezeli az ékezetes karaktereket
    }

    def parse(self, response):
        # Oldal címének kinyerése
        page_title = response.css('div#pagetitle::text').get()
        if page_title:
            page_title = page_title.strip()

        # Szakok információinak kinyerése
        for link in response.css('a.szak'):
            szak_name = link.css('span::text').get()
            if szak_name:
                szak_name = szak_name.strip()
            
            link_url = link.attrib.get('href', '')
            img_url = link.css('img::attr(src)').get()

            # Szakok adatainak átadása CSV-be
            yield {
                'szak neve': szak_name,
                'link url cime': response.urljoin(link_url),  # Relatív linket teljes URL-lé alakítja
                'kép url cime': response.urljoin(img_url) if img_url else None,  # Képlink validálás
                'képzes tipúsa': page_title,
            }
