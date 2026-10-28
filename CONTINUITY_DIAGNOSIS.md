# Audio continuity: analysis of the actual sample2 recordings

## Input identity and measured results

`C:/Users/user/Downloads/sample2.mp3` decodes byte-for-byte to `backend/audio/8f927495-dafe-49fe-9a56-ccf84415f988/original.wav`. `C:/Users/user/Downloads/tweeq-corrected2.wav` matches that session's `corrected-2.wav` PCM exactly. Both are 48 kHz stereo, and left/right channels are identical in this sample and the replacements, so a stereo-image change is not the cause here. No user recordings or saved generated clips were overwritten.

| Measurement | Original | Previous edited file | Local reconstructed result |
|---|---:|---:|---:|
| Decoded duration | 24.149333 s | 23.774000 s | 24.354896 s |
| Main sentence-gap low energy interval | 10.097–10.459 s | 9.882–9.924 s | 10.040–10.454 s |
| Main gap length | 362 ms | 42 ms | 414 ms |

Gap detection uses pydub, -38 dBFS RMS, 15 ms minimum, 1 ms step. These are low-energy intervals, not semantic word/breath alignments. Coarser 70 ms/5–10 ms-step analysis gives about 370 ms and 425 ms for original/new. The 42 ms interval is so short that it disappears from the coarse silence report.

The original/edited samples were inspected as signals, not subjectively auditioned by the agent. Human listening is still required to judge seamlessness and distinguish soft breaths from noise/fricatives. No new ASR/TTS/voice setup requests were made.

## Recovering the actual two edits

PCM matching identifies the applied clips unambiguously:

- Correct Speech: `9c677b3a-b7ac-4947-9e48-87b41a69d61f.wav`, 1.950458 s. Its interior occurs at 8.028 s in corrected-1 and corrected-2. Reconstructing the old splice recovers approximately 8.078–10.188 s selection in Original.
- Change Delivery: `045302cf-9370-4264-ad4e-1e887044801a.wav`, 2.229104 s. Its interior occurs at 9.852 s in corrected-2. The old selection is approximately 9.902–12.146 s in corrected-1, or 10.162–12.406 s on the original unchanged suffix mapping.
- Matching `*-provider.wav` files exist for both clips. Local reconstructions reuse these bytes and rerun only local preprocessing, never speech generation.

Rebuilding both old splices with these recovered boundaries reproduces corrected-1 and corrected-2 byte-for-byte. The old second selection overlaps the first preview's end by about 76 ms; its 50 ms left crossfade reaches 126 ms back into that preview. At 9.852 s, corrected-1 measures about -25 dBFS in the preceding 10 ms: this is audible material, not a safe quiet join. Around the second selection start it is approximately -28/-31 dBFS. This can attenuate a word release or breath. Energy alone does not identify the precise phoneme.

## Confirmed processing causes and limits

1. The former `before.append(clip, crossfade=50).append(after, crossfade=50)` removes 100 ms per internal edit. Two edits remove 200 ms even before accounting for generated speech duration. The observed 375 ms shortening also includes the different replacement durations. The overlap modifies OUTSIDE the explicit selected interval and can eat sentence spacing or an earlier edit's tail.
2. No trimming was applied by the old preprocessing code. Provider padding remained as generated. The second saved preview has roughly 70 ms near-silent leading padding and 245 ms near-silent trailing padding at -50 dBFS. Raw and approved preview are available for direct comparison.
3. Whole-segment RMS was matched exactly: first source selection/preview -17.57 dBFS; second -21.96 dBFS. Speech-active median differs only about +0.65 dB and -0.20 dB respectively. Gross loudness is therefore not the principal cause in this example. Whole-RMS matching can nevertheless bias gain when pauses differ.
4. Conversion does proper resampling. No time-stretching or pitch shift is present. Original channel format is already preserved by the preceding update. Dry/reverberant or breath texture differences may remain; this analysis does not establish a room impulse response, and no blind EQ/reverb/noise synthesis was added.

## Minimal implementation

- Apply inserts the APPROVED preview at the exact requested timestamps, with no context-consuming overlap. Samples before/after the selected interval are retained exactly, including sub-ms final frames. Uploaded, preview and resulting durations use actual frame durations rather than rounded millisecond counts. It never regenerates or reprocesses the preview.
- Preview preprocessing matches median active 20 ms energy rather than pause-dependent whole-clip RMS. Existing +/-12 dB gain bounds and -1 dBFS peak protection remain.
- Low-energy edge material from INSIDE the selection is copied into the preview when at least 40 ms of contiguous padding is available, capped at 500 ms per side. It can retain room tone and low-level breaths; it is not a breath classifier. Entirely low-energy selections do not donate overlapping padding.
- Only corresponding provider near-silence below -50 dBFS is replaced, retaining a 20 ms guard before/after generated vocal material. No interior pause or word is trimmed. If no safe original padding exists, generated padding stays intact.
- Gentle 5 ms frame-based ramps occur at generated core edges, inside the preview, without changing frame count. Original edge ambience is copied verbatim. No long crossfade, automatic boundary movement, or time stretching is used.
- Preview shows nonblocking boundary warnings when local 20 ms energy exceeds -35 dBFS, plus duration-change guidance from 100 ms. Users retain explicit control of selection and Apply. Mode/version/session preview validation, ASR caching, both modes, export and Undo/Redo are unchanged.

## Local reconstruction and reproducibility

`test-results/continuity/rebuild_local.py` performs local-only reconstruction and assertions. It uses the recovered first selection. The second selection is mapped to the CURRENT timeline using the actual first duration change. It produces:

- `tweeq-same-selection.wav` / `.mp3`: reuse the recovered second region, mapped onto the refreshed timeline.
- `tweeq-pause-aligned.wav` / `.mp3`: additionally place the second start 100 ms later in an existing low-energy gap (10.237 s in the rebuilt Current). This is an explicit offline alignment experiment, NOT an automatic product boundary shift. Both variants measure the same final duration and main gap in this case because edge padding preserves the original spacing.
- `transition-pause-aligned.wav`: short 7.5–13.7 s excerpt for listening.
- `measurements.json`: measured times and levels.

The first rebuilt preview lasts 2.085458 s. Current after the first edit lasts 24.124792 s, a -24.542 ms shift. Second aligned selection uses 10.237–12.381 s of that CURRENT recording. Final is 24.354896 s, about 206 ms longer than Original. Generated cadence still differs; matching total length was intentionally not forced. Assertions verify all source PCM outside the second selection, the exact inserted preview, and final tail preservation. FFmpeg MP3 exports were created locally for both variants.

## Validation and rollout

62 backend tests passed in the final complete suite, including all existing workflow tests plus new source-context/frame preservation, exact between-sentence pause preservation across two edits, edge ambience, active-speech loudness, and warning tests. 33 frontend tests and production build pass. Provider tests use mocks/local fixtures. No model, voice-reference setting, generation request or API spending changed.

Backend code needs a restart. The active server/session was left intact so current edits, Undo/Redo and cached voice setup are not discarded. Export or finish the active session first. Existing saved previews do not acquire the new preprocessing automatically; the provided offline reconstruction uses their saved provider audio without spending credits.

Changed files: backend/app/audio.py; backend/app/main.py; backend/tests/test_continuity.py; backend/tests/test_multi_edit.py; backend/tests/test_workflow.py; frontend/src/EditorWorkspace.jsx; frontend/src/App.ui.test.jsx; README.md; IMPLEMENTATION.md; CONTINUITY_DIAGNOSIS.md. Audio artifacts and reproduction script are under ignored test-results/continuity.
