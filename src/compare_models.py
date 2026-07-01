"""
compare_models.py
Baut DIESELBE Tagesausgabe einmal mit Haiku und einmal mit Sonnet -- damit du
am echten Ergebnis entscheiden kannst, welches Modell dir die Qualitaet wert ist.

Clever: News + Wetter + Volltext werden nur EINMAL geholt; nur die
KI-Zusammenfassung laeuft zweimal. So vergleichst du fair denselben Tag und
sparst dir das doppelte Laden.

Ergebnis:
  output/zeitung_haiku.json  + output/zeitung_haiku.pdf
  output/zeitung_sonnet.json + output/zeitung_sonnet.pdf
"""

import json
import os

from dotenv import load_dotenv

from fetch_weather import hole_wetter
from fetch_news import lade_config, hole_alle_news
from summarize import erstelle_zeitung
from render_pdf import baue_pdf, _pfade


# Welche Modelle verglichen werden (Name fuer die Datei -> OpenRouter-Modell)
MODELLE = [
    ("haiku", "anthropic/claude-haiku-4.5"),
    ("sonnet", "anthropic/claude-sonnet-4.6"),
]


def main():
    load_dotenv()
    pfade = _pfade()
    config = lade_config(os.path.join(pfade["projekt"], "config.yaml"))

    print("Wetter holen...")
    wetter = hole_wetter(
        config["standort"]["breitengrad"],
        config["standort"]["laengengrad"],
        config["standort"]["zeitzone"],
    )

    print("News + Volltext holen (einmalig fuer beide Modelle)...")
    news = hole_alle_news(config, mit_volltext=True)

    os.makedirs(pfade["output"], exist_ok=True)

    for kuerzel, modell in MODELLE:
        print(f"\n=== Modell: {modell} ===")
        print("  KI-Zusammenfassung erstellen...")
        zeitung = erstelle_zeitung(news, wetter, config, modell=modell)

        json_pfad = os.path.join(pfade["output"], f"zeitung_{kuerzel}.json")
        with open(json_pfad, "w", encoding="utf-8") as datei:
            json.dump(zeitung, datei, ensure_ascii=False, indent=2, default=str)

        pdf_pfad = os.path.join(pfade["output"], f"zeitung_{kuerzel}.pdf")
        baue_pdf(zeitung, config, pdf_pfad)
        print(f"  fertig: {pdf_pfad}")

    print("\nVergleich fertig. Oeffne zum Vergleichen:")
    for kuerzel, _ in MODELLE:
        print(f"  output/zeitung_{kuerzel}.pdf")


if __name__ == "__main__":
    main()
