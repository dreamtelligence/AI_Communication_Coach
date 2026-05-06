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
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
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
        "avatar_role": "Du bist der Mitarbeiter Alex, der seit 3 Jahren im Team ist. Du bist grundsätzlich engagiert, aber in letzter Zeit oft zu spät gekommen und hast zwei Deadlines verpasst. Du bist nervös wegen des Gesprächs. Wenn der Nutzer empathisch ist → zeigst du dich erleichtert und öffnest dich, erzählst von privaten Problemen die zur Situation geführt haben. Wenn der Nutzer anklagend/unsensibel ist → wirst du defensiv und ziehst dich zurück, sagst nur noch das Nötigste. Wenn keine Lösung angeboten wird → fragst du 'Was soll ich denn jetzt Ihrer Meinung nach tun?'",
        "user_goal": "Führe ein konstruktives Feedbackgespräch mit Empathie. Adressiere die Probleme klar, aber wertschätzend. Erarbeite gemeinsam eine Lösung."
    },
    {
        "id": "salary",
        "title": "Gehaltsverhandlung",
        "category": "Arbeit",
        "icon": "dollar",
        "description": "Du verhandelst mit deinem Vorgesetzten über eine Gehaltserhöhung.",
        "avatar_role": "Du bist der Abteilungsleiter Dr. Meier. Du hast Budget für Gehaltsanpassungen, bist aber unter Druck vom Management, Kosten zu sparen. Du schätzt den Mitarbeiter sehr. Wenn der Nutzer empathisch ist → würdigst du seine Leistungen und signalisierst Kompromissbereitschaft. Wenn der Nutzer anklagend/unsensibel ist → verweist du auf Budgetzwänge und blockst ab mit 'Das liegt nicht in meiner Hand'. Wenn keine Lösung angeboten wird → fragst du 'Was schlagen Sie konkret vor?'",
        "user_goal": "Argumentiere selbstbewusst für deine Gehaltserhöhung mit konkreten Leistungen. Bleibe sachlich und ergebnisorientiert."
    },
    {
        "id": "complaint",
        "title": "Kundenbeschwerde",
        "category": "Arbeit",
        "icon": "message-circle",
        "description": "Ein verärgerter Kunde beschwert sich über ein fehlerhaftes Produkt.",
        "avatar_role": "Du bist ein verärgerter Kunde, der viel Geld für ein Premium-Produkt ausgegeben hat, das defekt ist. Du bist emotional und fordernd, willst aber eigentlich nur ernst genommen werden und eine Lösung. Wenn der Nutzer empathisch ist → beruhigst du dich spürbar und wirst kooperativ, sagst 'Danke, dass Sie mir zuhören'. Wenn der Nutzer anklagend/unsensibel ist → wirst du lauter und drohst mit 'Dann gehe ich zur Konkurrenz und schreibe eine Bewertung'. Wenn keine Lösung angeboten wird → forderst du 'Und was machen wir jetzt? Das kann ja nicht Ihr Ernst sein!'",
        "user_goal": "Beruhige den Kunden mit Empathie. Finde eine klare Lösung und sorge für ein positives Ergebnis."
    },
    {
        "id": "conflict_colleague",
        "title": "Konflikt mit Kollegen",
        "category": "Arbeit",
        "icon": "users",
        "description": "Ein Kollege hat deine Idee im Meeting als seine ausgegeben.",
        "avatar_role": "Du bist Chris, ein ehrgeiziger Kollege. Du hast die Idee tatsächlich übernommen, weil du unter Druck stehst und Anerkennung suchst. Du fühlst dich jetzt ertappt und bist defensiv. Wenn der Nutzer empathisch ist → gibst du klein bei und entschuldigst dich, gestehst den Druck ein. Wenn der Nutzer anklagend/unsensibel ist → wirst du angriffslustig und konterst mit 'Das war Teamarbeit, da gehört die Idee allen'. Wenn keine Lösung angeboten wird → sagst du 'Und was soll sich jetzt konkret ändern?'",
        "user_goal": "Spreche den Konflikt offen aber respektvoll an. Fokussiere auf die gemeinsame Zusammenarbeit."
    },
    {
        "id": "presentation",
        "title": "Projektpräsentation",
        "category": "Arbeit",
        "icon": "trending-up",
        "description": "Du präsentierst ein neues Projekt vor der Geschäftsleitung.",
        "avatar_role": "Du bist Frau Wagner, die CFO. Du bist kritisch und hinterfragst Zahlen. Du willst ROI-Details sehen, bevor du zustimmst. Wenn der Nutzer empathisch ist → signalisierst du vorsichtiges Interesse und stellst präzise Nachfragen. Wenn der Nutzer anklagend/unsensibel ist → wirst du knapp und sagst 'So kommen wir hier nicht weiter'. Wenn keine Lösung angeboten wird → beendest du das Gespräch mit 'Schicken Sie mir die Zahlen schriftlich, dann sehen wir weiter.'",
        "user_goal": "Präsentiere klar und strukturiert. Gehe auf kritische Fragen ein und bleibe ergebnisorientiert."
    },
    {
        "id": "relationship",
        "title": "Beziehungsgespräch",
        "category": "Privat",
        "icon": "heart",
        "description": "Du möchtest mit deinem Partner über eure Zukunftspläne sprechen.",
        "avatar_role": "Du bist der/die Partner/in. Du liebst deinen Partner, hast aber andere Vorstellungen von der Zukunft. Du willst verstanden werden. Wenn der Nutzer empathisch ist → wirst du weicher und sagst 'Es bedeutet mir viel, dass du das verstehst'. Wenn der Nutzer anklagend/unsensibel ist → ziehst du dich emotional zurück und sagst 'Du hörst mir gar nicht zu'. Wenn keine Lösung angeboten wird → fragst du 'Wie stellst du dir unsere Zukunft eigentlich vor?'",
        "user_goal": "Führe ein empathisches Gespräch über Zukunftswünsche. Höre aktiv zu und finde Gemeinsamkeiten statt Unterschiede."
    },
    {
        "id": "neighbor",
        "title": "Nachbarschaftsgespräch",
        "category": "Privat",
        "icon": "home",
        "description": "Dein Nachbar beschwert sich seit Wochen über Lärm.",
        "avatar_role": "Du bist Nachbar Müller, Rentner, lebst allein. Der Lärm des Nachbarn stört deinen Schlaf. Du bist eigentlich ein freundlicher Mensch, aber zunehmend frustriert. Wenn der Nutzer empathisch ist → wirst du ruhiger und erzählst von deiner gesundheitlichen Situation, zeigst dich kompromissbereit. Wenn der Nutzer anklagend/unsensibel ist → wirst du bitter und sagst 'Auf meine Rücksicht nimmt ja sowieso keiner'. Wenn keine Lösung angeboten wird → fragst du 'Also was machen wir jetzt? Ich kann so nicht weitermachen.'",
        "user_goal": "Deeskaliere die Situation. Zeige Verständnis und finde eine pragmatische Lösung für beide Seiten."
    },
    {
        "id": "parents",
        "title": "Elterngespräch in der Schule",
        "category": "Privat",
        "icon": "book-open",
        "description": "Die Lehrerin hat dich zum Gespräch über dein Kind eingeladen.",
        "avatar_role": "Du bist Frau Schmidt, die Klassenlehrerin. Du machst dir Sorgen um das Kind, das sich zurückzieht. Du willst mit den Eltern kooperativ eine Lösung finden. Wenn der Nutzer empathisch ist → teilst du konkrete Beobachtungen und lobst das Engagement der Eltern. Wenn der Nutzer anklagend/unsensibel ist → wirst du formeller und sagst 'Ich dokumentiere das dann entsprechend'. Wenn keine Lösung angeboten wird → schlägst du vor 'Sollen wir einen Förderplan aufsetzen?'",
        "user_goal": "Bleibe offen für Feedback. Zeige Kooperationsbereitschaft und entwickle gemeinsam einen Plan zur Unterstützung des Kindes."
    },
    {
        "id": "doctor",
        "title": "Arztgespräch",
        "category": "Privat",
        "icon": "activity",
        "description": "Du hast gesundheitliche Beschwerden und musst diese dem Arzt klar schildern.",
        "avatar_role": "Du bist Dr. Berger, ein vielbeschäftigter Hausarzt. Du hast nur 10 Minuten Zeit und brauchst präzise Informationen, um eine Diagnose zu stellen. Wenn der Nutzer empathisch ist → nimmst du dir einen Moment mehr Zeit und erklärst die nächsten Schritte verständlich. Wenn der Nutzer anklagend/unsensibel ist → wirst du knapp und sagst 'Ich habe noch weitere Patienten'. Wenn keine Lösung angeboten wird → stellst du eine klare Diagnose und sagst 'Das ist mein Befund, so gehen wir vor.'",
        "user_goal": "Beschreibe deine Symptome klar und strukturiert. Stelle die richtigen Fragen zur Behandlung."
    },
    {
        "id": "free",
        "title": "Freies Coaching",
        "category": "Training",
        "icon": "zap",
        "description": "Freies Kommunikationstraining mit dem TalkToMe Coach.",
        "avatar_role": "Du bist ein professioneller Kommunikations-Coach. Du hilfst dem Nutzer, seine Kommunikationsfähigkeiten zu verbessern. Wenn der Nutzer empathisch ist → lobst du seinen Ansatz und gibst eine gezielte Verbesserungsempfehlung. Wenn der Nutzer anklagend/unsensibel ist → spiegelst du das Verhalten und fragst 'Wie kam das bei Ihrem Gegenüber wohl an?'. Wenn keine Lösung angeboten wird → fragst du 'Was möchten Sie in diesem Gespräch konkret erreichen?'",
        "user_goal": "Trainiere deine Kommunikationsfähigkeiten in einem offenen Gespräch."
    }
]

