# Power-Automate-Flow „Praxis Vibes KPI-Mail"

Der Flow holt alle zwei Wochen die fertige Mail vom Dashboard und verschickt sie aus Kilians Outlook. Die Empfänger stehen nur im Flow, nicht im öffentlichen Repo.

## Aufbau

1. **Trigger „Wiederholung"**
   - Intervall `2`, Häufigkeit `Woche`
   - An diesen Tagen: `Montag`, Zu diesen Stunden: `8`, Minuten: `0`
   - Zeitzone: `(UTC+01:00) Amsterdam, Berlin, …`
   - Startzeit: `2026-11-02T08:00:00` (erste Mail deckt KW 43–44 ab)

2. **Aktion „HTTP"**
   - Methode `GET`
   - URI: `https://kiliankimojo.github.io/praxis-vibes-dashboard/mail.json?t=@{ticks(utcNow())}`
     (der Zusatz `?t=` umgeht den Zwischenspeicher von GitHub Pages)

3. **Aktion „Bedingung"** – sind die Daten frisch?
   - Links: `@{body('HTTP')?['period']?['end']}`
   - ist gleich
   - Rechts: `@{formatDateTime(addDays(convertFromUtc(utcNow(), 'W. Europe Standard Time'), -1), 'yyyy-MM-dd')}`

4. **Wenn ja → „E-Mail senden (V2)"** (Office 365 Outlook)
   - An: Kilian, Laura, Steffen (weitere nach Absprache)
   - Betreff: `@{body('HTTP')?['subject']}`
   - Text: in die Code-Ansicht `</>` wechseln und `@{body('HTTP')?['html']}` einfügen
   - Wichtigkeit: Normal

5. **Wenn nein → „E-Mail senden (V2)"** nur an Kilian
   - Betreff: `Praxis Vibes KPI-Mail: Daten nicht aktuell`
   - Text: `Der Wochenabruf in GitHub ist nicht gelaufen oder fehlgeschlagen. Bitte unter Actions → Wochenabruf prüfen. Stand der Daten: @{body('HTTP')?['period']?['end']}`

## Testen

Im Flow „Testen" → „Manuell". Vorher den Empfänger der Ja-Mail testweise auf Kilian allein stellen.

## Hinweise aus der Erfahrung mit dem neuen Designer

- Ausdrücke über das fx-Feld eingeben und „Hinzufügen" zweimal klicken.
- Das Ergebnis in der Codeansicht prüfen.
- Die Aktion „HTTP" ist ein Premium-Connector. Sie ist im KIMOJO-Tenant schon im Einsatz.
