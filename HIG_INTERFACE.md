# Tweeq original HIG-inspired interface

Implemented the approved arrangement using original React/Tailwind components. The Apple UI kit is not a code or asset source. No Figma exports, SF Symbols, Apple font files, wallpapers, device frames or UI-kit components were imported. The existing original geometric Icon.jsx remains the icon source. System font aliases let the operating system choose a locally available font, without bundling or fetching fonts.

## Composition

- AppHeader: Tweeq wordmark, current recording filename, and original tagline. Filename can truncate in the header; the recording surface still exposes the full name.
- RecordingSurface: wide full-width waveform with unchanged playback, precise selection, zoom and existing Undo/Redo toolbar. Original quality warnings and optional cleanup remain associated with the recording.
- EditingFields / EditingModeControl: controlled Correct Speech and Change Delivery choices, existing fields, detected transcript, directions, presets and optional history words. State and callbacks remain in App/EditorWorkspace.
- ReplacementPreview: the existing generation action, approved preview and Apply action, independently grouped in the review column. Existing validation, loading, errors, boundary guidance and consent disclosure remain.
- ComparisonExport: Original/Current choice, playback and MP3 export below the replacement preview.
- EditHistoryList: existing applied/undone history below the editor.
- QualityDisclosure: original timestamped indicator details, with the same recommendations and poor-quality expansion behavior.

Desktop: full-width recording above editing/review columns. Review contains preview then comparison/export. At <=960 px columns stack in source/tab order: recording, editing, preview/apply, comparison/export, history. Existing compact breakpoints keep controls accessible at small widths. No phone bezel, simulated status bar or copied system chrome was added.

## Visual principles

Readable 17 px default body text with supporting label hierarchy; 32 px editor heading; system-ui font stack; shared neutral/blue color tokens; 24 px grouped surfaces, 16 px input corners, pill actions and 8/12/16/24-style spacing. Existing focus indicators, reduced-motion handling and accessible input names remain. Subtle navigation translucency is ordinary CSS, not an imported Apple material.

Sources used for general guidance: https://developer.apple.com/design/human-interface-guidelines/layout ; https://developer.apple.com/design/human-interface-guidelines/typography ; https://developer.apple.com/design/human-interface-guidelines/segmented-controls . These inform hierarchy, adaptability and grouped choices; implementation markup/styles are original and do not depend on UI-kit assets.

## Scope and validation

No backend/app source, API request helper, preview fingerprint helper, delivery preset or WaveformEditor code changed. Baseline SHA-256 checks cover these files. App's handlers/state and EditorWorkspace's state/ref ownership remain intact; only presentational composition and controlled UI rendering changed.

36 frontend tests (5 helper tests + 31 Vitest) and production build pass. Tests use HTTP/audio/WaveSurfer mocks with fetch forbidden, preserving checks for upload/consent, selection, zoom, mode changes, ASR, preview invalidation, Apply reuse, cleanup, comparison, export and Undo/Redo. Layout-presence assertions verify editing and review containers and recording filename placement. No Fish Audio calls, dependencies, model/voice settings or audio-processing changes. No backend restart or active-session reset.

Browser screenshot/layout inspection remains blocked by a saved browser permission; it was not bypassed. CSS breakpoints and DOM composition were inspected, and mocked workflows were exercised. These checks do not establish pixel-perfect rendering or real playback quality. Existing dev server can serve the update for user review.

Files: frontend/src/AppHeader.jsx (new); frontend/src/EditorSurfaces.jsx (new); frontend/src/App.jsx; frontend/src/EditorWorkspace.jsx; frontend/src/index.css; frontend/src/App.ui.test.jsx; README.md; HIG_INTERFACE.md.
