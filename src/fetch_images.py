"""
fetch_images.py
Sucht zu einem Stichwort ein LIZENZFREIES Bild ueber die Openverse-API
(aggregiert ~700 Mio. offen lizenzierte Werke von Creative Commons).

Warum Openverse: Die Zeitung wird auf GitHub Pages OEFFENTLICH veroeffentlicht
-- da duerfen keine geschuetzten Pressefotos rein. Openverse liefert Bilder
unter freien Lizenzen. Wir filtern auf gemeinfrei + Namensnennung (kein NC/ND),
wandeln in Graustufen (E-Ink) und liefern eine kurze Quellenzeile mit.

Hinweis: Lizenzfreie Quellen haben selten das tagesaktuelle Pressefoto --
die Bilder sind eher thematisch/symbolisch.
"""

import base64
import io
import re

import requests
from PIL import Image, ImageOps

WIKIMEDIA = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
# gemeinfrei (cc0, pdm) + Namensnennung (by, by-sa). Bewusst OHNE NC (nicht-
# kommerziell, Graubereich) und OHNE ND (keine Bearbeitung -> Graustufen waere eine).
LIZENZEN = "cc0,pdm,by,by-sa"
KOPF = {"User-Agent": "kindle-news/1.0 (persoenliche Morgenzeitung)"}


