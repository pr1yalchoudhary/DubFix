# Tweeq: native iOS-inspired presentation

Visual scope only. The existing React components, hooks, request functions, validation, playback/selection mechanics and backend architecture are retained.

## Presentation changes

- Light grouped background (#F2F2F7), white surfaces, dark text, restrained separators and blue actions. Shared tokens cover color, radius and typography. Action blue is slightly darker than the decorative #007AFF accent for readable white button text.
- System font stack: -apple-system, BlinkMacSystemFont, SF Pro Display, SF Pro Text, Inter, Segoe UI, sans-serif. Fonts resolve locally; nothing proprietary is bundled or downloaded.
- 20–24 px main cards, 14 px inputs, pill buttons/emotion presets and native-style segmented controls. No gradients, glow or new glass panels; subtle translucency is limited to the editor navigation.
- Minimal Tweeq wordmark with an original geometric waveform. Custom generic SVG controls are drawn in Icon.jsx; no Apple graphics/SF Symbols/icon library was copied.
- Wide desktop waveform, light timeline and blue selection. WaveSurfer's data/selection logic is unchanged; only its existing color parameters change.
- Existing Undo/Redo buttons are relocated from the history card into the waveform transport, using the same callbacks and enable conditions. Screen-reader names and hover titles remain explicit. History itself is unchanged.
- Correct Speech/Change Delivery segmented control is visually primary. The optional history-words field comes after the main editing fields, with the same ID/value/change handler.
- Upload, feedback, loading, quality disclosures, cleanup comparison, delivery fields, preview/apply, Original/Current, history and export all use the same light visual system. Existing meaningful warnings and authorized-sample disclosures remain.

## Responsive and accessibility decisions

Desktop workspace remains wide (1120 px content) rather than a phone-sized frame. At 800 px comparison/export stacks. At 600 px cards/spacing compact, controls wrap, three-step navigation stays available and transport timestamps use a full row. At 360 px numeric input padding tightens to keep precision controls usable. Long recording names/history words can wrap. No fixed-height form panels, hidden overflow page container or removal of major controls was introduced.

Most actions have a 44 px minimum height, with smaller spaced capsules/zoom controls. Visible focus outlines, labeled numeric boundaries, retained aria tab/group states, light native audio players and reduced-motion rules remain. The hidden file input now uses a visually hidden pattern instead of display:none, preserving keyboard access and the label focus ring. The existing direct numeric selection path remains available for keyboard editing.

## Validation and limits

36 frontend tests pass (5 text helpers + 31 Vitest), using local HTTP/WaveSurfer/audio mocks and a network-forbidden fetch stub. The new toolbar test verifies Undo/Redo location, accessibility names, enable rules, exact existing endpoints/revisions and refreshed Current URL. Existing tests cover upload/consent, numeric and drag selection, zoom, playback state, both modes, automatic ASR, preview invalidation, Apply reuse, errors, quality/cleanup choices, A/B, history and export.

Production build succeeds. The running Vite server returns HTTP 200 for the page, styles and new icon component. Baseline SHA-256 checks confirm all backend/app Python files plus frontend API/state/delivery helpers are unchanged. No backend/Fish/model/audio-processing/API settings changed. No Fish Audio request, paid service, dependency addition or backend restart occurred.

Live screenshot/viewport inspection was NOT performed: a saved browser policy blocks automation access to localhost, and that restriction was not bypassed. Responsive rules were inspected in source; jsdom tests do not establish pixel layout or real audio playback. Review at desktop/tablet/mobile widths in the existing browser to confirm visual polish. This limitation does not prevent the existing dev server from serving the redesign.

Files changed: frontend/src/index.css; frontend/src/Icon.jsx (new); frontend/src/App.jsx (import/markup only); frontend/src/EditorWorkspace.jsx (presentation/toolbar prop wiring only); frontend/src/WaveformEditor.jsx (visual colors, markup and relocated existing actions only); frontend/index.html (light theme-color); frontend/src/App.ui.test.jsx; README.md; IOS_REDESIGN.md.
