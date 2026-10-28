# Quality-first references and simplified setup

See REFERENCE_QUALITY.md for local indicators, selected 10 s default with shorter fallback, offline 20/30 s comparison preparation, explicit optional cleanup and removal of the reference management card. No paid tests or active backend restart.

# Continuity update using actual sample2 recordings

See CONTINUITY_DIAGNOSIS.md for measured 362 ms original / 42 ms previous / 414 ms locally restored sentence gap, exact preview insertion without source overlap, conservative edge padding, and local reconstruction files. No paid requests or backend restart.

# Speech quality investigation

See QUALITY_DIAGNOSIS.md for actual local-file measurements, voice routing, restrained presets, reference-window and format preservation changes. No paid tests or backend restart; active session preserved.

# Selected-segment ASR update

See ASR_UPDATE.md for verified contract, caching and local tests. Change Delivery now detects selected speech. Undo/Redo preserve all edits. No paid testing was performed.

# Implementation and validation record

## Multiple independent edits — 25 October 2026

Applied edits already spliced into Current; the frontend's retained/default selection made a second mode easy to apply to the previous phrase. Apply/Undo now clear selection, the refreshed waveform does not auto-select another region, previews bind to current revision/mode/inputs, and the backend checks requested mode/revision. Added simple Applied/Undone history and Undo restoring the exact previous WAV with a fresh monotonic revision.

**51 backend tests and 30 frontend tests passed; production build passed.** The two-edit Monday→Friday then excited/dramatic second-phrase flow was verified end to end using local WAV markers and mocked Fish Audio, including both clips in decoded MP3 and exact preceding-version Undo. No paid API requests or new transcription/services were introduced. See `MULTI_EDIT.md` for evidence and limits; live acoustic effects were not retested.

## Tweeq update — 25 October 2026

Current behavior is documented in `TWEEQ_UPDATE.md` and the refreshed README. Visible branding is Tweeq. Reference transcription is automatic inside Fish Audio private-model creation with `texts` omitted; the UI no longer asks for a transcript. One cached voice ID is reused by both modes without changing the selected TTS models or quality settings. One-/two-word Correct Speech input receives a non-blocking context tip. No provider/key/dependency was added.

**50 backend tests and 29 frontend tests passed**, with mocked provider requests and locally generated audio. Live setup/voice quality remains unverified and no paid tests were made. Historical notes below retain the behavior at their respective earlier stages; they are not current setup instructions.

## Preview failure diagnosis — 25 October 2026

Recorded preview requests were returning HTTP 502, not producing a successful clip subsequently lost by React. A page-top-only error combined with an idle preview placeholder concealed this failure in the editing section. Added persistent inline preview errors, safe HTTP/provider diagnostic categories and player-load failure handling. Existing Apply behavior remains unchanged and validated. Underlying historical provider failure is unknown because old logs did not preserve its category; no paid reproduction was attempted.

**27 frontend tests, 45 backend tests and production build passed**, including the complete Friday → preview → saved-clip Apply → changed Current / preserved Original → MP3 flow using local WAV fixtures and an HTTP test transport. See `PREVIEW_DEBUG.md` for evidence and verification limits. Backend restarted; sessions must be uploaded again.

## Apply Replacement fix — 25 October 2026

Investigation confirmed `/api/replace` already validates preview ownership/revision/selection, splices the saved clip, preserves Original and updates the Current revision. Preview generation alone deliberately does not edit the recording. The editor previously conditionally displayed an action named “Insert replacement”; it had no persistently visible “Apply Replacement” control.

The preview area now always shows **Apply Replacement**, disabled until a preview ID and playable URL exist. It appears beneath the generated audio player, applies that saved clip through the existing endpoint, switches comparison to Current and refreshes the waveform/player through the updated revision. Success explains that Original remains untouched. Selection, text, reference and mode changes invalidate stale previews. Missing optional duration metadata no longer breaks preview rendering; malformed preview responses display a clear error. Failed application retains the preview for retry. MP3 fetches bypass browser cache to retrieve the current edited export.

Validation: **23 frontend tests** (5 text helpers plus 18 DOM/request tests) and **44 backend tests** passed; production build passed. Tests cover the visible disabled/enabled Apply control, player ordering, preview invalidation, exact saved-preview request without regeneration, Current waveform/player revision refresh, original preservation, application errors and edited MP3 export. Local audio and provider mocks only; **no paid API requests**. Browser visual/listening verification remains pending under the previously declined browser access. No backend rewrite or UI redesign was performed.

## UI/workflow redesign — 25 October 2026

Implemented the four numbered sequential editor steps, waveform ruler and zoom, clearer reference instructions, adjacent preview/insertion controls, and independent Original/Current comparison playback. Fixed comparison-driven disabled inputs and selection resets, precise timestamp entry, stale-preview invalidation and request failure recovery. Draft text is preserved across mode/comparison/selection changes.

Validation: **21 frontend tests**, **44 backend regressions**, and production build passed. The running app accepted a local 12-second fixture; waveform/reference range requests returned valid WAV headers. No paid requests were made. Backend source and provider behavior are unchanged. Browser visual/listening checks remain unverified because prior browser access was declined. See `UI_REDESIGN.md` for changed files, coverage and limitations.

The key has since been configured and its application loading verified without displaying it. This does not establish successful provider authentication or generation. Historical notes below describe the state at their original verification dates.

## Change Delivery extension — 24 October 2026

