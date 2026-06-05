# TalkToMe — KI-Coaching mit Tavus

Eine interaktive Coaching-Plattform für Kommunikationstraining. Nutzer üben fokussierte Business-Gespräche mit einem KI-Avatar (Tavus) und erhalten eine KI-gestützte Analyse ihrer Kommunikationsfähigkeiten.

## Demo

Modal Dashboard: https://modal.com/apps/aliundmaggy/main

Frontend: https://aliundmaggy--asr-coaching-analysis-fastapi-app.modal.run/


## Übersicht

Die App ermöglicht zwei bewusst fokussierte Demo-Flows, die in Portfolio-Präsentationen schnell verständlich sind:

1. **Szenario wählen** — Gehaltsverhandlung oder Kundenbeschwerde
2. **Trainingsrolle wählen** — Nutzer entscheidet vorab, welche Gesprächsseite er trainiert
3. **Mit Avatar sprechen** — Tavus spielt konsequent die Gegenseite
4. **Analyse erhalten** — die KI bewertet das echte Gesprächstranskript nach Empathie, Klarheit und Ergebnisorientierung

## Tech Stack

| Komponente | Technologie |
|---|---|
| **Backend** | Python 3.12, FastAPI, Modal (serverless GPU) |
| **Avatar** | Tavus Conversational Video Interface |
| **Analyse** | DeepSeek Chat, optional Gemini-Fallback |
| **ASR** | NVIDIA Parakeet TDT 0.6b v2 (GPU-Transkription) |
| **Frontend** | React (TypeScript), Vite, Lucide Icons |
| **Infrastruktur** | Modal L40S GPU, Serverless Functions |

## Szenarien

### Gehaltsverhandlung
- **Mitarbeiter trainieren** — Nutzer verhandelt eine Gehaltserhöhung mit Abteilungsleiter Dr. Meier.
- **Führungskraft trainieren** — Nutzer reagiert als Manager fair und budgetbewusst auf eine Gehaltsforderung.

### Kundenbeschwerde
- **Service trainieren** — Nutzer beruhigt eine verärgerte Kundin und findet eine verbindliche Lösung.
- **Kunde trainieren** — Nutzer bringt eine Beschwerde klar, bestimmt und lösungsorientiert vor.

Jede Rollenoption erzeugt eine eigene Tavus-Persona mit versioniertem System-Prompt plus `conversational_context` pro Session. Dadurch weiß der Avatar immer, welche Rolle er spielt und welche Rolle der Nutzer trainiert.

## Analyse-Dimensionen

Die DeepSeek-Analyse bewertet den Nutzer nach drei Kern-Dimensionen:

1. **Empathie & Emotionale Intelligenz** (1-10) — Aktives Zuhören, Emotionserkennung, Tonfall-Anpassung
2. **Sprachliche Klarheit & Struktur** (1-10) — Roter Faden, Präzision, Gesprächsaufbau
3. **Ergebnisorientierung & Zielführung** (1-10) — Zielverfolgung, Abschlussstärke, Flexibilität

Jeder Score wird mit wörtlichen Zitaten aus den Nutzer-Aussagen belegt. Die Avatar-Aussagen dienen nur als Kontext — bewertet wird ausschließlich der menschliche Nutzer.

## Setup & Deployment

### Voraussetzungen
- Python 3.12+
- Node.js & npm
- Modal Account (`pip install modal && modal setup`)
- Tavus API Key (für Conversational Video)
- DeepSeek API Key oder Gemini API Key (für Analyse)

### Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install modal fastapi[standard] python-multipart openai requests
```

### Modal Secrets
In Modal müssen diese Secrets angelegt werden:
- `Tavus` — `TAVUS_API_KEY`
- `my-deepseek-secret` — `DEEPSEEK_API_KEY`
- `my-gemini-secret` — `GEMINI_API_KEY` (Fallback, wenn DeepSeek kein Guthaben hat)

Der Code unterstützt für Tavus zusätzlich die Legacy-Variable `TAURUS_API_KEY`, weil diese in einer früheren Modal-Secret-Version versehentlich so benannt war. Für neue Secrets sollte `TAVUS_API_KEY` verwendet werden.

Aktueller Diagnosebefund: `my-deepseek-secret` ist vorhanden, aber DeepSeek antwortet mit `402 Insufficient Balance`. Wenn DeepSeek wieder primär genutzt werden soll, muss Guthaben auf den DeepSeek-Account geladen oder der Key im Modal Secret `my-deepseek-secret` als `DEEPSEEK_API_KEY` ersetzt werden.

Optional kann `TAVUS_DEFAULT_REPLICA_ID` gesetzt werden. Ohne diese Variable verwendet die App die Replica `r90bbd427f71`.

### Build & Deploy
```bash
cd frontend && npm ci && npm run build
cd ..
modal deploy transcribe_demo.py
```

## Projektstruktur

```
asr_demo/
├── transcribe_demo.py    # Modal/FastAPI Entry Point
├── coach_app/            # Szenarien, Tavus-Client, Security, Analyse-Helpers
├── frontend/             # React SPA
│   ├── src/
│   │   ├── App.tsx        # Main layout + navigation
│   │   └── CoachAvatar.tsx # Avatar-Komponente, Szenario-Auswahl, Analyse-Display
│   └── dist/              # Build-Output (wird nach Modal deployed)
├── samples/              # Test-Audiodateien
├── scratch/              # Experimente
└── .env.local            # Lokale Secrets (nicht in git)
```

## API Endpunkte

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/api/scenarios` | GET | Alle Trainingsszenarien |
| `/api/session/create` | POST | Neue Avatar-Session starten |
| `/api/session/analyze` | POST | Session analysieren |
| `/api/session/status` | GET | Tavus-Setup-Status |
| `/api/tavus/setup` | POST | Tavus-Personas initialisieren, nur mit `X-Admin-Token` |
| `/api/transcribe` | POST | Audio-Transkription + Analyse |

## Tavus-Ressourcen

Die App erstellt pro Szenario und Trainingsrolle eine Tavus-Persona und nutzt diese mit der konfigurierten Replica für Live-Conversations. Das Setup wird serverseitig ausgeführt und ist nicht aus dem Browser heraus öffentlich triggerbar.

Beim Klick auf **Beenden & Analysieren** wird die Tavus-Conversation serverseitig beendet und anschließend mit `verbose=true` abgefragt, damit das End-of-call-Transkript aus `application.transcription_ready` analysiert wird.

## Qualitätschecks

```bash
cd frontend && npm run build
cd ..
python -m unittest discover -s tests
python -m py_compile transcribe_demo.py
```
