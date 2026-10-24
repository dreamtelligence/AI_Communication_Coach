from __future__ import annotations

import os
import re
import time

import modal
import requests
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from coach_app.analysis import (
    GEMINI_MODEL,
    AnalysisProviderError,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    build_analysis_prompt,
    deepseek_error_message,
    generate_with_gemini,
    parse_analysis_json,
    system_prompt,
)
from coach_app.scenarios import SCENARIOS, get_practice_side, get_scenario, list_public_scenarios, scenario_side_payload
from coach_app.schemas import AnalyzeSessionRequest, CreateSessionRequest
from coach_app.security import (
    InMemoryRateLimiter,
    SecurityHeadersMiddleware,
    issue_session_token,
    require_admin_token,
    require_session_token,
    validate_upload_size,
)
from coach_app.tavus_client import (
    TavusError,
    create_conversation,
    end_conversation,
    ensure_pal,
    get_conversation,
    is_configured,
    setup_pals,
)
from coach_app.transcript import transcript_from_tavus_conversation
from coach_app.transcript import parse_transcript


app = modal.App("asr-coaching-analysis")

MODAL_NAME = "nvidia/parakeet-tdt-0.6b-v2"
CUDA_TAG = "12.4.1-devel-ubuntu22.04"
CACHE_DIR = "/cache"

nemo_cache = modal.Volume.from_name("nemo-model-cache", create_if_missing=True)
pal_cache: dict[str, str] = {}
CONVERSATION_ID_PATTERN = re.compile(r"[a-z0-9]{8,64}")

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
        "requests",
    )
    .env({"NEMO_CACHE_DIR": CACHE_DIR})
    .add_local_dir(os.path.join(os.path.dirname(__file__), "coach_app"), remote_path="/root/coach_app")
    .add_local_dir(os.path.join(os.path.dirname(__file__), "frontend", "dist"), remote_path="/assets")
)


def _tavus_secrets() -> list[modal.Secret]:
    return [modal.Secret.from_name("Tavus")]


def _analysis_secrets() -> list[modal.Secret]:
    return [modal.Secret.from_name("my-deepseek-secret"), modal.Secret.from_name("my-gemini-secret")]


def _tavus_api_key() -> str | None:
    return os.environ.get("TAVUS_API_KEY") or os.environ.get("TAURUS_API_KEY") or os.environ.get("TAVUS_KEY")


def _gemini_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


@app.cls(gpu="L40S", image=image, timeout=600, scaledown_window=60, volumes={CACHE_DIR: nemo_cache})
class BatchTranscription:
    @modal.enter()
    def setup(self) -> None:
        import nemo.collections.asr as nemo_asr

        self.asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODAL_NAME)

    @modal.method()
    def transcribe_bytes(self, audio_data: bytes) -> str:
        import tempfile

        import soundfile as sf
        import torch
        import torchaudio

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
                waveform = torchaudio.transforms.Resample(sample_rate, 16000)(waveform)
                sample_rate = 16000
            sf.write(tmp_path, waveform.squeeze().numpy(), sample_rate)
            hypotheses = self.asr_model.transcribe([tmp_path], batch_size=1, verbose=False)
            if not hypotheses:
                return ""
            hyp = hypotheses[0]
            return hyp if isinstance(hyp, str) else getattr(hyp, "text", str(hyp))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


@app.function(image=image, secrets=_analysis_secrets())
def analyze_transcript(text: str, scenario_id: str = "salary", practice_side: str | None = None) -> dict:
    prompt = build_analysis_prompt(text, scenario_id, practice_side)
    result = _run_analysis_prompt(prompt)
    if "error" not in result:
        result["transcript"] = parse_transcript(text)["full_transcript"]
    return result


def _run_analysis_prompt(prompt: str) -> dict:
    from openai import OpenAI

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    gemini_key = _gemini_api_key()
    provider_errors: list[str] = []

    if gemini_key:
        gemini_error: str | None = None
        for attempt in range(2):  # Gemini occasionally returns malformed JSON; one retry is enough
            raw = ""
            try:
                raw = generate_with_gemini(gemini_key, prompt, os.environ.get("GEMINI_MODEL", GEMINI_MODEL))
                result = parse_analysis_json(raw)
                result["provider"] = "gemini"
                return result
            except AnalysisProviderError as exc:
                gemini_error = str(exc)
                break
            except requests.RequestException as exc:
                # log only the error type: request errors can carry URLs, model output can carry user content
                print(f"Gemini request failed (attempt {attempt + 1}): {type(exc).__name__}")
                gemini_error = "Analyse nicht verfügbar: Gemini ist gerade nicht erreichbar."
            except (ValueError, TypeError) as exc:
                print(f"Gemini returned invalid analysis JSON (attempt {attempt + 1}): {type(exc).__name__}, len={len(raw)}")
                gemini_error = "Analyse nicht verfügbar: Gemini konnte keine gültige JSON-Analyse liefern."
        if gemini_error:
            provider_errors.append(gemini_error)

    if deepseek_key:
        client = OpenAI(api_key=deepseek_key, base_url=DEEPSEEK_BASE_URL)
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                temperature=0.3,
                messages=[{"role": "system", "content": system_prompt()}, {"role": "user", "content": prompt}],
            )
            result = parse_analysis_json(response.choices[0].message.content or "")
            result["provider"] = "deepseek"
            return result
        except Exception as exc:
            provider_errors.append(deepseek_error_message(exc))

    if provider_errors:
        return {"error": " ".join(provider_errors)}
    return {"error": "Analyse-Service ist nicht konfiguriert. Hinterlege `DEEPSEEK_API_KEY` oder `GEMINI_API_KEY` in Modal."}


