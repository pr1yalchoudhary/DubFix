# Quality-first reference selection and simplified voice setup

## Implementation order and behavior

1. Upload decodes locally through FFmpeg, preserving recording channels/rate, then runs local signal checks BEFORE reference selection.
2. The selector ranks contiguous original windows by usable activity and quiet-run length, excludes flagged clipping/spike/tonal/hiss-like intervals, requires >=60% potential activity and no inactive run over 1.5 s, and never pads or aggressively processes the selected reference. Source sample positions are preserved in metadata for diagnostics/API compatibility; UI no longer exposes reference management.
3. Runtime default remains 10 seconds pending controlled listening evidence. If no suitable 10 s window exists, try 8, 6, then 5 s with a warning. Under 5 s or no suitable material: clearly ask for a clearer recording. Shorter clips are below Fish's recommended target, so provider acceptance/fidelity remain unverified live.
4. Official duration/format/multiple-sample support was checked. Offline trial preparation can use one eligible 20/30 s window or multiple separate nonoverlapping 10 s files, instead of concatenating disjoint words. This has NOT changed the runtime Fish request or model settings.
5. Only after core tests passed, an optional gentle cleanup comparison was added. It is explicit, local, cached per session/revision and never automatically accepted. Original and Current remain untouched; accepting cleanup changes only the future voice reference before model creation. Existing cached models cannot be replaced through cleanup. Rejecting cleanup does not invalidate an approved preview.
6. The voice-reference UI card, player, timestamps and extraction explanations are removed. The editor has three steps. Small readiness/preparation status, quality warnings, optional cleanup, consent and authorized-sample disclosure remain.

## What signal checks establish

All checks use existing pydub/FFmpeg plus Python standard-library audioop/math/statistics; no dependency or external service was added. 100 ms analysis windows use 16 kHz mono for level/zero-crossing analysis and 2 kHz for narrow 50/60/100/120 Hz tone energy. Clipping indicators are checked on original-channel 16-bit samples, before downsampling. Indicators cover:

- Repeated near-full-scale samples: possible clipping/saturation, not proof of its original cause.
- Low-energy runs >=1.5 s: possible silent/unusable portions.
- Very low activity levels: recommend a healthier microphone/input level without clipping.
- Persistent near-pure low tones and persistent high zero-crossing activity: possible hum/hiss or other steady sound. Harmonics, instruments or vocal sounds can produce false positives.
- Low 10th-to-80th percentile level contrast: background-energy REVIEW warning, not an automatic rejection of continuous speech.
- Isolated >15 dB local level jumps: possible transient, impact OR loud syllable; avoid automatically for reference selection and ask for listening review.

Timestamp resolution is about 0.1 s and warnings are explicitly marked as Original-recording times, since edits change Current's timeline. No claim of verified speaker identity, emotional range, linguistic intelligibility or overlap/music detection is made. Quiet breaths/fricatives and background energy cannot always be separated. The selector finds signal-suitable candidates, not guaranteed clean speech. Severe damage cannot be restored by simple cleanup; users are told to rerecord when appropriate.

## Actual sample2 local comparison

Source: `C:/Users/user/Downloads/sample2.mp3` (24.149333 s). Local analysis measured about 0.074 s, excluding initial FFmpeg decode. Only abrupt-level indicators were flagged at 0.9–1.0 s and 13.2–13.3 s. These could be speech onsets, not established noise. No clipping, persistent-tone or hiss-like warning was triggered; absence of a flag does not prove absence of noise.

Prepared files in `test-results/reference-quality/sample2`:

- A: `short-1.wav`, original 2.6–12.6 s, 10 s mono 44.1 kHz WAV.
- B: `long-1.wav` (same interval as A) plus `long-2.wav` (13.3–23.3 s), 20 s total as two separate files. A single contiguous 20 s span would include a flagged interval, and this recording cannot provide 30 s without padding, so neither is used.
- `gentle-cleanup.wav` is an offline investigation candidate only. `cleanup-matched-1.wav` uses the SAME timestamps as A for a controlled raw-versus-processed comparison. `cleanup-selected.wav` is the best candidate under the cleaned recording's own analysis and may cover different words; do not confuse these experiments.
- `manifest.json` records quality findings, exact candidate paths/timestamps and the proposed trial. No model creation, ASR, generation or provider request was performed.

