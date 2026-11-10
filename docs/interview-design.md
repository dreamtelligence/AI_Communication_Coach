# Vorstellungsgespräch: Recherche und Umsetzung

Stand: 10. November 2026. Fokus: Bewerbende für Fullstack-Entwicklung mit KI-Anwendungen. Das Szenario ist ein Übungsinterview, kein Instrument zur Auswahl realer Bewerbender.

## Quellen und daraus abgeleitete Gestaltung

- [Bundesagentur für Arbeit: Vorstellungsgespräch und Auswahltests](https://www.arbeitsagentur.de/arbeitslos-arbeit-finden/bewerbungstraining/vorstellungsgespraech-und-auswahltests), am 10.11.2026 gelesen: Gesprächsvorbereitung, berufliche Selbstvorstellung, Motivation, Arbeitgeberinformationen, eigene Fragen und nächste Schritte. Umsetzung: ein vollständiger Gesprächsbogen einschließlich tatsächlicher Gelegenheit für Rückfragen.
- [U.S. OPM: Structured Interviews](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/) und [Practical Guide, September 2008](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/guide.pdf), am 10.11.2026 gelesen: arbeitsbezogene Kompetenzen, vergleichbare Kernfragen, vergangenes Verhalten und hypothetische Situationen, gezielte Nachfragen, Verhaltensanker und typische Bewertungsfehler. Umsetzung: feste Reihenfolge mit begrenzten individuellen Nachfragen und getrennte Bewertung der drei Bereiche. Der Leitfaden liefert die Methode; unsere konkrete Rolle und 1–10-Anker sind eigene Produktentscheidungen und wurden nicht psychometrisch validiert.
- [Antidiskriminierungsstelle des Bundes: Was Arbeitgeber fragen (dürfen)](https://www.antidiskriminierungsstelle.gov.de/SharedDocs/downloads/DE/publikationen/Expertisen/was_arbeitgeber_fragen_duerfen.pdf?__blob=publicationFile&v=5), am 10.11.2026 gelesen: diskriminierungssensible Gestaltung und problematische persönliche Fragen. Umsetzung: keine Fragen nach geschützten oder privaten Merkmalen und keine Ableitung fachlicher Eignung daraus. Der ältere Forschungsbericht ersetzt keine aktuelle Rechtsberatung; das Trainingsszenario vermeidet solche Fragen vollständig.

## Konkreter Gesprächsrahmen

Die Nordlicht Software GmbH ist erfunden. Das Briefing ist vor und während des Anrufs sichtbar und liegt auch dem Avatar und der Analyse vor. Es beschreibt eine B2B-Serviceplattform, React/TypeScript, Python- oder Node-APIs, SQL, KI-Integration, Tests, Datenschutz und Zusammenarbeit. Quereinstieg und eigene Projekte sind ausdrücklich zugelassen.

Dr. Meier ist derselbe bestehende Charakter mit demselben Gesicht und Porträt. Für das Interview erhält er einen eigenen PAL mit eigenen Gesprächsregeln. Gehaltsverhandlung und Kundenbeschwerde verwenden ihre bisherigen Prompts. Das Date-Szenario bleibt intern erhalten, wird auf ausdrücklichen Nutzerwunsch aber nicht mehr in der öffentlichen B2B-Demo angeboten.

| Reihenfolge | Kernfrage / Zweck | Geeignete Nachfrage |
| --- | --- | --- |
| 1 | Beruflicher Weg und Bezug zur Stelle | Welche Aufgabe interessiert Sie konkret? |
| 2 | Eigenes umgesetztes Webprojekt | Eigene Entscheidung, Alternative, Prüfung, beobachtetes Ergebnis |
| 3 | KI-Assistent mit internen Kundendaten | Berechtigungen, Antwortqualität oder Fehlerfall |
| 4 | Fehleranalyse | Eingrenzung, Absicherung, Verifikation und Kommunikation |
| 5 | Feedback und Zusammenarbeit | Konkrete Änderung oder ausdrücklich hypothetisches Vorgehen |
| 6 | Fragen der bewerbenden Person | Arbeitgeber antwortet, danach organisatorische Klärung und Abschluss |

Nachfragen greifen tatsächliche Antworten auf; maximal zwei je Kernfrage. Das ist ein strukturiertes Training mit adaptiven Nachfragen, kein streng standardisiertes Auswahlinterview. Der Avatar kennt keinen Lebenslauf und kann GitHub nicht selbst ansehen. Neue Informationen dürfen nur aus den Antworten kommen. Nicht festgelegte Firmeninformationen bleiben offen. Es gibt keine Einstellungsentscheidung.

## Bewertungsmodell

| Anzeige | Bestehendes API-Feld | Beobachtbare Grundlage |
| --- | --- | --- |
| Stellenbezug | `empathy_score` | Bezug zwischen Motivation, Aufgaben und eigener Erfahrung; reflektierte Zusammenarbeit |
| Klarheit | `clarity_score` | Relevante, verständliche Antworten; nachvollziehbarer eigener Beitrag; passende Rückfragen |
| Fachliche Substanz | `result_score` | Begründete Entscheidungen, Problemlösen, Tests und verantwortlicher Umgang mit KI und Daten |

Die historischen API-Feldnamen bleiben kompatibel. Für jedes Kriterium stehen im Szenario fünf beschriebene Leistungsbereiche von 1–2 bis 9–10. Gute Rhetorik darf keine unsichere technische Lösung aufwerten. Hypothetische Antworten werden von berichteter Erfahrung unterschieden; beides bleibt ungeprüfter Selbstbericht.

Jede vergebene Note verlangt ein wörtliches Nutzerzitat in `evidence`. Der Server prüft dieses gegen die Teilnehmeraussagen und ergänzt den verifizierten Beleg im sichtbaren Feedback. Fehlende, erfundene, dem Avatar gehörende oder als Erkennungsfehler markierte Belege führen zu `null`. Ungültige Noten werden nicht auf einen scheinbar gültigen Wert gekürzt. Die Oberfläche zeigt dann „Nicht beurteilbar“ ohne Punktanzeige oder Messbalken. Fehlende Fragen oder ein abgebrochener Anruf sind keine Nullleistung.

Die Prüfung sichert die Herkunft eines Zitats, nicht dessen inhaltliche Eignung als Beleg. Ob ein Zitat die Wertung tatsächlich trägt, bleibt eine Modellentscheidung. Transkriptanweisungen werden im Prompt als unzuverlässige Daten behandelt; das ist keine Garantie gegen Prompt Injection. Es gibt keine Ableitung von Emotion, Persönlichkeit oder Eignung aus Bild oder Stimme. Verbesserungsvorschläge dürfen keine erfundenen Lebenslaufdaten enthalten.

## Prüfung und Grenzen

Die Unit-Tests prüfen Payloads, Stellenbriefing, Gesprächseinstieg, Quote-Validierung, ASR-Ausschluss, ungültige Scores, fehlende Antworten und das Ende längerer Transkripte. Sie prüfen keine Gesprächsqualität eines echten Avatars.

`scripts/evaluate_interview.py` ruft den echten Gemini-Anbieter mit fünf versionierten fiktiven Transkripten auf: konkret, vage, selbstbewusst/unsicher, abgebrochen, nur Avatar. Die Erwartungsbereiche sind bewusst breite Regressionserwartungen unserer Umsetzung. Ein bestandener Lauf ist keine Studie zu Fairness, Wiederholbarkeit oder Einstellungsprognosen. Der Aufruf kostet Anbieterressourcen und läuft nicht automatisch in CI:

```bash
# GEMINI_API_KEY sicher in der Prozessumgebung bereitstellen, nicht einchecken.
PYTHONPATH=. .venv/bin/python scripts/evaluate_interview.py
```

Der Live-Pfad bleibt Browser → FastAPI → Tavus → End-of-call-Transkript → Analyseanbieter → serverseitige Belegprüfung → Oberfläche. Die Audio-Upload-Funktion behält ihre allgemeine Auswertung; sie bietet keine Auswahl dieses Interviews. Es werden keine Lebenslaufdateien, Arbeitgeberdatenbanken, Recruiter-Zugänge oder Trainingshistorien hinzugefügt.

Vor einer Abnahme als authentisches Live-Interview muss eine Person mit Mikrofon den Gesprächsbogen, Denkpausen, sinnvolle Nachfragen, Rückfragenphase, Auflegen und anschließende Bewertung durchspielen. Technische Tests und fiktive Textfälle ersetzen diese Prüfung nicht.
