import csv
import os

def csv_to_text(csv_file_path, output_file_path):
    """CSV fájlt szöveggé alakít és csak akkor menti, ha a TXT fájl még nem létezik."""
    if os.path.exists(output_file_path):  # Ellenőrizzük, hogy létezik-e már a TXT fájl
        print(f"A fájl már létezik: {output_file_path}. Semmit sem csinálok.")
        return  # Ha létezik, nem csinál semmit

    # CSV beolvasása
    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Fejléc átlépése
        
        text_data = []  # Szöveges adatok tárolása

        # Sorok feldolgozása
        for row in reader:
            result_text = ' '.join([f"{header[i].capitalize()}: {row[i]}" for i in range(len(row))])
            text_data.append(result_text)
        
    # Szövegek mentése TXT fájlba
    with open(output_file_path, 'w', encoding='utf-8') as txtfile:
        for text in text_data:
            txtfile.write(text + "\n")

    print(f"Szöveg sikeresen elmentve: {output_file_path}")


def process_multiple_csv(csv_files):
    """Több CSV fájl feldolgozása egy listából."""
    for csv_file_path in csv_files:
        # Kimeneti fájl neve a CSV fájl neve alapján
        output_file_path = f"{csv_file_path.split('.')[0]}.txt"
        csv_to_text(csv_file_path, output_file_path)


# Példa használat
csv_files = ['sapientia_kepzesei.csv','felveteli_utemezes.csv']  # A fájlok nevei egy listában

# Több CSV fájl feldolgozása
process_multiple_csv(csv_files)