SCENARIO_OPENINGS = {
    "feedback": "Ich... ich wollte kurz fragen, ob das Gespräch heute wirklich sein muss.",
    "salary": "Sie wollten mich sprechen?",
    "complaint": "Das ist nicht akzeptabel! Ich habe viel Geld bezahlt und das funktioniert einfach nicht!",
    "conflict_colleague": "Ich verstehe nicht warum du das so siehst, das war doch Teamarbeit.",
    "presentation": "Bevor wir anfangen — welche konkreten Zahlen haben Sie mitgebracht?",
    "relationship": "Ich freue mich dass wir endlich reden. Ich hatte das Gefühl du weichst dem Thema aus.",
    "neighbor": "Ich wollte das eigentlich nicht ansprechen, aber es geht wirklich nicht mehr.",
    "parents": "Danke dass Sie gekommen sind. Ich mache mir ehrlich gesagt Sorgen um Ihr Kind.",
    "doctor": "Nächster bitte. Was kann ich für Sie tun? Ich habe etwa zehn Minuten.",
    "free": "Hallo, schön dass Sie da sind. Womit kann ich Ihnen heute helfen?",
}

def get_opening(scenario_id: str) -> str:
    return SCENARIO_OPENINGS.get(scenario_id, "Guten Tag.")


