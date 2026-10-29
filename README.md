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
Voraussetzung: @praxis.vibes ist ein öffentliches Business- oder Creator-Konto (Instagram → Einstellungen → Kontotyp und Tools).
1. Auf developers.facebook.com/apps „App erstellen" wählen. Anwendungsfall „Andere", App-Typ „Business", Name z. B. „Praxis Vibes Dashboard".
2. Beim Produkt „Instagram" auf „Einrichten" klicken. „API-Einrichtung mit Instagram-Login" wird automatisch hinzugefügt.
3. Unter Berechtigungen nur `instagram_business_basic` und `instagram_business_manage_insights` behalten, den Rest abwählen.
4. Unter „Instagram → API-Einrichtung mit Instagram Business Login" das Konto @praxis.vibes hinzufügen, mit dessen Zugang einloggen und „Token generieren" klicken. Der Token gilt 60 Tage.
5. Die App bleibt im Entwicklungsmodus. Für das eigene Konto ist keine App-Prüfung durch Meta nötig.
6. Den Token im Repo unter Settings → Secrets and variables → Actions → „New repository secret" als `IG_ACCESS_TOKEN` speichern.
7. Damit der Token nie abläuft: unter github.com/settings/personal-access-tokens/new einen fein granulierten Token anlegen. Repository access „Only select repositories" mit diesem Repo, Berechtigung Repository → „Secrets: Read and write", Ablauf 1 Jahr. Als Secret `GH_SECRETS_TOKEN` speichern. Der Wochenlauf verlängert und speichert den Instagram-Token dann selbst.
8. Actions → Wochenabruf → „Run workflow" mit `backfill` = `12`. Das holt die letzten zwölf Wochen nach, mehr hält Instagram nicht vor.

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