Added Correct Speech / Change Delivery tabs, eight tone presets, custom direction, manual segment text, cursor-position sound cues, selected-word Emphasis/Whisper, and a manual language/translation workflow. The existing reference, consent, previews, crossfading, comparison and export pipeline are reused. Correct Speech defaults and legacy request fields are preserved.

The existing Fish adapter supports explicit **`model: drama-3`** for delivery, while correction retains `FISH_AUDIO_MODEL`. MessagePack continues to carry raw authorized reference bytes and the manual transcript; current OpenAPI supports this request encoding and WAV response format. No persistent voice model, extra key, provider, automatic transcription, translation service, or fallback is introduced.

Validation: **44 backend tests passed** (the original 16 plus 28 delivery cases), **5 frontend text-helper tests passed**, production build passed and Python source compilation passed. Contract tests verify header selection rather than a model field in the payload, text composition, raw reference reuse, translation requirements, markup rejection before API calls, preview metadata, multiple independent takes, selected-preview insertion without another TTS call, unchanged original, MP3 export, legacy Correct Speech model selection, safe Drama 3 failure messages and timeout retry behavior.

The key is still a placeholder. **No authenticated Drama 3 request or acoustic acceptance test has run.** Emotion change, recognizable voice identity, sigh/laugh/breath/pause realization, whisper/emphasis and multilingual pronunciation are unverified. The required early live test was blocked by missing credentials and a consented recording. The CLI smoke tool now supports an explicit delivery test once those are available.

Browser visual verification is also incomplete due to the previously declined localhost browser permission. No advanced takes/history UI, extra effects toolbar, mixed-language tags, undo system or three-way comparison was added. All documented paired delivery tags are accepted in manually entered scripts; the UI provides only the two priority paired-tag helpers.

The original MVP validation record below is retained as the baseline.

24 October 2026

## Implemented

- React/Vite/Tailwind single-page interface with upload, editor and export screens.
- Explicit speaker consent checked by frontend and backend.
- MP3/PCM WAV validation, 25 MB / 15-minute limits, FFmpeg normalization and ffprobe metadata validation.
- WaveSurfer 7 waveform, draggable selection, numeric boundaries and selection playback.
- Local 10-second reference extraction (5–15 seconds when available), audible reference and manual transcript field.
- Fish Audio direct-reference adapter using Bearer authentication, MessagePack and `POST /v1/tts`; WAV output.
- Independent preview playback; approved saved preview inserted without regeneration. Preview loudness is matched within a bounded gain range before approval; insertion only overlaps boundary samples for crossfades.
- Up to 50 ms boundary crossfades, sequential corrections, preserved original, A/B playback and 192 kbps MP3 download.
- UUID validation, session ownership checks, stale-preview rejection, per-session concurrency locks, safe provider error messages, bounded output and limited retries.
- Ignored backend `.env` with a placeholder, example environment file, setup guide and opt-in live smoke script.

## Verified

`python -m pytest -q`: **16 passed**.

Tests include a 90-second MP3 upload; WAV conversion and reference extraction; consent rejection; invalid/empty/oversized uploads; short and silent references that remain playable; invalid timestamps and text; missing-key errors; preview ownership and stale-selection rejection; saved-preview insertion; byte-for-byte original preservation; crossfades at start/end/full-recording boundaries; valid MP3 decoding and 192 kbps bitrate; provider error mapping and retry counts; and suppression of raw provider error content.

Audio generation in tests uses explicitly declared sine fixtures and HTTP test transport. There is **no mock mode or synthetic fallback** in the application.

`vite build`: **passed**. Dependency installation completed successfully, including esbuild's install script. Python source compilation passed.

Local runtime checks: frontend `/` returned **HTTP 200**; proxied `/api/health` returned `status=ok`, `ffmpeg=true`, `ffprobe=true`, `fish_configured=false`. Both requested development ports are serving.

The test runtime reports upstream deprecation warnings for pydub/audioop and Starlette's httpx TestClient support. Python 3.12 is used; Python 3.13+ is deliberately excluded by the setup instructions.

## Pending verification

No real Fish Audio key or consented voice recording was supplied. Authenticated API calls, recognizable voice resemblance, and a real AI correction demo have **not** been tested. The user said those inputs will be supplied later. The pre-implementation authenticated smoke test was therefore blocked, and provider integration remains isolated in `backend/app/fish_audio.py`.

Browser automation permission was declined for the localhost preview. Rendered appearance, drag interactions, browser playback and download behavior have **not** been visually verified. Production compilation and server responses do not establish browser-level success.

## Provider contract and deviations

Official docs and live OpenAPI were reviewed before application code. The single provider endpoint implemented is **`POST https://api.fish.audio/v1/tts`**; no authenticated request has yet been sent.

Direct references eliminate persistent `/model` creation. MessagePack carries raw audio bytes and an exact manual transcript. This adds `reference_text` to `/api/preview` and a `/api/reference/{session_id}` player endpoint. The current persistent-model enhancement field is `enhance_audio_quality`, rather than the proposed `enhance`, but is not used in this workflow. Full sources and request details are in README.md.

## Deliberately excluded

Automatic transcription, persistent voice models, auth, database, cloud storage, multi-speaker audio, video, undo/history UI, stretching, advanced reference selection, background-noise matching and advanced waveform controls. Local audio persists on disk until manually removed; session metadata is lost at restart.

## Remaining live-demo checkpoint

Configure the real key only in `backend/.env`, restart the backend, upload a consented recording, enter the exact reference transcript, generate and listen to a correction, insert it, compare, and download. Confirm voice similarity by listening to the generated clip and original. A successful API status alone is insufficient to pass that criterion.
