import modal
import os
import json
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Define the Modal App
app = modal.App("asr-coaching-analysis")

# Configuration
MODAL_NAME = "nvidia/parakeet-tdt-0.6b-v2"
CUDA_TAG = "12.4.1-devel-ubuntu22.04"
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
HEYGEN_API_BASE = "https://api.liveavatar.com"

# Heygen resource IDs (cached in memory after first setup)
heygen_secret_id = None
heygen_llm_config_id = None
heygen_contexts = {}  # scenario_id -> context_id
heygen_avatar_id = "073b60a9-89a8-45aa-8902-c358f64d2852"

LIVE_COACH_SYSTEM_PROMPT = """Du bist {avatar_role}

DEIN VERHALTEN:
- Antworte immer auf Deutsch, natürlich und menschlich
- Reagiere emotional authentisch auf das was der Nutzer sagt
- Bleibe konsequent in deiner Rolle, brich nie aus ihr aus
- Antworten max. 2-3 Sätze — das ist ein Gespräch, kein Monolog
- Warte auf Reaktion, dränge nicht

DEIN ZIEL ALS GESPRÄCHSPARTNER:
- Mache es dem Nutzer nicht zu leicht
- Reagiere realistisch: Emotionen, Widerstände, Missverständnisse
- Eskaliere leicht wenn der Nutzer keine Empathie zeigt
- Deeskaliere wenn der Nutzer es gut macht

WICHTIG:
- Du weißt nicht dass du eine KI bist — bleib immer in der Rolle
- Kein Coaching-Feedback während des Gesprächs — das kommt danach
"""

