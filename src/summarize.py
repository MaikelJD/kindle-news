"""
summarize.py
Schickt Wetter + echte Artikeltexte an ein KI-Modell (ueber OpenRouter) und
baut daraus eine redigierte Zeitung mit GESTAFFELTER Tiefe:

  - "intro"        : freundlicher Einstieg in den Tag
  - "wichtigste"   : 4-6 Ueberblickspunkte (je 1 Satz) -> die "Aufhaenger"
  - Aufmacher      : der ERSTE Artikel je Ressort, ausfuehrlich (mehrere
                     Absaetze: Geschehen, Hintergrund, Einordnung)
  - weitere Artikel: kompakt (3-5 Saetze)

Wichtig fuer Verlaesslichkeit: Das Modell fasst NUR aus dem mitgelieferten
Artikeltext zusammen und darf nichts erfinden. Die Original-Links bleiben
erhalten, damit man jederzeit gegenpruefen kann.
"""

import json
import os
from openai import OpenAI


def _quelle(artikel):
    """Bevorzugt den echten Volltext; faellt auf den Feed-Anriss zurueck."""
    return artikel.get("volltext") or artikel.get("anriss") or ""


def _baue_artikel_liste(news):
    """
    Flache Liste aller Artikel mit eindeutiger ID, Rolle (Aufmacher/Standard)
    und Quelltext. Der erste Artikel je Ressort ist der Aufmacher.
    """
    eintraege = []
    for r_index, ressort in enumerate(news):
        for a_index, artikel in enumerate(ressort["artikel"]):
            eintraege.append({
                "id": f"r{r_index}a{a_index}",
                "ressort": ressort["name"],
                "rolle": "aufmacher" if a_index == 0 else "standard",
                "titel": artikel["titel"],
                "quelltext": _quelle(artikel),
            })
    return eintraege


def _baue_prompt(wetter, artikel_liste, lesezeit, ort):
    """Stellt die Anweisung an das KI-Modell zusammen (auf Deutsch)."""
    artikel_text = json.dumps(artikel_liste, ensure_ascii=False, indent=2)
    wetter_zeile = (
        f"{wetter['heute']['beschreibung']}, "
        f"{wetter['heute']['min']}-{wetter['heute']['max']} Grad"
    )

    return f"""Du bist Chefredakteur einer anspruchsvollen persoenlichen
Morgenzeitung. Schreibe nuechtern, praezise, gut eingeordnet und in fluessigem
Deutsch -- auf dem Niveau einer serioesen Tageszeitung.

Die ganze Ausgabe soll etwa {lesezeit} Minuten Lesezeit ergeben (also durchaus
gehaltvoll, kein blosser Ticker). Wetter heute in {ort}: {wetter_zeile}.

Du bekommst die heutigen Artikel als JSON. Jeder hat eine 'id', eine 'rolle'
und einen 'quelltext' (der echte Artikeltext, manchmal nur ein kurzer Anriss).

So tief schreibst du je nach Rolle:
- rolle = "aufmacher": AUSFUEHRLICH, 3 Absaetze, ca. 150-220 Woerter. Absatz 1:
  was ist passiert (Kern). Absatz 2: Hintergrund und Kontext aus dem Quelltext.
  Absatz 3: Bedeutung / Einordnung -- warum es zaehlt. Sachlich, keine Meinung.
- rolle = "standard": KOMPAKT, 3-5 Saetze (ca. 60-100 Woerter), ein Absatz.

Jede Zusammenfassung ist eine LISTE von Absaetzen (jeder Absatz ein eigener
Listeneintrag als Text). Aufmacher = 3 Eintraege, Standard = 1 Eintrag.

ABSOLUT WICHTIG (Verlaesslichkeit):
- Nutze AUSSCHLIESSLICH Informationen aus dem jeweiligen 'quelltext'. Erfinde
  keine Fakten, Zahlen, Zitate, Namen oder Hintergruende und ergaenze nichts
  aus eigenem Wissen.
- Wenn der Quelltext fuer eine tiefe Einordnung nicht genug hergibt, schreibe
  lieber kuerzer als zu spekulieren. Niemals raten.
- Formuliere in EIGENEN Worten, uebernimm keine ganzen Saetze woertlich.

Antworte AUSSCHLIESSLICH mit gueltigem JSON in genau dieser Struktur, ohne
weiteren Text und ohne Markdown:

{{
  "intro": "2-3 Saetze, die freundlich in den Tag einleiten (Wetter darf vorkommen)",
  "wichtigste": ["4-6 kurze Stichpunkte mit dem Wichtigsten des Tages, je ein Satz"],
  "zusammenfassungen": {{
    "<id>": ["Absatz 1", "Absatz 2 (nur beim Aufmacher)", "Absatz 3 (nur beim Aufmacher)"]
  }},
  "bildbegriffe": {{
    "<id>": "kurzer englischer Bild-Suchbegriff (1-3 Woerter), eher symbolisch/thematisch"
  }},
  "bild_eignung": {{
    "<id>": "hoch | mittel | keine"
  }}
}}

Gib fuer JEDE 'id' aus der Liste genau einen Eintrag in 'zusammenfassungen' zurueck
(als Liste von Absaetzen) UND einen 'bildbegriffe'-Eintrag. Der Bildbegriff ist
ein KONKRETER englischer Suchbegriff fuer eine Stockbild-Suche (z. B. "earthquake
rubble", "parliament building", "vaccine syringe") -- thematisch passend, ohne
Eigennamen, gut bebilderbar.

Gib ausserdem fuer JEDE 'id' eine 'bild_eignung' an -- wie gut sich die Geschichte
mit einem LIZENZFREIEN, eher symbolischen Bild bebildern laesst (wir haben KEINE
tagesaktuellen Pressefotos, nur freie/thematische Motive):
- "hoch"  : ein klares, aussagekraeftiges Motiv passt sehr gut (konkreter Ort,
            Gebaeude, Objekt, Natur-/Wetterereignis, Technik, Tier, Sport).
- "mittel": ein passables thematisches Bild ist denkbar, aber eher generisch.
- "keine" : abstrakt, reine Verfahrens-/Politmeldung, Statistik ODER heikel/
            pietaetlos zu bebildern (Gewalt, Unglueck mit Opfern) -> lieber kein Bild.
Sei zurueckhaltend mit "hoch" -- nur wenn ein Bild den Artikel wirklich aufwertet.

Heutige Artikel (JSON):
{artikel_text}"""


