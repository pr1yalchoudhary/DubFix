# Tweeq — focused UX and branding update

25 October 2026

## Changes

- Rebranded visible application text, monogram, browser title, backend API title, package name, export filename, README and project documents to **Tweeq**. The tagline is **One mistake shouldn't mean another take.** Existing project directories, modules, environment variables and API routes are unchanged.
- Removed the manual reference-transcription textarea and its generation prerequisite. Correct Speech still requires replacement text; Change Delivery still accepts its segment script and directions.
- Added the subtle phrase-context recommendation only for one- or two-word Correct Speech input. It never disables single-word corrections and disappears for longer text or Change Delivery.

## Why transcription was required and what replaces it

The old inline-reference TTS request requires `references[].audio` and an exact `references[].text`. Sending an empty transcript there would risk voice quality or violate the documented request contract.

The documented private-model workflow is the supported alternative. First preview creates a private fast voice using the existing extracted reference WAV and **omits `texts`**. Fish Audio performs reference recognition internally. The resulting model ID/state are cached in the existing session; both speech modes then use that ID as `reference_id` with their unchanged TTS model/quality settings. Upload remains entirely local and makes no provider call.

Preparation states are checked with bounded polling. Processing/failed models are retained rather than recreated per preview. Creation is not automatically retried on a timeout. Consent is still validated before setup. Legacy clients supplying `reference_text` keep the original inline-reference path; new clients omit it, and empty/omitted text selects automatic setup. No separate ASR endpoint, transcript editor, mistake detector, external provider, API key or dependency was added.

Sources verified before implementation: [Create Model](https://docs.fish.audio/api-reference/endpoint/model/create-model), [voice cloning](https://docs.fish.audio/features/voice-cloning), and [live OpenAPI](https://api.fish.audio/openapi.json). The schema explicitly says ASR is performed when model `texts` is unspecified.

## Modified files

- `backend/app/fish_audio.py`: private voice creation/status and TTS `reference_id` support, retaining legacy inline references.
- `backend/app/main.py`: optional legacy transcript field, per-session automatic setup, Tweeq API title/export name.
- `backend/app/sessions.py`: cached voice model ID/state.
- `backend/smoke_fish.py`: automatic setup by default; optional legacy transcript flag.
- `frontend/src/App.jsx`: removed transcript state/request requirement, Tweeq branding and download filename.
- `frontend/src/EditorWorkspace.jsx`: automatic setup explanation in the existing reference panel and conditional short-correction tip.
- `frontend/src/editorState.js`: removed transcript prerequisite and added tip predicate.
- `frontend/index.html`, `frontend/package.json`: visible page/application identity. No dependency was added; the existing lockfile/dependency installation was checked offline.
- `frontend/src/App.ui.test.jsx`, `backend/tests/test_voice_setup.py`: new and updated regression cases.
- `README.md`, this report and existing root project documents: current branding and workflow instructions. Historical investigation notes describe their earlier verification state; this report/README describe current behavior.

## Verification

- **50 backend tests passed**: all previous tests plus automatic setup without `texts`, private multipart reference upload, processing/failed state reuse, no creation retry on timeout, cached reference ID shared by Correct Speech and Change Delivery, saved-preview Apply, unchanged Original, changed Current and MP3 export.
- **29 frontend tests passed**: five text-helper tests plus 24 DOM/client tests. They verify no manual transcript field, one-word preview enabled, no `reference_text` sent, Tweeq branding, the conditional non-blocking tip, both modes, selection, preview, Apply, comparison, failures and export.
- Production build and Python source compilation checked.
- All provider operations were mocked. **No paid Fish Audio requests were made.** The API key was not changed or displayed. Preferred $3 / maximum $4 testing budget and approval before each paid test remain in force.

## Limits and costs

Live private-model preparation and acoustic quality have not been verified; those require an approved test. Automatic setup is an additional provider-side model/recognition operation once per new session and may have account-dependent costs. It does not request a generated sample. Later previews reuse the voice; normal TTS charges still apply.

Private models persist in the Fish Audio account until removed there. The existing in-memory cache is lost on backend restart, so a new session may create another model. Existing audio files, splicing, preview ownership/revision checks and export processing remain unchanged. Browser visual/listening QA remains unverified under previously declined browser access.
