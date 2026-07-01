"""
fetch_weather.py
Holt aktuelle Wetterdaten + Tagesvorhersage von Open-Meteo.
Kostenlos, kein API-Schluessel noetig.
"""

import requests

# Open-Meteo liefert nur eine Zahl (WMO-Code). Hier uebersetzen wir sie
# in deutsche Beschreibung + ein einfaches Symbol.
WETTER_CODES = {
    0:  ("Klar", "\u2600"),
    1:  ("\u00dcberwiegend klar", "\u2600"),
    2:  ("Teils bew\u00f6lkt", "\u26c5"),
    3:  ("Bew\u00f6lkt", "\u2601"),
    45: ("Nebel", "\U0001f32b"),
    48: ("Reifnebel", "\U0001f32b"),
    51: ("Leichter Nieselregen", "\U0001f326"),
    53: ("Nieselregen", "\U0001f326"),
    55: ("Starker Nieselregen", "\U0001f327"),
    61: ("Leichter Regen", "\U0001f326"),
    63: ("Regen", "\U0001f327"),
    65: ("Starker Regen", "\U0001f327"),
    71: ("Leichter Schneefall", "\U0001f328"),
    73: ("Schneefall", "\U0001f328"),
    75: ("Starker Schneefall", "\u2744"),
    80: ("Regenschauer", "\U0001f326"),
    81: ("Regenschauer", "\U0001f327"),
    82: ("Heftige Schauer", "\u26c8"),
    95: ("Gewitter", "\u26c8"),
    96: ("Gewitter mit Hagel", "\u26c8"),
}


def hole_wetter(breitengrad, laengengrad, zeitzone):
    """Fragt Open-Meteo ab und gibt ein aufgeraeumtes Dictionary zurueck."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": breitengrad,
        "longitude": laengengrad,
        "timezone": zeitzone,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset",
    }

    antwort = requests.get(url, params=params, timeout=15)
    antwort.raise_for_status()          # Bricht ab, falls die Abfrage scheitert
    daten = antwort.json()

    # --- aktuelle Werte ---
    jetzt = daten["current"]
    beschr_jetzt, symbol_jetzt = WETTER_CODES.get(
        jetzt["weather_code"], ("Unbekannt", "")
    )

    # --- Tagesvorhersage (Index 0 = heute) ---
    heute = daten["daily"]
    beschr_heute, symbol_heute = WETTER_CODES.get(
        heute["weather_code"][0], ("Unbekannt", "")
    )

    return {
        "jetzt": {
            "temperatur": round(jetzt["temperature_2m"]),
            "beschreibung": beschr_jetzt,
            "symbol": symbol_jetzt,
            "wind": round(jetzt["wind_speed_10m"]),
        },
        "heute": {
            "max": round(heute["temperature_2m_max"][0]),
            "min": round(heute["temperature_2m_min"][0]),
            "beschreibung": beschr_heute,
            "symbol": symbol_heute,
            "regen_prozent": heute["precipitation_probability_max"][0],
            "sonnenaufgang": heute["sunrise"][0][-5:],     # nur HH:MM
            "sonnenuntergang": heute["sunset"][0][-5:],
        },
    }


# Damit man diese Datei auch einzeln testen kann:
if __name__ == "__main__":
    wetter = hole_wetter(50.00, 8.99, "Europe/Berlin")
    print(wetter)