def _als_absatzliste(wert, rueckfall=""):
    """
    Macht aus der Modell-Antwort eine saubere Liste von Absaetzen.
    - Liste -> nur nicht-leere Texte behalten
    - einzelner Text -> an Leerzeilen in Absaetze trennen
    - nichts -> Rueckfalltext (Feed-Anriss) verwenden
    """
    if isinstance(wert, list):
        absaetze = [str(p).strip() for p in wert if str(p).strip()]
    elif isinstance(wert, str) and wert.strip():
        absaetze = [t.strip() for t in wert.split("\n\n") if t.strip()]
    else:
        absaetze = []

    if not absaetze:
        absaetze = [rueckfall.strip()] if rueckfall.strip() else []
    return absaetze


def _saeubere_json(roh):
    """Entfernt eventuelle ```-Codebloecke, die manche Modelle drumherum setzen."""
    roh = roh.strip()
    if roh.startswith("```"):
        roh = roh.strip("`")
        if "\n" in roh:
            roh = roh.split("\n", 1)[1]
        if roh.lstrip().startswith("json"):
            roh = roh.lstrip()[4:]
    return roh


def erstelle_zeitung(news, wetter, config, modell=None):
    """
    Ruft das KI-Modell auf und baut die fertige Zeitungs-Struktur.

    modell: optionaler Modell-Name, der die Einstellung aus der config
    ueberschreibt (praktisch fuer den Vergleich Haiku vs. Sonnet).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Kein API-Schluessel gefunden. Bitte OPENROUTER_API_KEY "
            "setzen (siehe CLAUDE.md)."
        )

    # OpenRouter ist OpenAI-kompatibel: gleicher Client, andere Adresse.
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    artikel_liste = _baue_artikel_liste(news)
    prompt = _baue_prompt(
        wetter,
        artikel_liste,
        config["zeitung"]["lesezeit_minuten"],
        config["standort"]["name"],
    )

    modell_name = modell or config["ki"]["modell"]
    antwort = client.chat.completions.create(
        model=modell_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=8000,        # Platz fuer gehaltvolle Texte (~12 Min Lesezeit)
        # JSON-Modus: der Anbieter garantiert gueltiges JSON -> keine kaputten
        # Anfuehrungszeichen/Umbrueche mehr.
        response_format={"type": "json_object"},
    )
    daten = json.loads(_saeubere_json(antwort.choices[0].message.content))

    # KI-Zusammenfassungen zurueck in die Ressort-Struktur einsetzen,
    # dabei unsere Original-Links und die Rolle (Aufmacher/Standard) behalten.
    zusammenfassungen = daten.get("zusammenfassungen", {})
    bildbegriffe = daten.get("bildbegriffe", {})
    bild_eignung = daten.get("bild_eignung", {})
    ressorts_fertig = []
    for r_index, ressort in enumerate(news):
        artikel_fertig = []
        for a_index, artikel in enumerate(ressort["artikel"]):
            artikel_id = f"r{r_index}a{a_index}"
            absaetze = _als_absatzliste(
                zusammenfassungen.get(artikel_id),
                rueckfall=artikel.get("anriss", ""),
            )
            artikel_fertig.append({
                "titel": artikel["titel"],
                "rolle": "aufmacher" if a_index == 0 else "standard",
                "zusammenfassung": absaetze,
                "bildbegriff": bildbegriffe.get(artikel_id, ""),
                "bild_eignung": (bild_eignung.get(artikel_id) or "keine").lower(),
                "link": artikel["link"],
            })
        if artikel_fertig:
            ressorts_fertig.append(
                {"name": ressort["name"], "artikel": artikel_fertig}
            )

    return {
        "intro": daten.get("intro", ""),
        "wichtigste": daten.get("wichtigste", []),
        "wetter": wetter,
        "modell": modell_name,
        "ressorts": ressorts_fertig,
    }
