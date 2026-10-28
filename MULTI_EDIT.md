# Independent sequential edits — 25 October 2026

## Cause and fix

The splice implementation already used `session.current`, so applied edits were cumulative. The frontend retained the region around the last replacement after Apply, and waveform initialization created a default region when no valid selection existed. Switching modes while that region remained selected could therefore prepare another edit for the same phrase. There was no history to make applied vs merely previewed changes clear, and Apply did not explicitly compare its requested editing mode with the saved preview's mode.

After Apply or Undo, the selection is now cleared. The refreshed WaveSurfer instance does not recreate a default region. Drag or enter both boundaries to select the next phrase on the updated recording; generation remains disabled until then. Playback duration, comparison source and waveform source all follow the latest revision. Changing modes does not apply anything and invalidates the previous mode's preview.

## Integrity

- Each preview is bound to session, current revision, selected region, mode, script and delivery settings in the frontend. Editing these inputs invalidates Apply.
- New preview/Apply requests send `revision`; Apply also sends `mode`. Backend checks these against the current session and saved preview, in addition to ownership, range and already-used checks. New fields are optional for older API clients; their existing session/revision/range protections remain in place.
- Apply inserts the saved clip into the latest Current WAV, never the original and never regenerated audio.
- History records edit number, mode, optional original phrase, replacement words/direction and Applied/Undone status. An optional original-words field is metadata only; no transcription is introduced.
- Undo uses the already saved previous WAV and duration, marks the most recent active history entry Undone, and increments the revision. Revisions never go backwards or reuse old file names, so old previews/cache entries cannot become valid after Undo. Further edits can be made after undoing.
- Export encodes the latest current recording, containing every active edit. Original comparison always uses the untouched original. Undoing all edits restores it exactly; there is then no edited MP3 to download until another edit is applied.

## Acceptance sequence

The backend integration test uses these exact text requests:

1. Original phrase: **We're launching next Monday**. Correct Speech replacement: **We're launching next Friday.**
2. Select a separate interval shifted to the updated timeline after the first replacement changes duration. Change Delivery script: **I can't wait for you to try it!**, direction **excited and dramatic**, header **model: drama-3**.
3. Apply both saved previews. Assert two Applied history entries, unchanged Original and preserved first-edit PCM after the second splice.
4. Export and decode the actual MP3. Distinct local audio markers from both replacement clips are present at their expected positions in the final recording.
5. Undo edit 2. The restored WAV is byte-for-byte identical to the result after edit 1, with its duration restored. Undo edit 1 restores the original bytes. Stale and wrong-mode Apply requests are rejected; Apply/Undo/export make no generation calls.

The React interaction test performs the corresponding two-preview/two-Apply flow, enforces a fresh selection after each Apply, verifies revision changes and history, and undoes the second edit. Test speech is represented by locally generated audio and HTTP mocks, not live Fish Audio. This verifies the editing pipeline and exact text/model requests; live word pronunciation and Drama 3 emotion were not retested.

## Validation and scope

**51 backend tests, 30 frontend tests and production build passed.** No paid API calls were made. Existing voice preparation, model choices, audio quality settings, consent, reference handling and API key are unchanged. No provider, dependency, transcription, multitrack system or redo stack was added.

Changed implementation: `backend/app/main.py`, `backend/app/sessions.py`, `frontend/src/App.jsx`, `frontend/src/WaveformEditor.jsx`, `frontend/src/EditorWorkspace.jsx`, `frontend/src/editorState.js`, small history/input styles, and focused tests in `backend/tests/test_multi_edit.py` and `frontend/src/App.ui.test.jsx`.

Session/history metadata remains in memory as before. Restarting the backend expires sessions; saved audio files remain on disk. Browser visual/listening verification remains incomplete under previously declined browser access.
