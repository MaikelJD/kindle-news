"""
render_pdf.py
Baut aus der fertigen Zeitungs-Struktur (output/zeitung.json) ein PDF
fuer den Kindle.

Ablauf:
  1. HTML-Vorlage (templates/zeitung.html) mit den Daten fuellen  -> Jinja2
  2. Diese HTML-Seite in einem unsichtbaren Chrome oeffnen        -> Playwright
  3. Die Seite als PDF speichern (600x800 px, Graustufen-tauglich)

Einmalige Einrichtung (nur beim allerersten Mal noetig):
    pip install -r requirements.txt
    playwright install chromium
"""

import json
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo        # Python 3.9+ (Zeitzonen)
except ImportError:                      # Sicherheitsnetz fuer aeltere Versionen
    ZoneInfo = None

from jinja2 import Environment, FileSystemLoader, select_autoescape


# Deutsche Namen fuer Wochentage und Monate (Windows-Locale ist unzuverlaessig,
# darum machen wir das selbst -- so steht immer "Montag, 30. Juni 2026" da).
WOCHENTAGE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
MONATE = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _deutsches_datum(zeitzone="Europe/Berlin"):
    """Gibt z. B. 'Montag, 30. Juni 2026' fuer heute zurueck."""
    jetzt = None
    if ZoneInfo is not None:
        try:
            jetzt = datetime.now(ZoneInfo(zeitzone))
        except Exception:
            # z. B. auf Windows ohne Zeitzonen-Daten -> auf lokale Zeit ausweichen
            jetzt = None
    if jetzt is None:
        jetzt = datetime.now()
    wochentag = WOCHENTAGE[jetzt.weekday()]
    monat = MONATE[jetzt.month - 1]
    return f"{wochentag}, {jetzt.day}. {monat} {jetzt.year}"


def _pfade():
    """
    Liefert die wichtigen Projekt-Pfade -- egal, ob das Skript aus dem
    Projektordner ODER aus dem src-Ordner gestartet wird.
    """
    hier = os.path.dirname(os.path.abspath(__file__))   # .../src
    projekt = os.path.dirname(hier)                      # Projekt-Wurzel
    return {
        "projekt": projekt,
        "templates": os.path.join(projekt, "templates"),
        "output": os.path.join(projekt, "output"),
    }


def _baue_html(zeitung, config):
    """Fuellt die HTML-Vorlage mit den Zeitungsdaten und gibt HTML-Text zurueck."""
    pfade = _pfade()
    umgebung = Environment(
        loader=FileSystemLoader(pfade["templates"]),
        autoescape=select_autoescape(["html"]),
    )
    vorlage = umgebung.get_template("zeitung.html")

    zeitzone = config.get("standort", {}).get("zeitzone", "Europe/Berlin")

    return vorlage.render(
        # Basis-Schriftgroesse aus config.yaml -- die ganze Typo-Skala im
        # Template ist in rem angelegt und skaliert daran mit.
        basis_schrift=config.get("pdf", {}).get("schriftgroesse_px", 26),
        titel=config["zeitung"]["titel"],
        ort=config.get("standort", {}).get("name", ""),
        datum_text=_deutsches_datum(zeitzone),
        intro=zeitung.get("intro", ""),
        wichtigste=zeitung.get("wichtigste", []),
        wetter=zeitung.get("wetter", {}),
        ressorts=zeitung.get("ressorts", []),
    )


def baue_pdf(zeitung, config, ziel_pfad=None):
    """
    Wandelt die Zeitungs-Struktur in ein PDF um.

    zeitung   : das Dictionary aus summarize.erstelle_zeitung (oder zeitung.json)
    config    : die geladene config.yaml
    ziel_pfad : wohin das PDF soll. Standard: output/zeitung.pdf
    """
    pfade = _pfade()
    if ziel_pfad is None:
        ziel_pfad = os.path.join(pfade["output"], "zeitung.pdf")

    html = _baue_html(zeitung, config)

    # Playwright erst hier importieren -> wenn es fehlt, koennen die anderen
    # Schritte (1-4) trotzdem laufen, und wir geben eine klare Anleitung.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright ist noch nicht installiert. Bitte einmalig ausfuehren:\n"
            "    pip install -r requirements.txt\n"
            "    playwright install chromium"
        )

    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)

    pdf_einst = config.get("pdf", {})
    breite = pdf_einst.get("breite_px", 600)
    hoehe = pdf_einst.get("hoehe_px", 800)
    # Einheitlicher Rand auf JEDER Seite (echter PDF-Seitenrand, nicht CSS-Padding).
    rand = pdf_einst.get("rand_px", 48)

    # Dezente, mittige Seitenzahl im unteren Rand -- fuer visuelle Ruhe.
    footer = (
        '<div style="width:100%; text-align:center; font-family:Arial, sans-serif;'
        ' font-size:7px; letter-spacing:0.25em; color:#9a9a9a;">'
        '<span class="pageNumber"></span></div>'
    )
    leer = '<div></div>'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            seite = browser.new_page()
            # networkidle: wartet, bis die Webfonts (Google Fonts) geladen sind.
            seite.set_content(html, wait_until="networkidle")
            # Sicherstellen, dass die Schriften wirklich einsatzbereit sind,
            # bevor das PDF "fotografiert" wird.
            seite.evaluate("document.fonts.ready")
            seite.pdf(
                path=ziel_pfad,
                width=f"{breite}px",
                height=f"{hoehe}px",
                print_background=True,
                display_header_footer=True,
                header_template=leer,
                footer_template=footer,
                margin={
                    "top": f"{rand}px", "right": f"{rand}px",
                    "bottom": f"{rand}px", "left": f"{rand}px",
                },
            )
            browser.close()
    except Exception as fehler:
        # Haeufigster Grund: der Chromium-Browser wurde noch nicht geladen.
        raise RuntimeError(
            "PDF-Erstellung fehlgeschlagen. Falls der Chromium-Browser fehlt, "
            "bitte einmalig ausfuehren:\n    playwright install chromium\n\n"
            f"Technische Meldung: {fehler}"
        )

    return ziel_pfad


# Diese Datei laesst sich auch einzeln testen -- praktisch, wenn die
# zeitung.json schon existiert und du nur am Layout feilst:
#     cd src
#     python render_pdf.py
if __name__ == "__main__":
    from fetch_news import lade_config

    pfade = _pfade()
    config = lade_config(os.path.join(pfade["projekt"], "config.yaml"))

    json_pfad = os.path.join(pfade["output"], "zeitung.json")
    if not os.path.exists(json_pfad):
        raise SystemExit(
            "Keine output/zeitung.json gefunden. Bitte zuerst 'python main.py' "
            "laufen lassen, damit die Daten da sind."
        )

    with open(json_pfad, "r", encoding="utf-8") as datei:
        zeitung = json.load(datei)

    ziel = baue_pdf(zeitung, config)
    print(f"PDF erstellt: {ziel}")