def _parse_transcript(full_transcript: str) -> dict:
    """
    Parse a Heygen transcript and identify user vs avatar lines.
    Returns separated transcripts with speaker labels for the prompt.
    """
    user_lines = []
    avatar_lines = []
    all_lines = []

    for line in full_transcript.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        all_lines.append(line)
        if ":" in line:
            speaker, text = line.split(":", 1)
            speaker_lower = speaker.strip().lower()
            if speaker_lower in ("user", "human", "nutzer", "you", "participant", "ich"):
                user_lines.append(text.strip())
            else:
                avatar_lines.append(f"[{speaker.strip()}]: {text.strip()}")
        else:
            user_lines.append(line)

    return {
        "user_only": "\n".join(user_lines) if user_lines else "",
        "avatar_only": "\n".join(avatar_lines) if avatar_lines else "",
        "full_transcript": "\n".join(all_lines)
    }

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
    secrets=[modal.Secret.from_name("my-deepseek-secret")]
)
def analyze_transcript(text: str):
    """Analyze transcript with DeepSeek via OpenAI-compatible endpoint."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"error": "DeepSeek API key not found in secrets."}

    parsed = _parse_transcript(text)
    user_text = parsed["user_only"]
    avatar_text = parsed["avatar_only"]
    avatar_lines_for_context = avatar_text if avatar_text else "(keine Avatar-Aussagen)"

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    system_prompt = """Du bist ein erfahrener Kommunikations-Coach mit 20 Jahren Erfahrung (Senior Executive Coach).
Du analysierst Live-Rollenspiele, in denen ein MENSCHLICHER NUTZER mit einem KI-AVATAR spricht.

