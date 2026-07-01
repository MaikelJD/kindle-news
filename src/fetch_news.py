"""
fetch_news.py
Liest die in config.yaml definierten Feeds ein und sammelt pro Ressort
die aktuellsten Artikel ein. Noch ohne KI -- nur Rohdaten abholen.
"""

import time
from datetime import datetime, timedelta, timezone

import feedparser
import yaml
import trafilatura


def lade_config(pfad="config.yaml"):
    """Liest die config.yaml ein und gibt sie als Dictionary zurueck."""
    with open(pfad, "r", encoding="utf-8") as datei:
        return yaml.safe_load(datei)


# Wie viele Zeichen Artikeltext wir maximal ans KI-Modell geben. Begrenzt die
# Kosten (lange Reportagen kosten sonst viele Tokens) und reicht fuer eine
# fundierte Zusammenfassung locker aus.
MAX_VOLLTEXT_ZEICHEN = 5000


def hole_volltext(url, max_zeichen=MAX_VOLLTEXT_ZEICHEN):
    """
    Laedt den vollstaendigen Artikel von seiner Webseite und loest den reinen
    Text heraus (ohne Menue, Werbung, Kommentare). So kann das KI-Modell
    fundiert zusammenfassen statt nur aus einem Ein-Satz-Anriss.

    Gibt den Text zurueck -- oder "" , wenn nichts zu holen war (z. B. Paywall
    oder Seite nicht erreichbar). Der Aufrufer faellt dann auf den Anriss zurueck.
    """
    if not url:
        return ""
    try:
        heruntergeladen = trafilatura.fetch_url(url)
        if not heruntergeladen:
            return ""
        text = trafilatura.extract(
            heruntergeladen,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception:
        return ""
    if not text:
        return ""
    text = text.strip()
    if len(text) > max_zeichen:
        text = text[:max_zeichen].rsplit(" ", 1)[0] + " …"
    return text


def _artikel_zeitpunkt(eintrag):
    """
    Holt das Veroeffentlichungsdatum eines Artikels als datetime.
    Feeds liefern das mal als 'published', mal als 'updated' -- wir nehmen,
    was da ist. Findet sich nichts, geben wir None zurueck.
    """
    zeit_struct = (
        getattr(eintrag, "published_parsed", None)
        or getattr(eintrag, "updated_parsed", None)
    )
    if zeit_struct is None:
        return None
    return datetime.fromtimestamp(time.mktime(zeit_struct), tz=timezone.utc)


def hole_artikel_fuer_ressort(ressort, max_alter_stunden=36):
    """
    Liest EINEN Feed und gibt eine Liste sauberer Artikel zurueck.
    max_alter_stunden: aeltere Artikel werden ignoriert (Standard 36h,
    damit am Wochenende/Feiertag nicht alles leer ist).
    """
    feed = feedparser.parse(ressort["feed"])

    grenze = datetime.now(timezone.utc) - timedelta(hours=max_alter_stunden)
    artikel = []

    for eintrag in feed.entries:
        zeitpunkt = _artikel_zeitpunkt(eintrag)

        # Zu alt? -> ueberspringen. Kein Datum? -> trotzdem behalten.
        if zeitpunkt is not None and zeitpunkt < grenze:
            continue

        link = eintrag.get("link", "")
        artikel.append({
            "titel": eintrag.get("title", "").strip(),
            "anriss": eintrag.get("summary", "").strip(),  # Kurztext aus Feed
            "link": link,
            "volltext": "",   # wird gleich (optional) gefuellt
            "zeitpunkt": zeitpunkt,
        })

        if len(artikel) >= ressort["max_artikel"]:
            break

    return artikel


def hole_alle_news(config, mit_volltext=True):
    """
    Geht alle Ressorts aus der Config durch und sammelt deren Artikel --
    in genau der Reihenfolge, in der sie spaeter in der Zeitung stehen.

    mit_volltext=True: laedt zusaetzlich den vollstaendigen Artikeltext jeder
    Quelle (fuer fundierte, laengere Zusammenfassungen). Schlaegt das fehl,
    bleibt der Feed-Anriss als Rueckfallebene erhalten.
    """
    ergebnis = []
    for ressort in config["ressorts"]:
        artikel = hole_artikel_fuer_ressort(ressort)

        if mit_volltext:
            for eintrag in artikel:
                eintrag["volltext"] = hole_volltext(eintrag["link"])

        # Kurzer Statusbericht: wie viele Artikel, wie viele mit echtem Volltext
        mit_text = sum(1 for a in artikel if a["volltext"])
        ergebnis.append({"name": ressort["name"], "artikel": artikel})
        print(f"  {ressort['name']}: {len(artikel)} Artikel "
              f"({mit_text} mit Volltext)")
    return ergebnis


# Zum einzelnen Testen dieser Datei:
if __name__ == "__main__":
    config = lade_config()
    print("Lade News...")
    news = hole_alle_news(config)
    print("\nFertig. Beispiel-Artikel:")
    for ressort in news:
        if ressort["artikel"]:
            print(f"\n[{ressort['name']}]")
            print(" -", ressort["artikel"][0]["titel"])
