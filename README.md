# Praxis Vibes Reichweiten-Dashboard

Zeigt Podcast-Wiedergaben und Instagram-Reichweite von Praxis Vibes. Die Daten werden jeden Montag automatisch abgerufen. Alle zwei Wochen geht eine KPI-Mail an das Team. Hintergrund und Kennzahlen stehen im internen Konzept (KONZEPT.md im OneDrive-Ordner, nicht im Repo).

## Ordner

| Pfad | Inhalt |
|---|---|
| `pipeline/` | Python-Skripte: Abruf, Excel-Import, Aufbau von Dashboard und Mail |
| `data/` | Wochenhistorie, Folgenliste, Status der Quellen |
| `docs/` | Die Dashboard-Seite, die GitHub Pages ausliefert, plus `mail.json` |
| `config/ziele.json` | Zielwerte aus dem Workshop und Adresse des Dashboards |
| `.github/workflows/` | Der wöchentliche Lauf |
| `power-automate/` | Anleitung für den Mail-Flow |

## Einrichtung

### 1. Repo und Seite
1. Auf GitHub als `KilianKIMOJO` ein Repo `praxis-vibes-dashboard` anlegen und diesen Ordner hochladen.
2. Settings → Pages → „Deploy from a branch" → Branch `main`, Ordner `/docs`.
3. Settings → Actions → General → Workflow permissions auf „Read and write" stellen.
4. Stimmt die Adresse nicht mit `config/ziele.json` überein, dort `dashboard_url` anpassen.

### 2. Instagram
Der Abruf erkennt am Token selbst, welche der beiden Meta-Varianten genutzt wird. Seit Oktober 2026 bietet Meta neuen Apps oft nur noch die Variante mit Facebook-Login an, deshalb ist sie hier der Standard.

**Variante Facebook-Login (Standard, Token läuft nie ab)**
1. @praxis.vibes muss ein Business- oder Creator-Konto sein und mit einer Facebook-Seite verknüpft sein, auf der du Admin bist.
2. Auf developers.facebook.com/apps eine App mit dem Anwendungsfall „Messaging und Content auf Instagram verwalten" anlegen. Unter „Anwendungsfälle → Anpassen → Berechtigungen und Features" diese Berechtigungen hinzufügen: `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`. Liegt die Seite in einem Business-Portfolio, zusätzlich `business_management`.
3. Im Graph API Explorer (developers.facebook.com/tools/explorer) die App wählen, „Nutzer-Token" einstellen, die Berechtigungen aus Schritt 2 anhaken und „Generate Access Token" klicken. Im Dialog die Seite und @praxis.vibes freigeben.
4. Im Access Token Debugger (developers.facebook.com/tools/debug/accesstoken) den Token einfügen, „Debuggen" und dann „Zugriffsschlüssel verlängern" klicken. Den langlebigen Token kopieren.
5. Zurück im Explorer den langlebigen Token einsetzen und `me/accounts?fields=name,access_token` abfragen. Den `access_token` der Praxis-Vibes-Seite kopieren. Im Debugger prüfen, dass dort „Läuft ab: Nie" steht.
6. Diesen Seiten-Token als Secret `IG_ACCESS_TOKEN` speichern (Settings → Secrets and variables → Actions → „New repository secret"). `GH_SECRETS_TOKEN` ist bei dieser Variante nicht nötig.

**Variante Instagram-Login (falls Meta sie anbietet, Token gilt 60 Tage)**
1. App mit dem Anwendungsfall „Messaging und Content auf Instagram verwalten" anlegen, beim Anpassen „API-Einrichtung mit Instagram-Login" wählen.
2. Nur `instagram_business_basic` und `instagram_business_manage_insights` behalten, das Konto hinzufügen und „Token generieren".
3. Token als Secret `IG_ACCESS_TOKEN` speichern.
4. Zusätzlich einen fein granulierten GitHub-Token mit „Secrets: Read and write" nur für dieses Repo als `GH_SECRETS_TOKEN` speichern. Dann verlängert der Wochenlauf den Instagram-Token selbst.

**Danach:** Actions → Wochenabruf → „Run workflow" mit `backfill` = `12`. Das holt die letzten zwölf Wochen nach, mehr hält Instagram nicht vor. Die App bleibt in beiden Varianten im Entwicklungsmodus, für das eigene Konto ist keine App-Prüfung nötig.

### 3. Spotify for Creators
Spotify hat keine offizielle Statistik-Schnittstelle. Der Abruf nutzt die Sitzungs-Cookies eines eingeloggten Kontos.
1. Empfohlen: ein eigenes Spotify-Konto anlegen und in Spotify for Creators ins Team von Praxis Vibes einladen, nur mit Leserechten.
2. Mit diesem Konto auf creators.spotify.com einloggen.
3. Entwicklertools öffnen → Application → Cookies → `https://accounts.spotify.com`.
4. Die Werte von `sp_dc` und `sp_key` als Secrets `SPOTIFY_SP_DC` und `SPOTIFY_SP_KEY` speichern.
5. Die Cookies halten einige Monate. Läuft der Zugang ab, zeigt das Dashboard „Spotify aus Excel" und die Schritte 2 bis 4 werden wiederholt.

### 4. Erster Lauf
1. Actions → Wochenabruf → „Run workflow", bei `backfill` den Wert `4` eintragen. Das füllt die letzten Wochen mit Instagram-Daten nach.
2. Danach im Dashboard oben prüfen, ob beide Quellen „automatisch" zeigen.
3. Unter dem Lauf liegt der Anhang „rohdaten". Beim ersten Spotify-Abruf dort prüfen, ob die Wiedergaben richtig erkannt wurden. Der Status zeigt die gefundenen Felder. Falls nötig, die Muster `KEYS` in `pipeline/fetch_spotify.py` anpassen.

### 5. Mail
Den Flow nach [power-automate/flow-anleitung.md](power-automate/flow-anleitung.md) anlegen.

### 6. Ziele
Die Zielwerte aus dem Workshop in `config/ziele.json` eintragen. Das Dashboard zeigt dann Fortschritt und Ampel.

## Lokal arbeiten

Historie aus dem Excel nachladen und alles neu aufbauen:
```bash
python3 -I pipeline/run_weekly.py --no-fetch --excel "../../06_Marketing & Kommunikation/Marketing/0_Orga/KPI Tracking/KPI-Tracking.xlsx"
```

Nur Dashboard und Mail neu erzeugen:
```bash
python3 -I pipeline/build.py
```

Der Excel-Import überschreibt nie Werte, die schon per API abgerufen wurden.

## Wenn etwas nicht läuft

| Anzeichen | Ursache | Lösung |
|---|---|---|
| Chip „Instagram aus Excel" | Token fehlt oder abgelaufen | Neuen Token erzeugen, Secret ersetzen |
| Hinweis „Instagram-Zugang läuft ab" | `GH_SECRETS_TOKEN` fehlt | Secret anlegen oder Token von Hand erneuern |
| Chip „Spotify aus Excel" | Cookies abgelaufen oder Spotify hat die Schnittstelle geändert | Cookies erneuern, sonst `spotifygraphqlconnector` aktualisieren |
| Mail „Daten nicht aktuell" | Wochenlauf fehlgeschlagen | GitHub → Actions → letzten Lauf ansehen |