# Communication training scenarios
SCENARIOS = [
    {
        "id": "feedback",
        "title": "Mitarbeiter-Feedbackgespräch",
        "category": "Arbeit",
        "icon": "briefcase",
        "description": "Du bist Führungskraft und musst einem Mitarbeiter Feedback zu seiner Leistung geben.",
        "avatar_role": "Du bist der Mitarbeiter Alex, der seit 3 Jahren im Team ist. Du bist grundsätzlich engagiert, aber in letzter Zeit oft zu spät gekommen und hast zwei Deadlines verpasst. Du bist nervös wegen des Gesprächs.",
        "user_goal": "Führe ein konstruktives Feedbackgespräch mit Empathie. Adressiere die Probleme klar, aber wertschätzend. Erarbeite gemeinsam eine Lösung."
    },
    {
        "id": "salary",
        "title": "Gehaltsverhandlung",
        "category": "Arbeit",
        "icon": "dollar",
        "description": "Du verhandelst mit deinem Vorgesetzten über eine Gehaltserhöhung.",
        "avatar_role": "Du bist der Abteilungsleiter Dr. Meier. Du hast Budget für Gehaltsanpassungen, bist aber unter Druck vom Management, Kosten zu sparen. Du schätzt den Mitarbeiter sehr.",
        "user_goal": "Argumentiere selbstbewusst für deine Gehaltserhöhung mit konkreten Leistungen. Bleibe sachlich und ergebnisorientiert."
    },
    {
        "id": "complaint",
        "title": "Kundenbeschwerde",
        "category": "Arbeit",
        "icon": "message-circle",
        "description": "Ein verärgerter Kunde beschwert sich über ein fehlerhaftes Produkt.",
        "avatar_role": "Du bist ein verärgerter Kunde, der viel Geld für ein Premium-Produkt ausgegeben hat, das defekt ist. Du bist emotional und fordernd, willst aber eigentlich nur ernst genommen werden und eine Lösung.",
        "user_goal": "Beruhige den Kunden mit Empathie. Finde eine klare Lösung und sorge für ein positives Ergebnis."
    },
    {
        "id": "conflict_colleague",
        "title": "Konflikt mit Kollegen",
        "category": "Arbeit",
        "icon": "users",
        "description": "Ein Kollege hat deine Idee im Meeting als seine ausgegeben.",
        "avatar_role": "Du bist Chris, ein ehrgeiziger Kollege. Du hast die Idee tatsächlich übernommen, weil du unter Druck stehst und Anerkennung suchst. Du fühlst dich jetzt ertappt und bist defensiv.",
        "user_goal": "Spreche den Konflikt offen aber respektvoll an. Fokussiere auf die gemeinsame Zusammenarbeit."
    },
    {
        "id": "presentation",
        "title": "Projektpräsentation",
        "category": "Arbeit",
        "icon": "trending-up",
        "description": "Du präsentierst ein neues Projekt vor der Geschäftsleitung.",
        "avatar_role": "Du bist Frau Wagner, die CFO. Du bist kritisch und hinterfragst Zahlen. Du willst ROI-Details sehen, bevor du zustimmst.",
        "user_goal": "Präsentiere klar und strukturiert. Gehe auf kritische Fragen ein und bleibe ergebnisorientiert."
    },
    {
        "id": "relationship",
        "title": "Beziehungsgespräch",
        "category": "Privat",
        "icon": "heart",
        "description": "Du möchtest mit deinem Partner über eure Zukunftspläne sprechen.",
        "avatar_role": "Du bist der/die Partner/in. Du liebst deinen Partner, hast aber andere Vorstellungen von der Zukunft. Du willst verstanden werden.",
        "user_goal": "Führe ein empathisches Gespräch über Zukunftswünsche. Höre aktiv zu und finde Gemeinsamkeiten statt Unterschiede."
    },
    {
        "id": "neighbor",
        "title": "Nachbarschaftsgespräch",
        "category": "Privat",
        "icon": "home",
        "description": "Dein Nachbar beschwert sich seit Wochen über Lärm.",
        "avatar_role": "Du bist Nachbar Müller, Rentner, lebst allein. Der Lärm des Nachbarn stört deinen Schlaf. Du bist eigentlich ein freundlicher Mensch, aber zunehmend frustriert.",
        "user_goal": "Deeskaliere die Situation. Zeige Verständnis und finde eine pragmatische Lösung für beide Seiten."
    },
    {
        "id": "parents",
        "title": "Elterngespräch in der Schule",
        "category": "Privat",
        "icon": "book-open",
        "description": "Die Lehrerin hat dich zum Gespräch über dein Kind eingeladen.",
        "avatar_role": "Du bist Frau Schmidt, die Klassenlehrerin. Du machst dir Sorgen um das Kind, das sich zurückzieht. Du willst mit den Eltern kooperativ eine Lösung finden.",
        "user_goal": "Bleibe offen für Feedback. Zeige Kooperationsbereitschaft und entwickle gemeinsam einen Plan zur Unterstützung des Kindes."
    },
    {
        "id": "doctor",
        "title": "Arztgespräch",
        "category": "Privat",
        "icon": "activity",
        "description": "Du hast gesundheitliche Beschwerden und musst diese dem Arzt klar schildern.",
        "avatar_role": "Du bist Dr. Berger, ein vielbeschäftigter Hausarzt. Du hast nur 10 Minuten Zeit und brauchst präzise Informationen, um eine Diagnose zu stellen.",
        "user_goal": "Beschreibe deine Symptome klar und strukturiert. Stelle die richtigen Fragen zur Behandlung."
    },
    {
        "id": "free",
        "title": "Freies Coaching",
        "category": "Training",
        "icon": "zap",
        "description": "Freies Kommunikationstraining mit dem TalkToMe Coach.",
        "avatar_role": "Du bist ein professioneller Kommunikations-Coach. Du hilfst dem Nutzer, seine Kommunikationsfähigkeiten zu verbessern.",
        "user_goal": "Trainiere deine Kommunikationsfähigkeiten in einem offenen Gespräch."
    }
]

# Create a volume for model caching
nemo_cache = modal.Volume.from_name("nemo-model-cache", create_if_missing=True)
CACHE_DIR = "/cache"