def _als_graustufen_dataurl(bild, breite=1000, seitenverhaeltnis=4 / 3):
    """Graustufen + mittiger 4:3-Zuschnitt -> base64-Data-URL (JPEG)."""
    bild = ImageOps.exif_transpose(bild).convert("L")
    # Kontrast normalisieren -> auf E-Ink (16 Graustufen) klarer, nicht matschig.
    bild = ImageOps.autocontrast(bild, cutoff=1)
    zielhoehe = int(breite / seitenverhaeltnis)
    bild = ImageOps.fit(bild, (breite, zielhoehe), method=Image.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", quality=82)
    b64 = base64.b64encode(puffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _lade_und_wandle(url):
    """Laedt ein Bild von url und gibt die Graustufen-Data-URL zurueck (oder None)."""
    try:
        roh = requests.get(url, headers=KOPF, timeout=25)
        roh.raise_for_status()
        bild = Image.open(io.BytesIO(roh.content))
        return _als_graustufen_dataurl(bild)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Quelle 1: Wikimedia Commons (treffsicher bei konkreten Begriffen: Orte,
# Gebaeude, Personen, Dinge). Alle Inhalte dort sind frei lizenziert.
# ---------------------------------------------------------------------------
def _wikimedia_bild(query):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",        # Datei-Namensraum
        "gsrlimit": "12",
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "1200",       # liefert eine handliche, skalierte Variante
    }
    try:
        antwort = requests.get(WIKIMEDIA, params=params, headers=KOPF, timeout=20)
        antwort.raise_for_status()
        seiten = antwort.json().get("query", {}).get("pages", {}).values()
    except Exception:
        return None

    for seite in seiten:
        infos = seite.get("imageinfo")
        if not infos:
            continue
        info = infos[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue   # SVG/TIF/GIF ueberspringen
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        data = _lade_und_wandle(url)
        if not data:
            continue
        return {
            "data": data,
            "credit": _wikimedia_credit(info.get("extmetadata", {})),
            "quelle": info.get("descriptionurl", ""),
        }
    return None


def _wikimedia_credit(extmeta):
    """Quellenzeile aus den Commons-Metadaten (Artist + Lizenz)."""
    def feld(name):
        return (extmeta.get(name) or {}).get("value", "")
    # Artist kann HTML enthalten -> Tags entfernen
    artist = re.sub(r"<[^>]+>", "", feld("Artist")).strip()
    lizenz = feld("LicenseShortName").strip()
    teile = ["Foto:"]
    teile.append(artist if artist else "Wikimedia Commons")
    if lizenz:
        teile.append("· " + lizenz)
    teile.append("· via Wikimedia Commons")
    return " ".join(teile)


# ---------------------------------------------------------------------------
# Quelle 2 (Fallback): Openverse (CC-Aggregator).
# ---------------------------------------------------------------------------
def _openverse_bild(query):
    params = {"q": query, "license": LIZENZEN, "page_size": 10, "mature": "false"}
    try:
        antwort = requests.get(OPENVERSE, params=params, headers=KOPF, timeout=20)
        antwort.raise_for_status()
        treffer = antwort.json().get("results", [])
    except Exception:
        return None

    for t in treffer:
        url = t.get("url")
        if not url:
            continue
        data = _lade_und_wandle(url)
        if not data:
            continue
        return {
            "data": data,
            "credit": _openverse_credit(t),
            "quelle": t.get("foreign_landing_url", ""),
        }
    return None


def _openverse_credit(treffer):
    lizenz = (treffer.get("license") or "").upper()
    version = treffer.get("license_version") or ""
    creator = treffer.get("creator") or "Unbekannt"
    if lizenz in ("CC0", "PDM"):
        return "Gemeinfrei · via Openverse"
    return f"Foto: {creator} · CC {lizenz} {version} · via Openverse".strip()


def hole_bild(query):
    """
    Sucht ein lizenzfreies Bild -- erst bei Wikimedia Commons (treffsicher),
    dann als Fallback bei Openverse. Gibt {data, credit, quelle} zurueck oder None.
    """
    if not query or not query.strip():
        return None
    return _wikimedia_bild(query) or _openverse_bild(query)


# Eignungs-Rang: kleiner = wichtiger (kommt zuerst dran).
_EIGNUNG_RANG = {"hoch": 0, "mittel": 1, "keine": 2}


def _bild_kandidaten(zeitung):
    """
    Baut die nach Prioritaet sortierte Liste der Artikel, die ueberhaupt ein
    Bild bekommen duerfen ("Kombi"-Logik):
      1. Tages-Aufmacher (erstes Ressort, erster Artikel) -- immer.
      2. Rubrik-Aufmacher mit Bild-Eignung "hoch" oder "mittel".
      3. Weitere Artikel nur bei Bild-Eignung "hoch" (passt besonders gut).
    Sortiert wird: Lead zuerst, dann Aufmacher vor Standard (fuer den ruhigen
    "ein Bild pro Rubrik"-Rhythmus), dann nach Eignung, zuletzt in
    Dokumentreihenfolge. Rueckgabe: Liste von Artikel-Dicts.
    """
    kandidaten = []
    for r_index, ressort in enumerate(zeitung.get("ressorts", [])):
        for a_index, artikel in enumerate(ressort.get("artikel", [])):
            ist_lead = r_index == 0 and a_index == 0
            ist_aufmacher = a_index == 0
            eignung = (artikel.get("bild_eignung") or "keine").lower()

            if ist_lead:
                pass                                   # kommt immer in Frage
            elif ist_aufmacher and eignung in ("hoch", "mittel"):
                pass
            elif eignung == "hoch":
                pass                                   # besonders bildwuerdig
            else:
                continue                               # kein Bild fuer diesen

            sortier = (
                0 if ist_lead else 1,                  # Lead ganz vorne
                0 if ist_aufmacher else 1,             # Aufmacher vor Standard
                _EIGNUNG_RANG.get(eignung, 2),         # dann nach Eignung
                r_index, a_index,                      # dann Dokumentreihenfolge
            )
            kandidaten.append((sortier, artikel))

    kandidaten.sort(key=lambda k: k[0])
    return [artikel for _, artikel in kandidaten]


def setze_bilder(zeitung, max_bilder=4):
    """
    Waehlt bis zu max_bilder Artikel aus und haengt ihnen ein lizenzfreies
    Bild an (bild_data + bild_credit + bild_quelle). Der Tages-Aufmacher wird
    dabei zuerst bedient; weitere Artikel nach Bild-Eignung (siehe
    _bild_kandidaten). Eine fehlgeschlagene Bildsuche verbraucht KEINEN Platz
    -- es wird weitergesucht, bis max_bilder echte Bilder gefunden sind.
    """
    gefunden = 0
    for artikel in _bild_kandidaten(zeitung):
        if gefunden >= max_bilder:
            break
        begriff = artikel.get("bildbegriff") or artikel.get("titel", "")
        ergebnis = hole_bild(begriff)
        if not ergebnis:
            continue
        artikel["bild_data"] = ergebnis["data"]
        artikel["bild_credit"] = ergebnis["credit"]
        artikel["bild_quelle"] = ergebnis["quelle"]
        gefunden += 1
    return zeitung


# Einzeln testbar: python fetch_images.py "earthquake"
if __name__ == "__main__":
    import sys
    begriff = sys.argv[1] if len(sys.argv) > 1 else "newspaper"
    ergebnis = hole_bild(begriff)
    if ergebnis:
        print("Gefunden:", ergebnis["credit"])
        print("Quelle:", ergebnis["quelle"])
        print("Data-URL Laenge:", len(ergebnis["data"]))
    else:
        print("Kein Bild gefunden fuer:", begriff)
