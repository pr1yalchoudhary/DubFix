# Tweeq — complete frontend visual restructuring

## Actual changes from the preceding version

The previous wide-waveform + editing/review two-column layout, top step-navigation strip and marketing-style upload hero have been removed. This revision uses the requested straightforward vertical workflow:

1. Minimal white header: Tweeq, tagline directly underneath, New Recording / Export only while a recording is open.
2. Compact file-selection card: "Upload your recording", "Choose an audio file to get started.", blue Choose File, existing drag/drop, consent and Fish disclosure. No hero or feature badge row. Open recording appears when a file has been chosen and retains the original upload handler/consent guard.
3. Prominent recording surface with file name, wide grey/blue waveform, thin blue playhead, blue region handles, playback, Undo/Redo and precise times.
4. Selection-first editing: editing fields stay visually/accessibly hidden until a valid region is finalized, or the user explicitly confirms the existing default region via Edit selection. No request is made by that confirmation. Presentation state is keyed by session/audio revision, so Apply/Undo/Redo hide the form until a new selection. Controlled draft fields remain mounted and their underlying App state is preserved.
5. A two-line segmented mode control: Correct Speech / Change what was said and Change Delivery / Change how it was said. Only the selected mode's existing panel is rendered.
6. Generate Preview sits inside the editing section. No empty replacement status box is displayed before generation. The replacement area reveals during generation, for a playable preview, or for an error that needs attention. Apply Edit remains disabled unless the existing strict valid-preview predicate succeeds. Regenerate reuses the original explicit generation handler.
7. Preview and comparison share one white section. Original / Edited labels call the unchanged original/current version selection. Export uses the same handler from both header and existing download action. History is a compact disclosure, shown when history exists.

## Change Delivery and advanced controls

Detected speech is first and labeled Your words. Automatic ASR, manual fallback, cache/version rules and editability are unchanged. Main chips are Natural, Excited, Calm, Confident, Sad, Nervous, Whisper, Dramatic. Existing preset direction values remain unchanged; Dramatic is an additional UI shortcut for an existing supported custom direction (no model, sampling or backend setting changes). Sarcastic remains available under More options rather than being removed.

More options is a native collapsed disclosure containing language, manual translations where required, sound cues and word-level effects. Existing update/apply handlers, field IDs, refs, tag insertion logic, validation and timing behavior remain. The optional original-words history field is also a small disclosure.

## Styling

The old stylesheet was replaced rather than layered with another override set. Exact requested tokens: background/input #F2F2F7, white cards, text #1C1C1E, secondary #8E8E93, accent #007AFF, hover #0066D6, border #E5E5EA, success #34C759, warning #FF9500, error #FF3B30. Tints use those same semantic colors. Cards are 24 px (20 px compact), inputs 12–16 px, actions pill-shaped at 44–48 px. Main text is restrained; no all-caps marketing headings, glow, purple, gradients, sidebar or glass navigation is present.

Font stack is -apple-system, BlinkMacSystemFont, Inter, Segoe UI, sans-serif. No fonts are bundled or downloaded. Existing original geometric SVG icons are reused as one consistent legally available in-project icon set; no Apple graphics, SF Symbols or kit assets were copied and no icon dependency was needed.

At <=760 px comparison/export stacks; <=560 px transport and selection controls wrap while retaining the wide waveform and touch targets. <=360 px header actions use another row instead of overflowing. Reduced-motion and keyboard focus rules remain. The file input is visually hidden but focusable. Error and warning text stays dark, with semantic red/orange accents rather than large diagnostic panels.

## What was preserved

Baseline SHA-256 checks confirm every backend/app Python file, frontend API helper, editor-state/fingerprint helper, preset/script helper, and all App editing handlers (the function body before the render) are unchanged. No voice/reference selection, model, Fish credentials, ASR, splicing, timestamp, Undo/Redo or export implementation changed. The only new state is presentation visibility for the required selection-first experience. Existing handlers are reused for header actions and regeneration.

40 frontend tests pass: 5 helper tests and 35 Vitest tests. Existing mocked workflows cover both modes, ASR, replacement reuse, staleness, cleanup, comparison, export and multi-edit Undo/Redo. Added tests verify compact upload, no old navigation/hero, selection-first reveal only on a finalized region, re-hiding after Apply without losing drafts, More options, all requested main tones, preserved Sarcastic, header export and reset. No real provider or paid requests were made. Production build passes.

## Render verification and screenshot limitation

The running localhost:5173 server returns HTTP 200 and serves the new Upload your recording markup and exact palette. The served stylesheet no longer contains the old editor-columns layout. No backend restart was performed, preserving the active session.

Requested screenshots of upload, waveform, Correct Speech, Change Delivery and generated preview could NOT be captured: a saved browser permission blocks automation of localhost. The earlier explicit denial forbids alternate browser/CDP workarounds, and this restriction was not bypassed. No mock image is presented as an application screenshot. DOM composition/visibility and workflow behavior were inspected through jsdom mocks, and responsive CSS rules were reviewed; these are not a substitute for pixel-level inspection. Rendered appearance is therefore not independently visually confirmed, and no claim of completed screenshot QA is made.

The transformation is structural, not only a color/radius adjustment: old hero/navigation/columns are removed, upload copy is replaced, header is rebuilt, editing becomes selection-first, delivery is reordered and progressively disclosed, preview is conditional and Apply/comparison labels are updated. If a tab still shows an old view, finish/export unsaved work before hard-refreshing (client session state is not durable).

## Files actually modified

- frontend/src/App.jsx — upload/export/header markup only; existing editing handlers unchanged.
- frontend/src/AppHeader.jsx — stacked brand/tagline and existing action wiring.
- frontend/src/EditorWorkspace.jsx — vertical composition, presentation-only selection reveal, compact preview/comparison.
- frontend/src/EditorSurfaces.jsx — visibility props, two-line mode control, compact quality/history disclosures.
- frontend/src/DeliveryControls.jsx — detected words first, requested tone shortcuts, collapsed advanced controls; original update/tag logic retained.
- frontend/src/WaveformEditor.jsx — visual palette/playhead/timeline labels only.
- frontend/src/index.css — complete replacement with the specified visual system and responsive layout.
- frontend/src/App.ui.test.jsx — renamed action labels and real workflow checks for the new presentation.
- README.md, COMPLETE_UI_REDESIGN.md — current behavior and verification limits.
