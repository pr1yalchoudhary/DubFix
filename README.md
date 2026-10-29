# Tweeq

**One mistake shouldn't mean another take.**

A local audio editor: upload → select → preview → apply → compare → download. **Correct Speech** replaces spoken words; **Change Delivery** re-performs them with Fish Audio Drama 3. No manual voice-reference transcription is required.

## Prerequisites

- Python **3.10–3.12** (pydub uses audioop, removed in Python 3.13).
- Node.js **20.19+ or 22.12+** and pnpm or npm.
- FFmpeg and ffprobe with the libmp3lame encoder.
- One Fish Audio API key, kept only in ignored `backend/.env`.
- A consented single-speaker MP3 or PCM WAV, at most 25 MB / 15 minutes. Voice setup prefers 10 seconds of suitable material; 5–8-second fallbacks warn about reduced fidelity. Very short, quiet, noisy or clipped recordings may need rerecording.

Windows: obtain an essentials build from [Gyan](https://www.gyan.dev/ffmpeg/builds/), linked by [FFmpeg](https://ffmpeg.org/download.html), and add its `bin` folder to PATH. Alternatively set `FFMPEG_PATH` and `FFPROBE_PATH` in `backend/.env`. The existing checkout also recognizes ignored `.tools/ffmpeg/ffmpeg.exe` and `.tools/ffmpeg/ffprobe.exe`.

macOS: `brew install ffmpeg`. Ubuntu/Debian: `sudo apt install ffmpeg`. Verify with `ffmpeg -version` and `ffprobe -version`.

## Install and configure

From the existing project root (the directory name is unchanged):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
# Only on first setup, if backend/.env does not already exist:
Copy-Item .env.example backend/.env
cd frontend
pnpm install
```

With npm use `npm install`. On macOS/Linux use `.venv/bin/python`.

Set `FISH_AUDIO_API_KEY` in `backend/.env`. Keep the existing `FISH_AUDIO_MODEL` setting for Correct Speech; its default is `s2.1-pro-free`. Change Delivery always sends the `model: drama-3` header. Neither mode selects a model through a body field. Never put the key in a `VITE_` variable, chat, source file or log. Restart the backend after changing `.env`.

## Run

### Deployed frontend/backend and demo access

Public free usage is implemented behind an explicit rollout mode. The safe default
still uses demo access. See [PUBLIC_USAGE.md](PUBLIC_USAGE.md) for the 2-per-visitor /
10-global operation budget, Upstash setup, anonymous sessions, emergency switch,
tests and deployment order. The demo instructions below apply to `AI_ACCESS_MODE=demo`.

The frontend supports a separate backend origin for both API calls and media playback.
In Vercel, set `VITE_API_BASE_URL=https://tweeq-backend.onrender.com` for the production
environment, then rebuild/redeploy the frontend. This is a public URL, not a secret.
For localhost, leave it unset or empty: `/api` continues to use the existing Vite proxy.
For local development against Render, use `frontend/.env.local` with the same URL.
Vite reads this variable at build/start time; restart after changing it.

Before exposing Fish Audio operations, deploy the backend changes to Render. Set
`DEMO_ACCESS_TOKEN` in Render's server-side environment to a cryptographically random
secret of at least 32 characters. Generate it locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the same variable in ignored `backend/.env` for local AI editing. Keep
`FISH_AUDIO_API_KEY` and `FISH_AUDIO_MODEL` on the backend as before. Never put either
secret in Vercel, a `VITE_` variable, source code, or a URL. Share the demo access code
privately with authorized testers. Enter it in the frontend's **Demo access** password
field before generating a preview or selecting Change Delivery. The code is kept in
page memory only and must be entered again after reload. If speech detection already
failed before the code was entered, use its retry action. Invalid credentials do not
cause automatic retries or provider requests.

The backend protects `POST /api/preview` (including private voice creation) and
`POST /api/transcribe` with constant-time bearer-token verification. Missing or short
server configuration disables these routes with 503; missing/invalid credentials
return 401. This applies on localhost too. CORS allows exactly the production Vercel
origin and the two existing localhost origins, including the Authorization header.
No cross-site cookies are required. CORS is not the access-control mechanism.

Uploads, local audio processing, audio playback and downloads remain available without
the demo code. Audio URLs contain no credentials. This is a shared demo gate, not
per-user authentication, recording ownership enforcement, rate limiting or a spending
cap: anyone holding the code can use AI operations. Rotate it in Render to revoke
shared access. In-memory sessions still expire on backend restart; existing recording
storage/retention behavior is unchanged. This change prepares the repository; it does
not modify the live Render or Vercel environment or deploy either service.

Local verification (no paid provider calls):

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
node --test src/deliveryText.test.js
node node_modules/vitest/vitest.mjs run
node node_modules/vite/bin/vite.js build
```

Terminal 1, from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
pnpm dev
```

Or use `npm run dev`. Open [Tweeq](http://localhost:5173). Backend [health](http://localhost:8000/api/health) and [API docs](http://localhost:8000/docs) are on port 8000. Vite proxies `/api` to the backend. Keep both servers running and bound to loopback; this local MVP has no authentication.

## Five-step demo

1. Upload a single-speaker recording and confirm you own the voice or have the speaker's permission.
2. In **Select the moment**, drag the waveform or enter Start/End seconds. Use selection playback and zoom for precision. Recording quality is checked locally and a suitable voice sample is prepared automatically; no reference management or transcript entry is needed.
3. In **Make your edit**, choose Correct Speech and enter corrected words, or Change Delivery, review the detected words and choose a direction. Click **Generate Preview**. The first preview prepares a private Fish Audio voice; later previews reuse it.
4. Listen to the generated clip and click **Apply Edit**. Previewing alone leaves Current unchanged. Applying inserts the saved clip without generating speech again.
5. Compare **Original** and **Current** in Step 3 and click **Download MP3**. The export is the current edited recording at 192 kbps.

For a demo, record a neutral sentence containing “March fifth”, select that phrase, and correct it to “April fifth”. A subtle tip appears for one- or two-word corrections: include a few words before and after the changed word for a more natural result. This is advice only; single-word edits remain enabled.

## Automatic voice setup

The original direct-reference TTS request needs both raw reference bytes and an exact transcript. The current UI instead uses Fish Audio's documented private voice-model workflow:

1. Upload validates consent, decodes locally to 16-bit WAV preserving the recording sample rate and channels, analyzes level/noise/clipping indicators, then selects a suitable contiguous mono 44.1 kHz sample. The default remains quality-selected 10 seconds, with shorter 8/6/5-second fallbacks when needed; samples are never padded. **Upload makes no provider request.**
2. On the first valid preview, the backend sends `POST https://api.fish.audio/model` with multipart `type=tts`, a Tweeq session title, `train_mode=fast`, `visibility=private`, `generate_sample=false`, and the existing reference WAV as `voices`.
3. **`texts` is omitted entirely. Fish Audio performs reference recognition internally.** Voice-reference setup needs no separate transcription request. Change Delivery separately transcribes only its selected segment through Fish ASR, using the same key.
4. The returned `_id` and `state` are cached in the existing in-memory session. If preparation is pending, bounded read-only `GET /model/{id}` checks run. A still-processing or failed model produces a clear error; it is not recreated on each attempt.
5. TTS uses the cached ID as `reference_id` on the existing `POST /v1/tts`, with the same model header, WAV format, sample rate and latency setting as before. No sound-quality or fallback-model changes were made.

The existing HTTP adapter uses Bearer authentication and MessagePack for TTS. The optional legacy `reference_text` request field remains supported: old clients supplying a transcript can still use inline references. New UI clients omit it. Empty or omitted reference text selects automatic setup.

Model creation is never automatically retried: an interrupted creation might already have made a private model. A returned model ID is retained while processing and shared between Correct Speech and Change Delivery. Different simultaneous previews for one session are serialized by the existing lock.

Official contract checked on 26 October 2026: [Create Model](https://docs.fish.audio/api-reference/endpoint/model/create-model), [voice cloning](https://docs.fish.audio/features/voice-cloning), [live OpenAPI](https://api.fish.audio/openapi.json), and [Drama 3](https://docs.fish.audio/features/text-to-speech/drama-3).

### Costs and retention

Automatic setup introduces one private-model creation/recognition operation per new session, followed by the usual TTS requests. Account-dependent provider charges may apply; do not assume setup is free. No sample generation is requested during creation. Models are reused rather than created per correction. No live setup or generation request was made while implementing this change.

Private voice models remain in your Fish Audio account until you remove them. Local session metadata is in memory and is lost on restart; a new session may create another private model. No automatic remote deletion, database or persistent account architecture was added. Existing local audio folders and API route names remain unchanged.

The preferred API testing budget is **$3**, with a **$4 maximum**. Every paid test request requires explicit approval. Current local regression tests consume no Fish Audio credits.

## Change Delivery

Choose Natural, Excited, Confident, Calm, Nervous, Sad, Sarcastic or Whisper, or write a custom direction. Natural sends no direction; custom directions are bracketed once. Change Delivery detects the finalized selected words automatically through `/v1/asr` with `model: transcribe-1-pro`. Review the editable words, choose a direction, preview and apply. Region dragging does not trigger requests; release the selection or leave the timestamp field to finalize. Failures allow manual entry or explicit retry. No automatic retry or model fallback is used. Live Pro access depends on the account.

Select words and click Emphasis or Whisper to wrap them. Laugh, Sigh, Breath and Pause insert cues at the cursor. All documented paired tags below are accepted; the toolbar prioritizes Emphasis/Whisper.

```text
[excited and enthusiastic] Welcome everyone!
I'm fine. [sigh] Really.
Our <emphasis>biggest launch</emphasis> is tomorrow.
<whisper>Keep this a secret.</whisper>
Wait. [pause] I have something to tell you.
<soft>Gently.</soft> <fast>Hurry.</fast> <slow>Listen carefully.</slow>
<stress>This word.</stress> <forceful>Stop.</forceful>
```

For another language, choose English, Hindi, Spanish or French and manually enter the translated words. The text itself determines the spoken language; the optional provider `language` field is a normalization hint. There is no automatic translation. The same cached voice is reused; pronunciation and voice similarity may vary. Experimental language-switching tags are excluded.

Demo: preview an excited version of a neutral announcement, then try a sigh and an emphasized phrase. Apply your preferred preview, compare, and export. Optional Spanish text: `Nuestro gran lanzamiento es mañana.` Directions and sounds may be inconsistent and must be evaluated by listening.

## Architecture and safeguards

- `frontend/src/App.jsx`: existing upload/editor/export state and API orchestration.
- `frontend/src/EditorWorkspace.jsx`: four-step workspace, editing modes, previews, comparison and short-correction tip.
- `frontend/src/WaveformEditor.jsx`: WaveSurfer Regions/Timeline, selection, numeric boundaries, playback and zoom.
- `backend/app/main.py`: FastAPI endpoints and per-session voice preparation.
- `backend/app/fish_audio.py`: private-model creation/status and existing TTS adapter.
- `backend/app/sessions.py`: session voice cache, recording revisions, previews and locks.
- `backend/app/audio.py`: unchanged ffprobe/FFmpeg/pydub extraction, preview-level matching, crossfades and MP3 export.

Audio stays in `backend/audio/<session UUID>/`. Original is never overwritten. Preview IDs bind to the session, recording revision and selected interval. Changes to selection, text or mode invalidate stale previews. Apply uses the already saved audio, with up to 50 ms crossfades; it does not regenerate, stretch or change its gain. Current playback sources include revision identifiers; exports bypass browser cache.

Errors appear beside the preview and at the page top. Apply remains disabled until a playable preview exists. Safe provider diagnostic codes identify authentication, credit, processing, network and malformed-audio failures without exposing credentials, audio/text payloads or raw provider messages.

## Tests and live verification

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
pnpm test
pnpm build
```

Tests use explicit local sine-wave WAV fixtures and HTTP mocks; no runtime mock or fallback voice is available in the app. Automatic setup tests verify omitted `texts`, private fast creation, model reuse across both modes, processing/failure handling, TTS with `reference_id`, Apply, Original preservation and export. Legacy inline-reference regression tests remain in place.

The actual key's loading and read-only account authentication were previously verified. Live automatic voice setup and acoustic quality have **not** been tested; a separately approved paid test is still required. Browser visual/listening checks also remain incomplete under previously declined browser access.

An opt-in CLI uses the same adapter and requires speaker consent:

```powershell
cd backend
..\.venv\Scripts\python.exe smoke_fish.py --audio "C:/path/to/your-recording.wav" --text "The meeting is on Friday." --consent
```

For delivery add `--mode delivery --direction "excited and enthusiastic"`. For manual Spanish use `--language es` and Spanish `--text`. This creates a private model for that CLI run unless the optional legacy `--transcript` is supplied. It may consume credits and must not be run as a paid test without approval. Listen to output to assess resemblance and effects; decoding alone does not establish quality.

## Multiple independent edits and Undo

Apply the first preview, then select the next phrase in the **updated current waveform**. Apply clears the old selection so switching modes cannot accidentally reuse it. Both Correct Speech and Change Delivery can be applied repeatedly in one session. Each replacement may change total duration; always choose subsequent timestamps from Current.

Edit History lists each applied edit and its mode, words/direction and status. You may optionally enter the original selected words for history; Correct Speech does not transcribe them; Change Delivery detects its selected words. **Undo last edit** restores the preceding saved recording and duration. **Redo last edit** restores undone audio; a new Apply clears the redo branch. Original remains untouched; Current and MP3 export include all active edits. Previewing and switching modes never apply changes automatically. See `MULTI_EDIT.md` for the local two-edit acceptance test.

## Known limitations

Single speaker, basic reference extraction, manual correction regions, imperfect prosody/background-noise matching, no automatic translation or full-recording transcription, no video, no multitrack editing, and no durable session database. Corrected duration may differ slightly. To delete local recordings, stop the backend and remove the appropriate UUID folders; deleting local files does not remove private models from Fish Audio.

See `TWEEQ_UPDATE.md` for this update's implementation and validation record. Historical investigation notes remain in the other project documents.

ASR caches successful transcripts by session, current revision and exact start/end timestamps. Apply, Undo and Redo invalidate transcripts and previews. Only selected CURRENT audio is sent, using the same millisecond boundary rounding as replacement. ASR may consume credits. Development tests use mocked responses and local audio; no paid requests were made.

## Speech quality and local diagnostics

Excited now requests restrained, conversational enthusiasm and reference-like accent/pacing. Other forceful presets have been softened. Custom directions remain editable; stronger performance can still change pitch and voice similarity. No model, sampling parameters, cloning mode or provider settings changed. New uploads preserve their sample rate and channels through Current and MP3 export; Fish WAV output remains mono 44.1 kHz and is properly resampled to the recording before preview. Mono generated audio does not recreate the original stereo ambience. Existing sessions retain their existing format.

Saved successful previews now also retain `<preview-id>-provider.wav`, the exact provider response, beside the approved preview for local diagnostics. These have the same local session lifetime/privacy as other generated audio. Preview preparation matches active-speech energy with bounded gain and peak protection, preserves available selected edge ambience, and uses short internal ramps. Apply inserts the exact approved preview without overlapping or consuming source context; no stretching or pitch adjustment is used. Listen to the preview before Apply: splicing cannot repair a voice mismatch already present there. See `QUALITY_DIAGNOSIS.md` for measured findings and limits. Finish/export an active session before restarting the backend to use the new processing code.

## Continuity and sentence spacing

Apply now preserves every frame outside the selected interval. Preview preprocessing preserves available low-energy edge room tone/breath-like material, replaces only near-silent provider padding with a vocal guard, and uses 5 ms internal ramps without shrinking the timeline. Active boundary and duration-change notes help you choose quiet phrase boundaries; they do not move your selection automatically. See `CONTINUITY_DIAGNOSIS.md` for actual sample2 comparison measurements and local listening artifacts.

## Quality-first voice preparation

Local 100 ms checks flag possible clipping, long quiet stretches, very low speech levels, persistent tonal/high-frequency activity, limited level contrast and abrupt spikes. Warnings identify approximate times in **Original**, not the edited timeline. These indicators cannot verify intelligibility, speaker identity, overlapping speakers, music, or the exact source of a sound. Suitable windows exclude flagged clipping/spikes/persistent tone/high-frequency intervals and long pauses. If none are available, Tweeq recommends a clearer recording; severe distortion cannot be promised repair by filtering.

Voice management is automatic. The separate reference card/player/timestamps have been removed. Recording warnings remain visible via a compact disclosure; meaningful poor-quality warnings and speaker consent remain. Both editing modes share the same cached private voice model.

The default is NOT automatically increased to 30 seconds. Fish's guide recommends at least 10 seconds per sample and supports multiple `voices` files. Prepare local controlled candidates with:

```powershell
.venv\Scripts\python.exe backend/prepare_reference_trial.py C:/path/recording.mp3 test-results/reference-trial
```

This command makes no provider requests. It writes quality findings, a selected 10-second sample and eligible contiguous 20/30-second or separate nonoverlapping 10-second samples, plus raw-versus-gentle-cleanup listening candidates. It refuses the source's folder as output. A live 10-vs-20/30 test needs separate approvals for each model creation and each generation; model/settings/script must be held constant. Longer or processed samples are not assumed better.

For suitable noise indicators, **Compare gentle cleanup** creates a local FFmpeg `afftdn=nr=6:nf=-45` candidate. Users hear Original and cleanup, then explicitly choose **Use cleanup for voice setup** or **Keep original voice**. Cleanup never replaces Original or Current and is never automatically accepted. It is offered before cached voice creation only, preventing unexpected model recreation or charges. Acceptance changes the voice-sample revision and invalidates old previews; rejection preserves an existing valid preview. Existing edits, audio timestamps, ASR cache and Undo/Redo remain intact.

See `REFERENCE_QUALITY.md` for limits, test evidence, and the actual sample2 controlled comparison plan. Backend changes require a restart; finish/export an active in-memory session first.

## Interface

Tweeq uses a light, native iOS-inspired presentation: system fonts, grouped white surfaces, blue controls, a wide waveform and Undo/Redo beside playback. All editing behavior and backend integrations are unchanged. See `IOS_REDESIGN.md` for presentation-only scope, accessibility/responsive decisions and validation limits. No Apple font or proprietary graphics are bundled.

The approved HIG-inspired arrangement uses original presentation components: full-width recording above editing/review columns, stacking in workflow order at compact widths. It does not embed Apple UI-kit components, fonts or assets. See `HIG_INTERFACE.md` for component mapping and validation.

## Current frontend structure

The latest redesign supersedes the earlier two-column HIG layout: compact upload, stacked brand/tagline with New Recording/Export, prominent recording, selection-first editing, Generate Preview, and one preview/comparison section. Change Delivery shows Your words and simple tone chips first; More options holds language, translations and effects. User-facing comparison labels are Original / Edited, while API values remain original/current. See `COMPLETE_UI_REDESIGN.md` for the exact palette, changed files, tests and explicit screenshot-verification limitation.
