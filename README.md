# TalkToMe — KI-Coaching mit LiveAvatar

Eine interaktive Coaching-Plattform für Kommunikationstraining. Nutzer üben Gespräche mit einem KI-Avatar (Heygen) und erhalten eine KI-gestützte Analyse ihrer Kommunikationsfähigkeiten (DeepSeek).


## Übersicht

Die App ermöglicht Führungskräften, Mitarbeitern und Privatpersonen, schwierige Gespräche in einem realistischen Rollenspiel zu üben:

1. **Szenario wählen** — 10 Trainingsszenarien aus den Bereichen Arbeit, Privat, Training
2. **Mit Avatar sprechen** — Der Heygen LiveAvatar spielt die Rolle des Gegenübers (Chef, Kunde, Partner etc.)
3. **Analyse erhalten** — DeepSeek bewertet die Kommunikation des Nutzers nach Empathie, Klarheit und Ergebnisorientierung

## Tech Stack

| Komponente | Technologie |
|---|---|
| **Backend** | Python 3.12, FastAPI, Modal (serverless GPU) |
| **Avatar** | Heygen LiveAvatar API (interaktiver KI-Avatar) |
| **Analyse** | DeepSeek Chat ($0.44/$0.87 pro M tokens) |
| **ASR** | NVIDIA Parakeet TDT 0.6b v2 (GPU-Transkription) |
| **Frontend** | React (TypeScript), Vite, Lucide Icons |
| **Infrastruktur** | Modal L40S GPU, Serverless Functions |

## Szenarien

### Arbeit
- **Feedbackgespräch** — Mitarbeiter Alex braucht konstruktives Feedback
- **Gehaltsverhandlung** — Verhandlung mit Abteilungsleiter Dr. Meier
- **Kundenbeschwerde** — Verärgerter Kunde mit defektem Produkt
- **Konflikt mit Kollege** — Kollege Chris hat eine Idee gestohlen
- **Präsentation vor Geschäftsleitung** — CFO Frau Wagner hinterfragt Zahlen

### Privat
- **Beziehungsgespräch** — Unterschiedliche Zukunftsvorstellungen
- **Nachbarschaftskonflikt** — Lärmbelästigung bei Rentner Müller
- **Elterngespräch** — Lehrkraft Frau Schmidt sorgt sich ums Kind
- **Arztgespräch** — Dr. Berger unter Zeitdruck

### Training
- **Freies Coaching** — Offenes Kommunikationstraining mit Coach

Jedes Szenario hat dynamische Avatar-Reaktionen: Der Avatar reagiert unterschiedlich je nachdem, ob der Nutzer empathisch oder anklagend kommuniziert.

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
- Heygen API Key (für LiveAvatar)
- DeepSeek API Key (für Analyse)

### Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install modal fastapi[standard] python-multipart openai requests
```

### Modal Secrets
In Modal müssen drei Secrets angelegt werden:
- `heygen-api-key` — `HEYGEN_API_KEY`
- `my-deepseek-secret` — `DEEPSEEK_API_KEY`

### Build & Deploy
```bash
cd frontend && npm install && npm run build
cd ..
modal deploy transcribe_demo.py
```

## Projektstruktur

```
asr_demo/
├── transcribe_demo.py    # Main App: FastAPI, Modal Functions, Heygen-Integration
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
| `/api/session/status` | GET | Heygen-Setup-Status |
| `/api/heygen/setup` | GET | Heygen-Ressourcen neu initialisieren |
| `/api/transcribe` | POST | Audio-Transkription + Analyse |

## Heygen-Ressourcen

Beim ersten Start (`/api/heygen/setup`) werden automatisch angelegt:
- **Secret**: DeepSeek API Key (als `OPENAI_API_KEY` Secret-Type)
- **LLM Configuration**: DeepSeek Chat mit OpenAI-kompatiblem Endpunkt
- **Contexts**: Pro Szenario ein Avatar-Kontext mit System-Prompt, Eröffnungstext und Voice