The actual sample2 warning is a spike indicator, so the runtime UI would not offer broad denoising for it. Optional cleanup is reserved for high-frequency/background-energy warnings; it is not presented as a repair for transients or severe clipping.

## Controlled paid test proposed, not executed

Keep account/key, authorized speaker, model, latency, output settings, exact phrase and restrained direction identical. Create private voice A from the selected 10 s sample and B from the two selected files using repeated `voices` fields with `texts` omitted, then generate one identical utterance per model. Use the existing Drama 3 mode if evaluating Change Delivery. Randomize A/B presentation and ask the user to assess identity/accent, rhythm, naturalness, breathing and artifacts. Inspect level/duration separately; neither louder nor longer is an automatic win.

This entails two potentially billable creation operations and two TTS requests. Obtain approval BEFORE EACH request, check applicable account pricing/available credit, stay within preferred $3 / hard $4 testing budget and stop if cost cannot be bounded. No paid requests are made by the preparation script. Do not permanently increase default duration until listening evidence supports it.

## Optional cleanup safety and caching

FFmpeg uses mild fixed `afftdn=nr=6:nf=-45`, with no pitch/speed change or automatic noise-source identification. Users compare full Original/cleaned audio at the same format/duration and accept/reject. Filtering can change transients/phase/timbre or sound worse; fewer signal warnings do not establish better cloning. No provider enhancement setting was changed.

Only accepted cleanup can replace the LOCAL reference file, never the user recording. Acceptance increments `reference_revision`; frontend fingerprints/backend preview ownership validation reject outdated previews. It leaves audio revision, ASR transcript cache, edit history, source timestamps and Undo/Redo untouched. Preview/choice operations use the session lock. Choices reject stale candidate IDs/revisions. Cleanup cannot accept after a private voice ID is cached, avoiding unwanted retraining or extra calls. Cache reuse and consent behavior remain as before; restart still loses in-memory sessions/models and may require fresh setup.

## Tests and rollout

70 backend tests passed in the final complete suite, including the new multi-sample trial planner and cleanup/reference-preview invalidation. Covered selection avoiding noise/clipping/long quiet; low-tone/quiet/spike indicators; short fallbacks; unpadded 10/30 s candidates; multiple nonoverlapping files; local-only upload; original/current/frame preservation; cleanup cache; explicit accept/reject; immutable cached voices; and stale previews. Existing two-edit, ASR, export and Undo/Redo tests passed. 35 frontend tests and the production build pass, including three-step UI without reference management, timestamped quality warnings, cleanup comparison/choice, retained preview on rejection, and all prior edit workflows. All provider traffic in tests is mocked.

No paid requests or new API keys/services/dependencies. No live speaker-similarity claim is made. Backend has not been restarted, preserving the user's active session; finish/export it before restart/reupload to exercise quality-first upload analysis. The HMR frontend remains backward-compatible with sessions lacking quality fields.

Files: backend/app/quality.py (new), backend/app/audio.py, backend/app/main.py, backend/app/sessions.py, backend/prepare_reference_trial.py (new), backend/tests/test_quality_selection.py (new), backend/tests/test_cleanup.py (new), backend/tests/test_audio_quality.py, frontend/src/App.jsx, frontend/src/EditorWorkspace.jsx, frontend/src/editorState.js, frontend/src/index.css, frontend/src/App.ui.test.jsx, README.md, IMPLEMENTATION.md, REFERENCE_QUALITY.md.

Official sources: https://docs.fish.audio/features/voice-cloning (Sample audio requirements, Multiple samples: aim for >=10 seconds per clip; clean mono single-speaker input; multiple clips supported) and https://docs.fish.audio/api-reference/endpoint/model/create-model (multipart upload). The guide recommends longer clear material but does not prove a 20/30 s improvement for this user or provide a universal maximum in the guide. Existing 44.1 kHz mono WAV, private fast model workflow, omitted texts and cached reference_id are preserved.
