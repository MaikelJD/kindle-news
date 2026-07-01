"""
build_site.py
Baut den Ordner 'site/', den GitHub Pages spaeter ins Internet stellt.

Inhalt von site/:
  - zeitung.pdf   : die fertige Ausgabe (Kopie aus output/)
  - catalog.xml   : OPDS-Katalog -> DAS holt sich KOReader auf dem Kindle ab
  - index.html    : kleine Startseite fuer den Browser (zum Nachschauen)

OPDS ist das "Buchregal-Format", das KOReader versteht. Du traegst die
Katalog-Adresse einmal in KOReader ein; danach erscheint die Zeitung dort
jeden Morgen als neuer Eintrag zum Herunterladen.

Aufruf (nach main.py):
    cd src
    python build_site.py
"""

import os
import shutil
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from fetch_news import lade_config
from render_pdf import _pfade, _deutsches_datum


def _jetzt(zeitzone="Europe/Berlin"):
    """Aktuelle Zeit in der gewuenschten Zeitzone (faellt notfalls auf UTC)."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(zeitzone))
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _xml_escape(text):
    """Macht Text fuer XML sicher (&, <, > ersetzen)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _schreibe_catalog(ziel_ordner, config, pdf_name, jetzt):
    """Schreibt den OPDS-Katalog (catalog.xml)."""
    titel = config["zeitung"]["titel"]
    datum_lesbar = _deutsches_datum(
        config.get("standort", {}).get("zeitzone", "Europe/Berlin")
    )
    # Zeitstempel im Format, das OPDS erwartet (z. B. 2026-06-30T06:00:00Z)
    stempel = jetzt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datum_id = jetzt.strftime("%Y-%m-%d")

    eintrag_titel = _xml_escape(f"{titel} – {datum_lesbar}")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>urn:kindle-news:catalog</id>
  <title>{_xml_escape(titel)}</title>
  <updated>{stempel}</updated>
  <author><name>kindle-news</name></author>
  <link rel="self"
        href="catalog.xml"
        type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <link rel="start"
        href="catalog.xml"
        type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <entry>
    <title>{eintrag_titel}</title>
    <id>urn:kindle-news:{datum_id}</id>
    <updated>{stempel}</updated>
    <content type="text">Nachrichten und Wetter, kompakt fuer den Morgen.</content>
    <link rel="http://opds-spec.org/acquisition"
          href="{pdf_name}"
          type="application/pdf"/>
  </entry>
</feed>
"""
    pfad = os.path.join(ziel_ordner, "catalog.xml")
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write(xml)
    return pfad


def _schreibe_index(ziel_ordner, config, pdf_name):
    """Schreibt eine schlichte Startseite (zum Nachschauen im Browser)."""
    titel = config["zeitung"]["titel"]
    datum_lesbar = _deutsches_datum(
        config.get("standort", {}).get("zeitzone", "Europe/Berlin")
    )
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_xml_escape(titel)}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 640px; margin: 40px auto;
         padding: 0 20px; line-height: 1.5; color: #111; }}
  a.button {{ display: inline-block; margin-top: 12px; padding: 10px 18px;
             border: 2px solid #111; text-decoration: none; color: #111; }}
  code {{ background: #f0f0f0; padding: 2px 5px; }}
</style>
</head>
<body>
  <h1>{_xml_escape(titel)}</h1>
  <p>Ausgabe vom {datum_lesbar}.</p>
  <p><a class="button" href="{pdf_name}">PDF oeffnen</a></p>
  <hr>
  <p>Auf dem Kindle ueber <strong>KOReader &rarr; OPDS-Katalog</strong> abrufen.
     Katalog-Adresse: <code>catalog.xml</code> (relativ zu dieser Seite).</p>
</body>
</html>
"""
    pfad = os.path.join(ziel_ordner, "index.html")
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write(html)
    return pfad


def baue_site():
    """Baut den kompletten site/-Ordner aus der vorhandenen output/zeitung.pdf."""
    pfade = _pfade()
    config = lade_config(os.path.join(pfade["projekt"], "config.yaml"))

    quell_pdf = os.path.join(pfade["output"], "zeitung.pdf")
    if not os.path.exists(quell_pdf):
        raise SystemExit(
            "Keine output/zeitung.pdf gefunden. Bitte zuerst 'python main.py' "
            "laufen lassen (oder 'python render_pdf.py')."
        )

    site = os.path.join(pfade["projekt"], "site")
    os.makedirs(site, exist_ok=True)

    pdf_name = "zeitung.pdf"
    shutil.copyfile(quell_pdf, os.path.join(site, pdf_name))

    zeitzone = config.get("standort", {}).get("zeitzone", "Europe/Berlin")
    jetzt = _jetzt(zeitzone)

    _schreibe_catalog(site, config, pdf_name, jetzt)
    _schreibe_index(site, config, pdf_name)

    print(f"site/ gebaut: {site}")
    print("  - zeitung.pdf")
    print("  - catalog.xml  (fuer KOReader/OPDS)")
    print("  - index.html   (zum Nachschauen im Browser)")
    return site


if __name__ == "__main__":
    baue_site()