DEINE AUFGABE: Analysiere AUSSCHLIESSLICH den menschlichen Nutzer. Der Avatar ist eine KI — bewertet wird NUR der echte Mensch.

WICHTIGE REGELN:
1. Analysiere NUR die Aussagen des MENSCHLICHEN NUTZERS (im Transkript als "User", "Human", "Nutzer" oder ähnlich markiert).
2. Die Avatar-Aussagen dienen NUR als Kontext — sie zeigen, worauf der Nutzer reagiert hat.
3. Jeder Score MUSS mit einem wörtlichen Zitat aus den NUTZER-Aussagen belegt werden.
4. Verwechsle NIEMALS Avatar und Nutzer. Wenn du dir unsicher bist, wer wer ist: Der Avatar spricht den ERSTEN Satz im Gespräch.
5. Sei ehrlich und direkt. Beschönige nichts. Der Nutzer will sich verbessern — dafür braucht er ungeschönte Wahrheit.
6. Antworte NUR mit JSON, kein Markdown, keine Erklärungen außerhalb des JSON."""

    prompt = f"""Analysiere das folgende Live-Coaching-Transkript.

DER AVATAR (KI-Gesprächspartner) hat diese Rolle gespielt und Folgendes gesagt:
{avatar_lines_for_context}

DER MENSCHLICHE NUTZER (wird bewertet) hat Folgendes gesagt:
{user_text if user_text else "(Keine Nutzer-Aussagen gefunden — bitte analysiere das vollständige Transkript und identifiziere den menschlichen Sprecher)"}

VOLLSTÄNDIGES TRANSKRIPT (zur Orientierung):
{text[:4000]}

---
BEWERTE DEN MENSCHLICHEN NUTZER NACH FOLGENDEN KRITERIEN:

1. EMPATHIE & EMOTIONALE INTELLIGENZ (1-10):
   - Erkennt und benennt der Nutzer die Emotionen des Gegenübers explizit?
     (z.B. "Ich verstehe, dass Sie frustriert sind", "Ich höre raus, dass Sie Sorgen haben")
   - Spiegelt/paraphrasiert der Nutzer, was das Gegenüber gesagt hat? (aktives Zuhören)
   - Geht der Nutzer auf非verbale/emotionale Signale ein?
   - Passt der Nutzer seinen Tonfall der Situation an? (z.B. beruhigend bei Ärger)
   - Unterbricht der Nutzer das Gegenüber oder lässt er ausreden?

2. SPRACHLICHE KLARHEIT & STRUKTUR (1-10):
   - Hat der Nutzer einen klaren roten Faden oder springt er planlos zwischen Themen?
   - Sind die Aussagen präzise oder vage? Werden konkrete Beispiele genannt?
   - Gibt es eine erkennbare Gesprächsstruktur (Einleitung, Hauptteil, Abschluss)?
   - Ist die Wortwahl dem Kontext angemessen (weder zu salopp noch zu gestelzt)?
   - Werden Fachbegriffe verständlich erklärt?

3. ERGEBNISORIENTIERUNG & ZIELFÜHRUNG (1-10):
   - Verfolgt der Nutzer ein klares Ziel oder treibt das Gespräch ziellos?
   - Lenkt der Nutzer das Gespräch aktiv in Richtung seines Ziels?
   - Wird ein konkreter nächster Schritt / eine Vereinbarung getroffen?
   - Reagiert der Nutzer flexibel auf unerwartete Wendungen, ohne das Ziel aus den Augen zu verlieren?
   - Bringt der Nutzer das Gespräch zu einem klaren Abschluss?

JEDER SCORE MUSS MIT MINDESTENS EINEM WÖRTLICHEN ZITAT DES NUTZERS BELEGT WERDEN.
Formuliere das Feedback direkt, ehrlich und konstruktiv — wie ein Senior Coach, der wirklich helfen will.

