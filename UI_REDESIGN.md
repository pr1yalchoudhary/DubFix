# Tweeq workflow redesign — 25 October 2026

## Result

The editor is a single sequential workspace with four numbered cards:

1. **Select the moment** — current recording waveform, timestamp ruler, visible cursor, region dragging/handles, manually editable second boundaries, duration, selection playback, and 1×–16× zoom with reset.
2. **Give your voice a reference** — existing extracted clip, a reason for the transcript, and **Words spoken in the reference audio** with exact-word instructions.
3. **Make your edit** — preserved Correct Speech/Change Delivery tabs with mode explanations, input, preview action, preview player and **Insert replacement** action in that order.
4. **Compare and export** — Original/Current selector, an explicit playback-version label, a dedicated comparison player and MP3 download.

Existing branding, dark/lavender palette and rounded panels are retained. The numbered navigation links jump to each card. Reference and comparison sections stack on smaller screens; selection controls and mode controls also adapt to narrow widths.

## Bugs fixed

- Original comparison previously disabled correction and delivery inputs through `locked || original`. Comparison now controls a separate player and never changes editability.
- Switching comparison versions previously changed the main waveform URL, remounted it, initialized a new 0–3-second region and invalidated previews. The selection waveform now always loads the current recording; comparison has an independent source.
- Waveform initialization now restores an existing valid selection. Identical region events no longer clear previews. Genuine selection/text changes still invalidate stale previews while retaining all draft text.
- Start/End fields no longer force `toFixed(2)` during every keystroke. Local string drafts allow clearing a field and entering precise values; invalid intervals receive a visible explanation and disable generation/selection playback, rather than disabling text entry.
- Zoom uses the existing WaveSurfer API and keeps selection and text intact. Timeline markers track the waveform.
- Requests now have client time limits covering response-body reads, and clear timers in `finally`. Generation, insertion, upload and export failures restore controls and show actionable messages. No automatic frontend retry is introduced.
- Disabled generation lists the missing prerequisite (selection, transcript, script, reference or configuration). Busy locks have a prominent explanation. Export explains that an inserted edit is required.
- Failed insertion retains the saved preview for retry. Draft words remain visible after successful insertion, comparison switches and returning from export.
- Native players pause each other, and starting a native reference/preview/comparison player pauses waveform playback.

## Files

- `frontend/src/App.jsx`: state transitions and existing API orchestration; preserves drafts and delegates editor layout.
- `frontend/src/EditorWorkspace.jsx`: four-step layout, comparison playback and action explanations; reuses DeliveryControls and WaveformEditor.
- `frontend/src/WaveformEditor.jsx`: existing WaveSurfer integration with Timeline, zoom, synchronized manual selection and playback states.
- `frontend/src/editorState.js`: shared selection validation, equality checks and generation prerequisites.
- `frontend/src/api.js`: bounded client requests and export response handling. Endpoint paths and payload formats are unchanged.
- `frontend/src/index.css`: sequential layout, typography, section spacing, control hierarchy and responsive styles.
- `frontend/src/App.ui.test.jsx`, `frontend/src/api.ui.test.js`, `frontend/vitest.config.js`: DOM interaction and failure-recovery tests with fully mocked network/audio dependencies.
- Frontend package manifest and lockfile: Vitest/jsdom are development dependencies only; `pnpm test` runs all frontend checks.
- README and implementation notes reflect the revised workflow.

No backend source, Fish Audio integration, consent handling, reference extraction, splicing, model selection, endpoint contract or export format was changed for this redesign. No runtime mock feature was added.

## Verification

- **21 frontend tests passed**: 5 delivery-text helper tests, 12 React interaction tests and 4 client-request tests.
- **44 backend regression tests passed**, using fixture credentials and mocked provider calls; includes actual local FFmpeg splicing and 192 kbps MP3 export validation.
- **Production Vite build passed.**
- The running frontend and proxied backend health returned HTTP 200.
- A generated local 12-second sine-wave fixture uploaded through the running app with HTTP 200. Waveform and reference audio both returned HTTP 206 to range requests and valid WAV headers.
- **No Fish Audio generation requests and no paid API calls were made.** Testing budget usage for this task: $0. The user's per-request approval requirement remains in force.

The mocked interaction suite checks upload/consent, all four sections, timeline initialization, drag/manual selection synchronization, invalid input recovery, zoom calls, transcript and script entry, both editing modes, manual translation requirements, Original/Current playback URLs, preview validity, saved-preview insertion, failed-request recovery and export failure/success. All test network calls are mocked; no real key is used by those tests.

## Limits

Browser automation permission was previously declined, so rendered visual layout, actual pointer dragging and audible playback have not been browser-verified. DOM tests exercise the React logic with mocked WaveSurfer events; they do not verify real canvas rendering or sound. Responsive CSS is implemented but not screenshot-verified.

Real voice generation, resemblance and Drama 3's acoustic effects remain outside this UI verification. They still require explicit approval before each paid request and an authorized voice sample with the exact reference transcript. The configured API key was not displayed or moved.