# Define the container image
image = (
    modal.Image.from_registry(f"nvidia/cuda:{CUDA_TAG}", add_python="3.12")
    .apt_install("libsndfile1", "ffmpeg")
    .pip_install(
        "nemo_toolkit[asr]",
        "torchaudio",
        "soundfile",
        "fastapi[standard]",
        "python-multipart",
        "openai",
        "requests"
    )
    .env({"NEMO_CACHE_DIR": CACHE_DIR})
    .add_local_dir(
        os.path.join(os.path.dirname(__file__), "frontend", "dist"),
        remote_path="/assets"
    )
)


@app.cls(
    gpu="L40S",
    image=image,
    timeout=600,
    scaledown_window=60,
    volumes={CACHE_DIR: nemo_cache}
)
class BatchTranscription:
    @modal.enter()
    def setup(self):
        import nemo.collections.asr as nemo_asr
        self.asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODAL_NAME)

    @modal.method()
    def transcribe_bytes(self, audio_data: bytes):
        import tempfile
        import torchaudio
        import torch
        import soundfile as sf

        print("Starting transcription (v4 - using soundfile for I/O)")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        try:
            data, sample_rate = sf.read(tmp_path)
            waveform = torch.from_numpy(data).float()
            if len(waveform.shape) == 1:
                waveform = waveform.unsqueeze(0)
            else:
                waveform = waveform.T

            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
                sample_rate = 16000

            sf.write(tmp_path, waveform.squeeze().numpy(), sample_rate)
            hypotheses = self.asr_model.transcribe([tmp_path], batch_size=1, verbose=False)

            if not hypotheses:
                return ""

            hyp = hypotheses[0]
            if isinstance(hyp, str):
                return hyp
            return hyp.text if hasattr(hyp, 'text') else str(hyp)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("my-gemini-secret")]
)
def analyze_transcript(text: str):
    """Analyze transcript with Gemini (free tier) via OpenAI-compatible endpoint."""
    from openai import OpenAI

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "Gemini API key not found in secrets."}

    client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)

    prompt = f"""
    Du bist ein Experte fuer Coaching-Analyse. Analysiere das folgende Transkript eines Gespraechs
    hinsichtlich der drei TalkToMe-Dimensionen:
    1. Empathie (Wie gut wurde emotional validiert?)
    2. Klarheit (Gibt es einen roten Faden?)
    3. Ergebnisorientierung (Gibt es einen klaren Next Step?)

    Gib die Analyse im JSON-Format zurueck mit den Schluesseln:
    "empathy_score" (1-10), "empathy_feedback",
    "clarity_score" (1-10), "clarity_feedback",
    "result_score" (1-10), "result_feedback",
    "summary"

    Transkript:
    {text}
    """

    try:
        response = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent, der Coaching-Analysen im JSON-Format ausgibt. Antworte NUR mit JSON, kein Markdown."},
                {"role": "user", "content": prompt}
            ]
        )

        clean_response = response.choices[0].message.content.strip()
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif clean_response.startswith("```"):
            clean_response = clean_response.split("```")[1].strip()
        return json.loads(clean_response)
    except Exception as e:
        return {
            "summary": "Error during analysis",
            "error": str(e)
        }


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("heygen-api-key"),
        modal.Secret.from_name("my-gemini-secret")
    ]
)
def setup_heygen_resources(force: bool = False):
    """
    One-time setup of Heygen resources: Secret, LLM Config, Context.
    Returns dict with resource IDs. Caches in memory (module globals).
    """
    global heygen_secret_id, heygen_llm_config_id, heygen_contexts, heygen_avatar_id

    heygen_key = os.environ.get("HEYGEN_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not heygen_key:
        return {"error": "HEYGEN_API_KEY not found in secrets"}
    if not gemini_key:
        return {"error": "GEMINI_API_KEY not found in secrets"}

    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    result = {}

    # Step 1: Create secret for Gemini API key (or reuse existing)
    if not heygen_secret_id or force:
        print("[Heygen Setup] Creating secret for Gemini API key...")
        list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/secrets", headers=headers)
        if list_resp.status_code == 200:
            raw = list_resp.json().get("data", [])
            existing = raw if isinstance(raw, list) else raw.get("results", [])
            for s in existing:
                if s.get("secret_name") == "gemini-api-key":
                    heygen_secret_id = s["id"]
                    print(f"[Heygen Setup] Reusing existing secret: {heygen_secret_id}")
                    break

        if not heygen_secret_id:
            create_resp = requests.post(
                f"{HEYGEN_API_BASE}/v1/secrets",
                headers=headers,
                json={
                    "secret_name": "gemini-api-key",
                    "secret_value": gemini_key,
                    "secret_type": "GEMINI_API_KEY"
                }
            )
            if create_resp.status_code in (200, 201):
                heygen_secret_id = create_resp.json().get("data", {}).get("id")
                print(f"[Heygen Setup] Created secret: {heygen_secret_id}")
            else:
                return {"error": f"Failed to create secret: {create_resp.text}"}

    result["secret_id"] = heygen_secret_id

    # Step 2: Create LLM configuration for Gemini
    if not heygen_llm_config_id or force:
        print("[Heygen Setup] Creating LLM configuration for Gemini...")
        list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/llm-configurations", headers=headers)
        if list_resp.status_code == 200:
            raw = list_resp.json().get("data", [])
            existing = raw if isinstance(raw, list) else raw.get("results", [])
            for cfg in existing:
                if cfg.get("display_name") == "Gemini 2.0 Flash":
                    heygen_llm_config_id = cfg["id"]
                    print(f"[Heygen Setup] Reusing existing LLM config: {heygen_llm_config_id}")
                    break

        if not heygen_llm_config_id:
            create_resp = requests.post(
                f"{HEYGEN_API_BASE}/v1/llm-configurations",
                headers=headers,
                json={
                    "display_name": "Gemini 2.0 Flash",
                    "model_name": GEMINI_MODEL,
                    "base_url": GEMINI_BASE_URL,
                    "secret_id": heygen_secret_id
                }
            )
            if create_resp.status_code in (200, 201):
                heygen_llm_config_id = create_resp.json().get("data", {}).get("id")
                print(f"[Heygen Setup] Created LLM config: {heygen_llm_config_id}")
            else:
                return {"error": f"Failed to create LLM config: {create_resp.text}"}

    result["llm_config_id"] = heygen_llm_config_id

    # Step 3: Create per-scenario coaching contexts
    print("[Heygen Setup] Creating per-scenario coaching contexts...")
    list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/contexts", headers=headers)
    existing_contexts = {}
    if list_resp.status_code == 200:
        raw = list_resp.json().get("data", [])
        existing_list = raw if isinstance(raw, list) else raw.get("results", [])
        for ctx in existing_list:
            name = ctx.get("name", "")
            if name.startswith("TalkToMe - "):
                # Extract scenario title from name
                for s in SCENARIOS:
                    if name == f"TalkToMe - {s['title']}":
                        existing_contexts[s["id"]] = ctx["id"]
                        print(f"[Heygen Setup] Reusing context for {s['id']}: {ctx['id']}")
                        break

    for scenario in SCENARIOS:
        sid = scenario["id"]
        if sid in heygen_contexts:
            continue  # already cached in this session
        if sid in existing_contexts and not force:
            heygen_contexts[sid] = existing_contexts[sid]
            continue

        prompt = LIVE_COACH_SYSTEM_PROMPT.format(avatar_role=scenario["avatar_role"])
        opening = "Guten Tag."

        create_resp = requests.post(
            f"{HEYGEN_API_BASE}/v1/contexts",
            headers=headers,
            json={
                "name": f"TalkToMe - {scenario['title']}",
                "prompt": prompt,
                "opening_text": opening
            }
        )
        if create_resp.status_code in (200, 201):
            ctx_id = create_resp.json().get("data", {}).get("id")
            heygen_contexts[sid] = ctx_id
            print(f"[Heygen Setup] Created context for {sid}: {ctx_id}")
        else:
            print(f"[Heygen Setup] WARNING: Failed context for {sid}: {create_resp.text}")

    result["context_ids"] = dict(heygen_contexts)

    result["avatar_id"] = heygen_avatar_id
    result["status"] = "ready"
    return result


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("heygen-api-key"),
        modal.Secret.from_name("my-gemini-secret")
    ]
)
def create_liveavatar_session(sandbox: bool = True, scenario_id: str = "free"):
    """Create a FULL mode LiveAvatar session with scenario-specific context."""
    global heygen_contexts, heygen_llm_config_id, heygen_avatar_id

    heygen_key = os.environ.get("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HEYGEN_API_KEY not found"}

    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Ensure base resources are set up (secret + LLM config)
    if not heygen_llm_config_id:
        setup_result = setup_heygen_resources.remote()
        if "error" in setup_result:
            return setup_result
        heygen_llm_config_id = setup_result.get("llm_config_id")
        heygen_avatar_id = setup_result.get("avatar_id")
        # Merge any pre-created contexts
        for sid, ctx_id in setup_result.get("context_ids", {}).items():
            if sid not in heygen_contexts:
                heygen_contexts[sid] = ctx_id

    # Look up scenario
    scenario = None
    for s in SCENARIOS:
        if s["id"] == scenario_id:
            scenario = s
            break
    if not scenario:
        scenario = SCENARIOS[-1]  # default to "free"

    # Ensure scenario-specific context exists (lazy creation)
    if scenario_id not in heygen_contexts:
        print(f"[Session] Creating context for scenario: {scenario['title']}")
        # Check if context already exists on HeyGen side
        list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/contexts", headers=headers)
        if list_resp.status_code == 200:
            raw = list_resp.json().get("data", [])
            existing_list = raw if isinstance(raw, list) else raw.get("results", [])
            for ctx in existing_list:
                if ctx.get("name") == f"TalkToMe - {scenario['title']}":
                    heygen_contexts[scenario_id] = ctx["id"]
                    print(f"[Session] Reusing existing context: {ctx['id']}")
                    break

        if scenario_id not in heygen_contexts:
            prompt = LIVE_COACH_SYSTEM_PROMPT.format(avatar_role=scenario["avatar_role"])
            create_resp = requests.post(
                f"{HEYGEN_API_BASE}/v1/contexts",
                headers=headers,
                json={
                    "name": f"TalkToMe - {scenario['title']}",
                    "prompt": prompt,
                    "opening_text": "Guten Tag."
                }
            )
            if create_resp.status_code in (200, 201):
                heygen_contexts[scenario_id] = create_resp.json().get("data", {}).get("id")
                print(f"[Session] Created context: {heygen_contexts[scenario_id]}")
            else:
                return {"error": f"Failed to create context: {create_resp.text}"}

    context_id = heygen_contexts[scenario_id]
    print(f"[Session] Scenario: {scenario['title']}, avatar={heygen_avatar_id}, context={context_id}")

    # Create session token
    token_body = {
        "mode": "FULL",
        "avatar_id": heygen_avatar_id,
        "avatar_persona": {
            "context_id": context_id,
            "language": "de"
        },
        "llm_configuration_id": heygen_llm_config_id,
        "is_sandbox": sandbox
    }

    token_resp = requests.post(
        f"{HEYGEN_API_BASE}/v1/sessions/token",
        headers=headers,
        json=token_body
    )

    if token_resp.status_code not in (200, 201):
        print(f"[Session] Token creation failed: {token_resp.status_code} {token_resp.text}")
        return {"error": f"Session token creation failed: {token_resp.text}"}

    token_data = token_resp.json()
    session_token = token_data.get("data", {}).get("session_token")
    session_id = token_data.get("data", {}).get("session_id")

    if not session_token:
        return {"error": "No session_token in response", "raw": token_data}

    print(f"[Session] Got token for session {session_id}")

    # Create embed URL
    embed_resp = requests.post(
        f"{HEYGEN_API_BASE}/v2/embeddings",
        headers=headers,
        json={
            "avatar_id": heygen_avatar_id,
            "context_id": context_id,
            "is_sandbox": sandbox
        }
    )

    embed_url = None
    if embed_resp.status_code in (200, 201):
        embed_data = embed_resp.json()
        embed_url = embed_data.get("data", {}).get("url")
        print(f"[Session] Embed URL: {embed_url}")

    return {
        "session_id": session_id,
        "session_token": session_token,
        "embed_url": embed_url,
        "mode": "FULL",
        "sandbox": sandbox,
        "avatar_id": heygen_avatar_id,
        "scenario": {
            "id": scenario["id"],
            "title": scenario["title"],
            "user_goal": scenario["user_goal"]
        }
    }