Gib die Analyse im JSON-Format zurück:
{{"empathy_score": 7, "empathy_feedback": "...", "clarity_score": 6, "clarity_feedback": "...", "result_score": 8, "result_feedback": "...", "summary": "Gesamteinschätzung mit den 2-3 wichtigsten Entwicklungsfeldern des Nutzers."}}"""

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        clean_response = response.choices[0].message.content.strip()
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[1].split("```")[0].strip()
        elif clean_response.startswith("```"):
            clean_response = clean_response.split("```")[1].strip()
        result = json.loads(clean_response)
        result["transcript"] = text
        return result
    except Exception as e:
        return {
            "summary": "Error during analysis",
            "error": str(e)
        }


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("heygen-api-key"),
        modal.Secret.from_name("my-deepseek-secret")
    ]
)
def setup_heygen_resources(force: bool = False):
    """
    One-time setup of Heygen resources: Secret, LLM Config, Context.
    Returns dict with resource IDs. Caches in memory (module globals).
    """
    global heygen_secret_id, heygen_llm_config_id, heygen_contexts, heygen_avatar_id

    heygen_key = os.environ.get("HEYGEN_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

    if not heygen_key:
        return {"error": "HEYGEN_API_KEY not found in secrets"}
    if not deepseek_key:
        return {"error": "DEEPSEEK_API_KEY not found in secrets"}

    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    result = {}

    # Step 1: Create secret for DeepSeek API key (or reuse existing)
    if not heygen_secret_id or force:
        print("[Heygen Setup] Creating secret for DeepSeek API key...")
        list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/secrets", headers=headers)
        if list_resp.status_code == 200:
            raw = list_resp.json().get("data", [])
            existing = raw if isinstance(raw, list) else raw.get("results", [])
            for s in existing:
                if s.get("secret_name") == "deepseek-api-key":
                    heygen_secret_id = s["id"]
                    print(f"[Heygen Setup] Reusing existing secret: {heygen_secret_id}")
                    break

        if not heygen_secret_id:
            create_resp = requests.post(
                f"{HEYGEN_API_BASE}/v1/secrets",
                headers=headers,
                json={
                    "secret_name": "deepseek-api-key",
                    "secret_value": deepseek_key,
                    "secret_type": "OPENAI_API_KEY"
                }
            )
            if create_resp.status_code in (200, 201):
                heygen_secret_id = create_resp.json().get("data", {}).get("id")
                print(f"[Heygen Setup] Created secret: {heygen_secret_id}")
            else:
                return {"error": f"Failed to create secret: {create_resp.text}"}

    result["secret_id"] = heygen_secret_id

    # Step 2: Create LLM configuration for DeepSeek
    if not heygen_llm_config_id or force:
        print("[Heygen Setup] Creating LLM configuration for DeepSeek...")
        list_resp = requests.get(f"{HEYGEN_API_BASE}/v1/llm-configurations", headers=headers)
        if list_resp.status_code == 200:
            raw = list_resp.json().get("data", [])
            existing = raw if isinstance(raw, list) else raw.get("results", [])
            for cfg in existing:
                if cfg.get("display_name") == "DeepSeek V3":
                    heygen_llm_config_id = cfg["id"]
                    print(f"[Heygen Setup] Reusing existing LLM config: {heygen_llm_config_id}")
                    break

        if not heygen_llm_config_id:
            create_resp = requests.post(
                f"{HEYGEN_API_BASE}/v1/llm-configurations",
                headers=headers,
                json={
                    "display_name": "DeepSeek V3",
                    "model_name": DEEPSEEK_MODEL,
                    "base_url": DEEPSEEK_BASE_URL,
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
        opening = get_opening(sid)

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
        modal.Secret.from_name("my-deepseek-secret")
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
                    "opening_text": get_opening(scenario_id)
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

    # 2. Analysis (DeepSeek)
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
        modal.Secret.from_name("my-deepseek-secret")
    ]
)
def analyze_session(session_id: str, scenario_id: str = "free"):
    """Fetch transcript from Heygen and analyze with DeepSeek. Falls back to scenario-based coaching tips if transcript unavailable."""
    from openai import OpenAI

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if not deepseek_key:
        return {"error": "DEEPSEEK_API_KEY not found"}

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

    client = OpenAI(api_key=deepseek_key, base_url=DEEPSEEK_BASE_URL)

    system_prompt = """Du bist ein erfahrener Kommunikations-Coach mit 20 Jahren Erfahrung (Senior Executive Coach).
