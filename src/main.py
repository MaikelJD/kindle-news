"""
main.py
Faedelt alle Schritte aneinander:
  1. Config laden
  2. Wetter holen
  3. News holen
  4. Mit KI zur Zeitung zusammenfassen
  5. (TODO) PDF rendern
  6. (TODO) Zustellung vorbereiten (GitHub Pages -> KOReader holt es ab)

Aktueller Stand: Schritte 1-4 laufen. Das Ergebnis wird als JSON in
output/zeitung.json gespeichert -- so kannst du heute schon pruefen, ob
die KI-Zusammenfassung sauber funktioniert, bevor wir das PDF bauen.
"""

import json
import os

from dotenv import load_dotenv

from fetch_weather import hole_wetter
from fetch_news import lade_config, hole_alle_news
from summarize import erstelle_zeitung
from fetch_images import setze_bilder
from render_pdf import baue_pdf


def main():
    # Liest den API-Schluessel aus der .env-Datei im Projektordner.
    load_dotenv()

    print("1/5  Config laden...")
    config = lade_config()

    print("2/5  Wetter holen...")
    wetter = hole_wetter(
        config["standort"]["breitengrad"],
        config["standort"]["laengengrad"],
        config["standort"]["zeitzone"],
    )
    print(f"     heute: {wetter['heute']['beschreibung']}, "
          f"{wetter['heute']['min']}-{wetter['heute']['max']} Grad")

    print("3/5  News holen...")
    news = hole_alle_news(config)

    print("4/5  KI-Zusammenfassung erstellen...")
    zeitung = erstelle_zeitung(news, wetter, config)

    max_bilder = config.get("bilder", {}).get("max", 4)
    print(f"     Lizenzfreie Bilder holen (bis zu {max_bilder})...")
    zeitung = setze_bilder(zeitung, max_bilder)

    # Ergebnis speichern, damit wir es ansehen koennen
    os.makedirs("output", exist_ok=True)
    pfad = os.path.join("output", "zeitung.json")
    with open(pfad, "w", encoding="utf-8") as datei:
        json.dump(zeitung, datei, ensure_ascii=False, indent=2, default=str)
    print(f"     zeitung.json gespeichert ({pfad})")

    print("5/5  PDF fuer den Kindle bauen...")
    pdf_pfad = baue_pdf(zeitung, config)

    print(f"\nFertig! PDF liegt in {pdf_pfad}")
    print(f"Intro: {zeitung['intro'][:120]}...")

    # --- NAECHSTER BAUSTEIN ---
    # PDF auf GitHub Pages veroeffentlichen, KOReader holt es per OPDS-Katalog.


if __name__ == "__main__":
    main()
