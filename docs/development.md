# Development map

## Source layout

- `coach_app/`: importable Python modules for scenarios, Tavus requests, transcripts, scoring and request security.
- `transcribe_demo.py`: the existing Modal deployment entry point, FastAPI routes and GPU transcription. The filename is retained because deployment commands and function identifiers depend on this entry point.
- `frontend/src/App.tsx`: page shell and English audio upload.
- `frontend/src/CoachAvatar.tsx`: selection, session creation, call status polling, analysis and results.
- `frontend/src/components/ScoreCard.tsx`: the shared numeric/unassessed score display.
- `frontend/src/personas.ts`: presentation data and portrait paths; scenario behavior comes from the backend.
- `frontend/src/index.css`: the app's own CSS and bundled font declarations. There is no Tailwind/component-generator dependency in the active UI.
- `tests/`: secret-free Python tests; `tests/fixtures/` contains fictional provider-evaluation cases.
- `scripts/evaluate_interview.py`: an explicitly invoked, billable text evaluation. It is not a unit test or a live video test.
- `samples/`: the English sample audio, separate from source and tests.

## Request and provider boundaries

Vercel serves the built frontend and forwards `/api` to Modal. The same API can serve a packaged frontend directly. Vite's development proxy uses `VITE_API_PROXY_TARGET` or the configured remote backend. A local frontend does not imply a local or free backend.

Live sessions receive a server-signed conversation token. Status and analysis requests require that token. This is a conversation access boundary, not an account system or an expiring user login. Rate limiting is in-memory and depends on the configured single web container.

The interview grader uses domain-specific model fields, then maps them to the existing public response fields. It validates quote provenance before displaying a score. Semantic correctness of the feedback remains a model decision; the public rubric is not a validated hiring instrument.

## Audio and reproducibility

The deployed Parakeet v2 upload model is English-only, and the upload path does not split two speakers. Its output uses the default rubric. German live-roleplay transcripts arrive through Tavus. See the [NVIDIA model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) for the upload model's documented language and input requirements.

The frontend has a committed npm lockfile and the test environment pins its two direct Python requirements. The remote GPU image installs additional dependencies in the deployment file without a full resolved lock. Tests do not guarantee that a future GPU image rebuild, provider model identifier or provider quota will remain available.

Historical Tavus `TalkToMe` PAL names are retained as provider cache identifiers. Changing them to match the display brand would create new remote personas; a repository cleanup should not do that implicitly.
