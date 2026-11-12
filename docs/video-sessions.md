# Video sessions and mobile layout

## Incident, 11 November 2026

On iPhone, the active call area collapsed to 0 × 0 pixels while the goal sidebar stayed visible. The `aspect-ratio` grid item had only absolutely positioned children and no definite width. A browser regression using the actual active-call React path reproduced this at 393 and 768 pixels in WebKit; Chromium retained the expected dimensions. Setting `width: 100%` on `.stage--call` fixes the collapsed area in both engines. Git blame traces these layout rules to the redesign `2ee36a4` on 27 October, not the portrait/interview changes on 10 November. The earlier mobile release check covered selection and results, not an actual connected call.

A separate provider error reported maximum concurrent conversations. An owner-confirmed abandoned interview session was explicitly ended through Tavus; the provider then reported zero active conversations. No unrelated session was terminated.

## Video presentation

`VideoCall.tsx` uses the Daily call object behind Tavus to render the remote avatar as the main video and the muted, mirrored local camera as a small overlay. Microphone and camera buttons retain native browser permission handling; blocked remote audio exposes a user-gesture playback button. The existing backend still creates the Tavus conversation, owns provider credentials and authorizes session operations. The Daily SDK is loaded only when a conversation starts. Its CSP sources are allowed explicitly, without enabling `unsafe-eval`.

At the owner's follow-up request, phone widths below 760 pixels use the same preview width at twice its original height (2:3), placed 16 pixels from the bottom and right edges. Media buttons sit to the left to avoid overlap at 320 pixels. Desktop keeps its 4:3 preview in the upper corner. The browser regression covers these positions at 320, 393, 768 and 1440 pixels.

## Ending a call and showing the report, 12 November 2026

The video component now unmounts as soon as analysis starts. Its expected disconnect cannot replace the analysis loading screen with a connection error; only an active conversation accepts video-error state changes. Status requests that finish after leaving the active state are ignored, so a late `ended` response cannot start a second paid analysis. Actual connection failures during a call and analysis-provider errors remain visible.

The owner approved publication on 12 November 2026. The isolated regression reproduces the brief connection-error screen before the fix, and a separate delayed-status case reproduces two analysis requests instead of one. All ten transition checks in Chromium/WebKit, the eight existing video checks and the TypeScript/production build pass. These checks use controlled media and API responses; no paid provider call was made for this fix.

## Abandoned-call recovery

- Each new conversation receives a server-created 120-second deadline in the persistent Modal dictionary `coach-conversation-leases`. Failed registration closes the provider session instead of returning an untracked call.
- The client renews every 15 seconds only while decoded remote video frames are advancing. A JavaScript timer in a frozen video page is insufficient. Brief app switches do not immediately hang up; extended background suspension may expire the call.
- `pagehide`, component unmount and fatal connection/permission errors send an authenticated, keepalive end request. Browser delivery is best effort.
- A scheduled Modal function runs every minute and ends expired sessions. Normal recovery is within roughly two to three minutes, plus provider/platform delays. Provider failures retain the deadline for the next attempt. This is a recovery mechanism, not an immediate disconnect guarantee.
- End and heartbeat endpoints require the same conversation-bound HMAC token as status and analysis. They cannot close somebody else's conversation. Expired deadlines cannot be revived by late heartbeats.
- A timeout reason is retained for one hour, then removed. A returning browser shows a connection error instead of automatically requesting a paid evaluation of an abandoned call.
- Provider maximum duration and participant absence timeouts remain as additional bounds. Sessions created before this release have no dictionary lease and are not swept.

## Checks

Run the Python suite from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

For browser regressions, install frontend dependencies and Playwright's browsers, start the normal Vite server on port 3291, then run:

```bash
cd frontend
npm ci
npx playwright install chromium webkit
npm run dev -- --port 3291
# In another shell, from the repository root:
node scripts/check_video_call.mjs
CHECK_URL=http://127.0.0.1:3291/ node scripts/check_analysis_transition.mjs
```

`CHECK_URL` selects another served build. `BROWSER_EXECUTABLE` can select an installed Chromium-based executable. Browser checks use an explicitly labeled synthetic video fixture instead of opening paid Tavus conversations. They check active-stage dimensions, the corner preview, media controls, StrictMode cleanup, stopping heartbeats for frozen video, and releasing on unmount. They do not prove real camera/microphone behavior, real Tavus media transport or acceptance on physical iPhones.

The analysis-transition check mocks all API and media responses. It covers manual completion, avatar hang-up, a late status response, a real in-call disconnect and an analysis error in Chromium and WebKit. It makes no provider requests.

## Actual provider check, 11 November 2026

The production backend and the compiled frontend were exercised together under the production CSP using a real Tavus conversation. Headless Chromium supplied synthetic local camera/microphone devices; the remote avatar was genuine provider video (640 × 356 pixels). Both the large avatar and corner preview rendered, including a 361 × 481 mobile-width stage. No CSP or browser errors occurred during connection. Video playback was then deliberately paused while the WebRTC connection stayed joined. Heartbeats stopped, and the scheduled watchdog logged one expired session ended, zero failures. Authenticated status reported `ended` after 166 seconds; a final explicit release returned HTTP 200. Transcript analysis was intercepted for this controlled recovery test. Provider hang-up messages after intentional expiry are expected, not a successful human conversation evaluation.

The separate Python suite covers session ownership, expired leases, failed-provider retries and registration failures. Real microphone/camera acceptance in Brave/Safari on a physical iPhone remains an owner check; WebKit automation verifies layout, not iOS hardware behavior.

## Release

Implementation commits: `235c856` and `866b6ca`. The Modal `asr-coaching-analysis` deployment includes the persistent deadlines, protected heartbeat/end endpoints and scheduled watchdog. Vercel production deployment `dpl_FKC6kPNjZYQk4Vc9soadd5PMFfMh` was built with production settings, checked before promotion, and promoted to [coach.dreamtelligence.de](https://coach.dreamtelligence.de/). Public HTTP 200 serves the same compiled HTML/asset hashes as the verified local Node 24.22.2 build. Unauthenticated heartbeat and end requests return HTTP 403.

All 51 Python tests pass. The active-call browser checks pass in Chromium and WebKit at 393, 768 and 1440 pixels, including a frozen-video heartbeat check and the distinction between a normal end and abandonment. The live-domain browser pass uses the same controlled media fixture and does not open additional paid sessions. The real-provider recovery check above is separate evidence. Dependency audit and staged secret scan passed. The earlier GitHub Actions account-billing restriction is independent of these local checks.
