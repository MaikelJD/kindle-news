# Kindle-Morgenzeitung

Eine personalisierte KI-Tageszeitung als PDF für einen gejailbreakten
Kindle 4. Jeden Morgen werden Nachrichten (RSS) und Wetter geholt, von einem
KI-Modell kompakt redigiert (~12 Minuten Lesezeit, auf Deutsch) und als
Zeitung aufbereitet.

## So funktioniert die Zustellung

Statt die Datei auf den Kindle zu "schieben", wird die fertige PDF im Internet
bereitgestellt (GitHub Pages), und der Kindle **holt sie selbst ab** — über
die Lese-App **KOReader** per OPDS-Katalog. Ein Tipp am Morgen, fertig.
(Kein SSH, kein SCP, kein dauerhaft laufender Server nötig.)

## Projektstruktur

```
kindle-news/
├── config.yaml          # alle Einstellungen (Standort, Feeds, Modell)
├── requirements.txt     # benötigte Python-Pakete
├── .env.example         # Vorlage für den API-Schlüssel
├── CLAUDE.md            # Kontext-Anleitung für Claude Code
├── src/
│   ├── fetch_weather.py # Wetter via Open-Meteo (kein Key nötig)
│   ├── fetch_news.py    # RSS-Feeds einlesen
│   ├── summarize.py     # KI-Zusammenfassung via OpenRouter
│   └── main.py          # fädelt alles zusammen
├── templates/           # (kommt: HTML/CSS fürs PDF-Layout)
└── output/              # generierte Dateien (zeitung.json, später .pdf)
```

## Schnellstart

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM jetzt in .env den OpenRouter-Schlüssel eintragen
cd src
python main.py
```

Danach liegt das Ergebnis in `output/zeitung.json`. Das PDF-Rendering und die
Veröffentlichung sind die nächsten Bausteine (siehe `CLAUDE.md`).

## Status

- [x] Wetter holen
- [x] News holen
- [x] KI-Zusammenfassung
- [ ] PDF-Rendering (E-Ink-Layout)
- [ ] Tägliche Automation (GitHub Actions)
- [ ] Veröffentlichung + KOReader-Abruf (OPDS)