@app.function(image=image, secrets=_tavus_secrets())
def setup_tavus_resources() -> dict:
    global pal_cache

    api_key = _tavus_api_key()
    if not is_configured(api_key):
        return {"error": "Tavus is not configured."}
    try:
        pal_cache = setup_pals(api_key or "", SCENARIOS)
        return {"status": "ready", "pal_count": len(pal_cache)}
    except TavusError as exc:
        return {"error": str(exc)}


@app.function(image=image, secrets=_tavus_secrets())
def create_tavus_session(scenario_id: str = "salary", practice_side: str | None = None, sandbox: bool = False) -> dict:
    global pal_cache

    api_key = _tavus_api_key()
    if not is_configured(api_key):
        return {"error": "Tavus is not configured."}

    scenario = get_scenario(scenario_id)
    side = get_practice_side(scenario, practice_side)
    try:
        cache_key = f"{scenario['id']}:{side['id']}"
        pal_id = pal_cache.get(cache_key)
        if not pal_id:
            pal_id = ensure_pal(api_key or "", scenario, side["id"])
            pal_cache = {**pal_cache, cache_key: pal_id}
        conversation = create_conversation(api_key or "", pal_id, scenario, side["id"], sandbox=sandbox)
    except TavusError as exc:
        return {"error": str(exc)}

    conversation_id = conversation["conversation_id"]
    conversation_url = conversation["conversation_url"]
    return {
        "conversation_id": conversation_id,
        "conversation_url": conversation_url,
        "session_id": conversation_id,
        "embed_url": conversation_url,
        "sandbox": sandbox,
        "provider": "tavus",
        "scenario": scenario_side_payload(scenario, side["id"]),
    }


@app.function(image=image, secrets=[*_tavus_secrets(), *_analysis_secrets()])
def analyze_tavus_session(conversation_id: str, scenario_id: str = "salary", practice_side: str | None = None) -> dict:
    tavus_key = _tavus_api_key()
    if not tavus_key:
        return {"error": "Tavus is not configured."}

    transcript: str | None = None
    try:
        end_conversation(tavus_key, conversation_id)
        for _ in range(8):
            conversation = get_conversation(tavus_key, conversation_id, verbose=True)
            transcript = transcript_from_tavus_conversation(conversation)
            if transcript:
                break
            time.sleep(3)
    except TavusError as exc:
        return {"error": f"Tavus-Transkript konnte nicht abgerufen werden: {exc}"}

    if not transcript:
        return {
            "error": (
                "Analyse nicht gestartet: Tavus hat noch kein End-of-call-Transkript geliefert. "
                "Bitte die Tavus-Session beenden und nach wenigen Sekunden erneut analysieren."
            )
        }

    prompt = build_analysis_prompt(transcript, scenario_id, practice_side)
    result = _run_analysis_prompt(prompt)
    if "error" not in result:
        result["transcript"] = parse_transcript(transcript)["full_transcript"]
    return result


web_app = FastAPI(
    title="TalkToMe API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
web_app.add_middleware(SecurityHeadersMiddleware)
rate_limiter = InMemoryRateLimiter()


@web_app.middleware("http")
async def rate_limit_api(request: Request, call_next):
    try:
        rate_limiter.check(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    return await call_next(request)


@web_app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@web_app.post("/api/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)) -> dict:
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="Only audio uploads are supported.")
    audio_data = await file.read()
    validate_upload_size(request, len(audio_data))

    transcript_text = await BatchTranscription().transcribe_bytes.remote.aio(audio_data)
    analysis = await analyze_transcript.remote.aio(transcript_text) if transcript_text else {"error": "No transcript generated."}
    return {"text": transcript_text, "analysis": analysis}


@web_app.get("/api/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": list_public_scenarios()}


@web_app.get("/api/session/status")
def session_status() -> dict:
    return {"configured": is_configured(_tavus_api_key()), "provider": "tavus"}


@web_app.post("/api/session/create")
def create_session(payload: CreateSessionRequest) -> dict:
    result = create_tavus_session.remote(
        scenario_id=payload.scenario_id,
        practice_side=payload.practice_side,
        sandbox=payload.sandbox,
    )
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    # binds status/analyze calls to the browser that created the session
    return {**result, "session_token": issue_session_token(result["conversation_id"])}


@web_app.get("/api/session/{conversation_id}/status")
def conversation_status(conversation_id: str, request: Request) -> dict:
    """Lets the frontend notice when the PAL ended the call itself (end_call)."""
    if not CONVERSATION_ID_PATTERN.fullmatch(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation id.")
    require_session_token(request, conversation_id)
    api_key = _tavus_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="Tavus is not configured.")
    try:
        conversation = get_conversation(api_key, conversation_id, verbose=False)
    except TavusError as exc:
        print(f"Tavus status lookup failed: {exc}")
        raise HTTPException(status_code=502, detail="Status nicht verfügbar.") from exc
    return {"status": conversation.get("status", "unknown")}


@web_app.post("/api/session/analyze")
def analyze_endpoint(payload: AnalyzeSessionRequest, request: Request) -> dict:
    require_session_token(request, payload.conversation_id)
    result = analyze_tavus_session.remote(payload.conversation_id, payload.scenario_id, payload.practice_side)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@web_app.post("/api/tavus/setup")
def run_setup(request: Request) -> dict:
    require_admin_token(request)
    result = setup_tavus_resources.remote()
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


# One web container that serves many requests at once: keeps the in-memory rate limiter (incl. the global
# cap on new Tavus sessions) authoritative instead of counting per autoscaled container.
@app.function(image=image, secrets=_tavus_secrets(), max_containers=1)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def fastapi_app():
    web_app.mount("/", StaticFiles(directory="/assets", html=True), name="static")
    return web_app
