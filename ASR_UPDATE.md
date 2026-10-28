# Automatic selected speech detection

Official contract: POST https://api.fish.audio/v1/asr, Bearer auth, model header transcribe-1-pro, multipart audio WAV; ignore_timestamps=true, diarize=false, tag_audio_events=false. No automatic retry or fallback model. Live account access and acoustic accuracy require separately approved testing.

Change Delivery automatically detects words after a finalized valid selection. Its editable field supports corrections and manual fallback on failure. Correct Speech stays manual. No full transcript editor, service or dependency was added.

WaveSurfer region-update invalidates previews/text without starting ASR; region-updated finalizes. Numeric inputs finalize on blur. Frontend pending requests are shared; cached edited words are reused for unchanged selections. Backend caches successful transcripts by session/revision/start/end under the session lock. Extraction uses CURRENT WAV and the same millisecond rounding as splicing. Apply/Undo/Redo advance revisions and clear backend cache; late frontend results are ignored. Original, cumulative edits and MP3 export are preserved.

Redo now restores saved audio without generation. A new Apply clears its redo branch.

Tests: 51 existing backend tests passed; four new ASR cases passed (exact current-region multipart WAV, auth/model header, cache, stale version, access failure and empty/invalid responses). The updated two-edit integration feeds detected text into Drama 3, checks both replacements in real FFmpeg MP3 output and byte-exact Undo/Redo. Frontend 32 tests passed (5 helpers + 27 Vitest), covering finalized selection, stale responses, cache, manual fallback and the two-edit example without typing the second phrase. Production build passed. No paid API calls or live acoustic tests were made.

Files changed: backend/app/{main,fish_audio,sessions}.py; backend/tests/{test_asr,test_multi_edit}.py; frontend/src/{App,WaveformEditor,EditorWorkspace,DeliveryControls}.jsx; frontend/src/App.ui.test.jsx; README.md; IMPLEMENTATION.md; ASR_UPDATE.md.