Du analysierst Live-Rollenspiele, in denen ein MENSCHLICHER NUTZER mit einem KI-AVATAR spricht.

DEINE AUFGABE: Analysiere AUSSCHLIESSLICH den menschlichen Nutzer. Der Avatar ist eine KI — bewertet wird NUR der echte Mensch, der im Rollenspiel übt.

WICHTIGE REGELN — MISSACHTEN FÜHRT ZU FEHLANALYSE:
1. Analysiere NUR die Aussagen des MENSCHLICHEN NUTZERS. Im Transkript ist der Mensch meist als "User", "Human", "Nutzer" oder ähnlich markiert. Der Avatar (KI) trägt meist einen Rollennamen (z.B. "Dr. Meier", "Alex", "Frau Wagner") oder ist als "Avatar", "Assistant", "AI" markiert.
2. Der Avatar spricht in der Regel den ERSTEN Satz im Gespräch (Begrüßung/Eröffnung). Alles was der Avatar sagt ist NUR Kontext.
3. Jeder Score MUSS mit wörtlichen Zitaten des NUTZERS belegt werden — NIEMALS mit Avatar-Zitaten.
4. Verwechsle NIEMALS Avatar und Nutzer. Wenn der Avatar sagt "Ich bin frustriert" und der Nutzer antwortet "Ich verstehe" — dann ist es falsch zu schreiben "Der Nutzer hat seine Frustration geäußert". Die Frustration gehört zum Avatar!
5. Sei ehrlich und direkt. Beschönige nichts. Der Nutzer will sich verbessern — dafür braucht er ungeschönte, präzise Wahrheit.
6. Antworte NUR mit JSON, kein Markdown, keine Erklärungen außerhalb des JSON."""

    if full_transcript:
        parsed = _parse_transcript(full_transcript)
        user_text = parsed["user_only"]
        avatar_text = parsed["avatar_only"]

        scenario_title = scenario_meta.get("title", "Freies Coaching") if scenario_meta else "Freies Coaching"
        scenario_goal = scenario_meta.get("user_goal", "Kommunikation verbessern") if scenario_meta else "Kommunikation verbessern"

        prompt = f"""Analysiere ein Live-Coaching-Rollenspiel.

SZENARIO: {scenario_title}
ZIEL DES NUTZERS: {scenario_goal}

---
DER KI-AVATAR (Gesprächspartner, der vom Nutzer trainiert wird) sagte:
{avatar_text if avatar_text else "(Keine Avatar-Aussagen identifiziert)"}

---
DER MENSCHLICHE NUTZER (wird bewertet — das ist die Person, die trainiert) sagte:
{user_text if user_text else "(Keine Nutzer-Aussagen identifiziert — bitte identifiziere den menschlichen Sprecher anhand des Kontexts: Wer reagiert auf den Avatar?)"}

---
VOLLSTÄNDIGES TRANSKRIPT (zur Orientierung, wer wem geantwortet hat):
{full_transcript[:4000]}

---
BEWERTE DEN MENSCHLICHEN NUTZER NACH DIESEN KRITERIEN:

1. EMPATHIE & EMOTIONALE INTELLIGENZ (1-10):
   - Erkennt und benennt der Nutzer die Emotionen des Gegenübers explizit?
     (z.B. "Ich verstehe, dass Sie frustriert sind", "Ich höre raus, dass Sie unter Druck stehen")
   - Spiegelt/paraphrasiert der Nutzer, was das Gegenüber gesagt hat? (aktives Zuhören)
   - Geht der Nutzer auf emotionale Signale des Gegenübers ein?
   - Passt der Nutzer seinen Tonfall der Situation an? (z.B. beruhigend bei Ärger, verständnisvoll bei Sorge)
   - Unterbricht der Nutzer das Gegenüber oder lässt er ausreden?