# FastAPI App
web_app = FastAPI()


@web_app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_data = await file.read()

    # 1. Transcription (GPU)
    transcriber = BatchTranscription()
    transcript_text = await transcriber.transcribe_bytes.remote.aio(audio_data)

    # 2. Analysis (Gemini)
    if transcript_text:
        analysis = await analyze_transcript.remote.aio(transcript_text)
    else:
        analysis = {"error": "No transcript generated"}

    return {
        "text": transcript_text,
        "analysis": analysis
    }


@web_app.get("/api/scenarios")
def list_scenarios():
    """Return available training scenarios."""
    return {"scenarios": SCENARIOS}


@web_app.post("/api/session/create")
def create_session(scenario_id: str = "free", sandbox: bool = False):
    """Create a new LiveAvatar coaching session with optional scenario."""
    result = create_liveavatar_session.remote(sandbox=sandbox, scenario_id=scenario_id)
    return result


@web_app.get("/api/session/status")
async def session_status():
    """Check if Heygen integration is configured."""
    global heygen_contexts, heygen_llm_config_id, heygen_avatar_id
    return {
        "configured": bool(heygen_llm_config_id and heygen_avatar_id),
        "context_count": len(heygen_contexts),
        "llm_config_id": heygen_llm_config_id,
        "avatar_id": heygen_avatar_id
    }


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("heygen-api-key"),
        modal.Secret.from_name("my-gemini-secret")
    ]
)
def analyze_session(session_id: str, scenario_id: str = "free"):
    """Fetch transcript from Heygen and analyze with Gemini. Falls back to scenario-based coaching tips if transcript unavailable."""
    from openai import OpenAI

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"error": "GEMINI_API_KEY not found"}

    heygen_key = os.environ.get("HEYGEN_API_KEY")
    headers = {"X-API-KEY": heygen_key, "Accept": "application/json"} if heygen_key else {}

    full_transcript = None

    # Look up scenario metadata
    scenario_meta = None
    for s in SCENARIOS:
        if s["id"] == scenario_id:
            scenario_meta = s
            break

    # Try to fetch transcript from Heygen
    if heygen_key and session_id:
        print(f"[Analyze] Fetching transcript for session {session_id}")
        transcript_resp = requests.get(
            f"{HEYGEN_API_BASE}/v1/sessions/{session_id}/transcript",
            headers=headers
        )

        if transcript_resp.status_code == 200:
            transcript_data = transcript_resp.json()
            lines = []
            data = transcript_data.get("data", {})
            if isinstance(data, list):
                for entry in data:
                    speaker = entry.get("speaker", "Unknown")
                    text = entry.get("text", "")
                    lines.append(f"{speaker}: {text}")
            elif isinstance(data, dict):
                results = data.get("results", data.get("transcript", []))
                for entry in results:
                    speaker = entry.get("speaker", entry.get("role", "Unknown"))
                    text = entry.get("text", entry.get("content", ""))
                    lines.append(f"{speaker}: {text}")
            full_transcript = "\n".join(lines) if lines else None
        else:
            # Also try listing historic sessions to find the embed session
            print(f"[Analyze] Direct transcript fetch failed, trying historic sessions...")
            hist_resp = requests.get(f"{HEYGEN_API_BASE}/v1/sessions?type=historic", headers=headers)
            if hist_resp.status_code == 200:
                hist_data = hist_resp.json().get("data", {})
                results = hist_data.get("results", []) if isinstance(hist_data, dict) else hist_data
                if results:
                    latest_id = results[0].get("id")
                    print(f"[Analyze] Trying latest historic session: {latest_id}")
                    t2 = requests.get(f"{HEYGEN_API_BASE}/v1/sessions/{latest_id}/transcript", headers=headers)
                    if t2.status_code == 200:
                        td = t2.json().get("data", {})
                        if isinstance(td, list) and td:
                            lines = [f"{e.get('speaker','?')}: {e.get('text','')}" for e in td]
                            full_transcript = "\n".join(lines)

    client = OpenAI(api_key=gemini_key, base_url=GEMINI_BASE_URL)

    if full_transcript:
        # Analyze actual transcript
        prompt = f"""
        Du bist ein Kommunikations-Coaching-Experte. Analysiere das folgende Gespraechstranskript
        hinsichtlich der drei TalkToMe-Dimensionen:

        1. Empathie (1-10): Wie gut hat der Nutzer emotional validiert und Verstaendnis gezeigt?
        2. Klarheit (1-10): Hatte der Nutzer einen roten Faden? War er praezise?
        3. Ergebnisorientierung (1-10): Hat der Nutzer auf ein klares Ergebnis hingesteuert?

        Gib die Analyse im JSON-Format zurueck:
        {{"empathy_score": 7, "empathy_feedback": "...", "clarity_score": 6, "clarity_feedback": "...", "result_score": 8, "result_feedback": "...", "summary": "..."}}

        Transkript:
        {full_transcript[:4000]}
        """
    else:
        # Generate coaching tips based on scenario metadata
        scenario_title = scenario_meta.get("title", "Freies Coaching") if scenario_meta else "Freies Coaching"
        scenario_goal = scenario_meta.get("user_goal", "Kommunikation verbessern") if scenario_meta else "Kommunikation verbessern"
        scenario_role = scenario_meta.get("avatar_role", "") if scenario_meta else ""

        prompt = f"""
        Du bist ein Kommunikations-Coaching-Experte. Der Nutzer hat gerade ein Live-Rollenspiel
        zum Szenario "{scenario_title}" absolviert.

        Das Ziel des Nutzers war: {scenario_goal}
        Die Rolle des Avatars: {scenario_role}

        Da das Transkript nicht automatisch verfuegbar ist, erstelle eine hilfreiche generische
        Coaching-Analyse fuer dieses Szenario. Gib konkrete, umsetzbare Tipps.

        Gib die Analyse im JSON-Format zurueck:
        {{"empathy_score": 7, "empathy_feedback": "...", "clarity_score": 6, "clarity_feedback": "...", "result_score": 8, "result_feedback": "...", "summary": "..."}}

        Verwende realistische Scores (5-9) und gib konstruktives, spezifisches Feedback.
        """

    try:
        response = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[
                {"role": "system", "content": "Du gibst Coaching-Analysen NUR als JSON aus, kein Markdown."},
                {"role": "user", "content": prompt}
            ]
        )
        clean = response.choices[0].message.content.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif clean.startswith("```"):
            clean = clean.split("```")[1].strip()
        analysis = json.loads(clean)
        if full_transcript:
            analysis["transcript"] = full_transcript
        else:
            analysis["note"] = "Analyse basiert auf Szenario-Metadaten (Live-Transkript nicht automatisch verfügbar)"
        return analysis
    except Exception as e:
        return {"error": str(e), "summary": f"Coaching-Analyse für Szenario '{scenario_meta.get('title') if scenario_meta else 'Coaching'}' konnte nicht erstellt werden."}


@web_app.post("/api/session/analyze")
def analyze_endpoint(session_id: str = "", scenario_id: str = "free"):
    """Analyze a completed coaching session."""
    if not session_id:
        return {"error": "session_id required"}
    result = analyze_session.remote(session_id, scenario_id)
    return result


@web_app.get("/api/heygen/setup")
def run_setup():
    """Run Heygen resource setup manually."""
    result = setup_heygen_resources.remote(force=True)
    return result


@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    web_app.mount("/", StaticFiles(directory="/assets", html=True), name="static")
    return web_app