2. SPRACHLICHE KLARHEIT & STRUKTUR (1-10):
   - Hat der Nutzer einen klaren roten Faden oder springt er planlos zwischen Themen?
   - Sind die Aussagen präzise oder vage? Werden konkrete Beispiele/Zahlen genannt?
   - Gibt es eine erkennbare Gesprächsstruktur (Einleitung → Hauptteil → Abschluss)?
   - Ist die Wortwahl dem Kontext angemessen?
   - Werden Fachbegriffe oder unklare Aussagen verständlich erklärt?

3. ERGEBNISORIENTIERUNG & ZIELFÜHRUNG (1-10):
   - Verfolgt der Nutzer ein klares Ziel oder treibt das Gespräch ziellos?
   - Lenkt der Nutzer das Gespräch aktiv in Richtung seines Ziels?
   - Wird ein konkreter nächster Schritt oder eine Vereinbarung getroffen?
   - Reagiert der Nutzer flexibel auf unerwartete Wendungen, ohne das Ziel aus den Augen zu verlieren?
   - Bringt der Nutzer das Gespräch zu einem klaren, verbindlichen Abschluss?

JEDER SCORE MUSS MIT MINDESTENS EINEM WÖRTLICHEN ZITAT AUS DEN NUTZER-AUSSAGEN BELEGT WERDEN.
Die Zitate müssen AUSSCHLIESSLICH vom menschlichen Nutzer stammen, nicht vom Avatar.
Formuliere das Feedback direkt, ehrlich und konstruktiv — wie ein Senior Coach, der wirklich helfen will.
Sei spezifisch: schreibe nicht "Der Nutzer war einfühlsam", sondern "Der Nutzer benannte die Sorge des Gegenübers mit den Worten 'Ich sehe, dass Ihnen das wichtig ist' — das war gut, aber er hätte noch tiefer nachfragen können, WAS genau die Sorge ist."

Gib die Analyse im JSON-Format zurück:
{{"empathy_score": 7, "empathy_feedback": "...", "clarity_score": 6, "clarity_feedback": "...", "result_score": 8, "result_feedback": "...", "summary": "Gesamteinschätzung mit den 2-3 wichtigsten Stärken und Entwicklungsfeldern"}}"""
    else:
        scenario_title = scenario_meta.get("title", "Freies Coaching") if scenario_meta else "Freies Coaching"
        scenario_goal = scenario_meta.get("user_goal", "Kommunikation verbessern") if scenario_meta else "Kommunikation verbessern"
        scenario_role = scenario_meta.get("avatar_role", "") if scenario_meta else ""

        prompt = f"""Der Nutzer hat gerade ein Live-Rollenspiel mit einem KI-Avatar absolviert.
Das Transkript ist technisch leider nicht verfügbar.

SZENARIO: {scenario_title}
ZIEL DES NUTZERS (das ist die Person, die geübt hat): {scenario_goal}
ROLLE DES AVATARS (KI-Gesprächspartner, nicht der Nutzer): {scenario_role}

Erstelle eine generische, aber spezifisch auf das Szenario "{scenario_title}" zugeschnittene Coaching-Analyse FÜR DEN MENSCHLICHEN NUTZER.
Der Nutzer hat versucht, folgendes Ziel zu erreichen: {scenario_goal}
Der Avatar spielte die Rolle: {scenario_role}

Da kein Transkript vorliegt, formuliere das Feedback als hypothetische Analyse ("Vermutlich haben Sie...", "In dieser Situation ist es wichtig..."). Verwende realistische Scores (5-9) und gib konkrete, umsetzbare Verbesserungsvorschläge, die spezifisch zu diesem Szenario passen.

Bewerte nach:
1. EMPATHIE (1-10): Fähigkeit, die Emotionen der Rolle "{scenario_role[:80]}..." zu erkennen und darauf einzugehen
2. KLARHEIT (1-10): Struktur und Präzision in der Argumentation
3. ERGEBNIS (1-10): Zielorientierung und Abschlussstärke

Gib die Analyse im JSON-Format zurück:
{{"empathy_score": 7, "empathy_feedback": "...", "clarity_score": 6, "clarity_feedback": "...", "result_score": 8, "result_feedback": "...", "summary": "..."}}"""

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
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
