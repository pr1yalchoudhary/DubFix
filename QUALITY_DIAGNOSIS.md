# Generated speech quality diagnosis

Inspected local session `2b9fd2da-5674-4a26-b1a0-5c591ef1c756`, matching the reported format/duration pattern. No provider requests were made. The audio has not been subjectively auditioned by the agent; pitch estimates supplied by the user were not independently reproduced.

## Confirmed measurements

| File | Decoded duration | Sample rate / channels | Leading / trailing quiet below -40 dBFS |
|---|---:|---|---|
| uploaded.mp3 | 13.568 s | 48 kHz stereo | 1150 / 170 ms |
| original.wav | 13.568 s | 44.1 kHz mono | 1150 / 170 ms |
| reference.wav | 10 s | 44.1 kHz mono | 1150 / 0 ms |
| corrected-1.wav | 13.761 s | 44.1 kHz mono | 1150 / 170 ms |
| corrected-2.wav | 14.205 s | 44.1 kHz mono | 1150 / 480 ms |
| export-2.mp3 | 14.205 s | 44.1 kHz mono | 1150 / 480 ms |

Container/player durations may include padding and differ from decoded durations. Threshold-based quiet detection is not speech recognition or a background-noise estimate.

First change begins at 10.145 s; second change begins at 11.511 s. Saved preview durations are 1.625 s and 2.694 s. Their interiors match exact PCM bytes in the corresponding corrected WAV, demonstrating no post-preview pitch shift. The placements overlap by about 0.259 s, including boundary mixing; the second edit can overwrite the first preview's tail. This is a selection issue to check while listening, not evidence of the sustained voice mismatch. Select complete phrases and inspect adjacent words in preview/current.

The final preview includes about 480 ms trailing quiet versus 170 ms at the original ending. Generated duration and pauses account for timing differences; splicing shortens via up-to-50-ms overlaps per edge, never time stretches.

## Voice routing and likely contributors

Both modes receive the same session-specific private voice model ID. Creation uploads that session's extracted authorized reference WAV with consent enforced, private visibility and fast mode. No stock voice fallback exists. Correct Speech retains its configured model; Change Delivery explicitly sends the `model: drama-3` header with `reference_id`. Tests verify both headers, same ID, and exact reference WAV bytes in model creation. Legacy clients explicitly supplying `reference_text` use the same session reference bytes inline instead.

Historical request/model metadata and raw provider audio were not persisted for these existing files, so actual historical provider-side routing and the exact stage before preview cannot be retrospectively proved. Current pipeline converts sample rate properly, changes gain only, and never pitch-shifts or time-stretches. Sustained voice/pitch mismatch is therefore present before Apply and is consistent with synthesis/reference/emotional-direction effects, rather than the splice. This does not establish subjective similarity from signal measurements alone.

Old Excited asked for high-energy delivery. Combined with custom dramatic instructions, this can encourage a larger vocal change; it is a plausible contributor, not experimentally established causation. The fixed reference used 1.15 seconds of its 10 seconds on leading quiet and did not assess background music/reverb/overlapping speakers. Short references limit fidelity; reference quality cannot be established from RMS alone.

## Focused changes

- Excited uses restrained conversational enthusiasm, requesting reference accent, vocal character and natural pacing without exaggerated pitch/shouting. Confident, Nervous and Sarcastic are also softened. Custom directions remain untouched. Natural remains empty.
- Reference extraction avoids leading quiet only when a complete 10-second window remains. Existing cached voices are not replaced; new uploads use the change. It remains mono 44.1 kHz for the same private cloning workflow.
- New recording WAVs preserve uploaded sample rate and channels. Provider output remains mono 44.1 kHz, latency normal, same models/settings; approved previews are properly resampled/upmixed to current recording format before gain matching. Original stereo outside edits is preserved; generated ambience is still mono duplicated across channels.
- Successful provider WAV bytes are retained as `<preview-id>-provider.wav` for direct local comparison with the processed preview and applied clip. Failed previews are cleaned up. Existing files are untouched.

No automatic pitch correction, pause trimming, denoising, model switch, additional API requests or regenerated takes were added. These could damage speech or consume credits without evidence. Voice similarity and improvements from softer prompts require human listening to separately approved generations; identity is not guaranteed by prompt wording.

## Verification and rollout

57 backend tests passed, including same-reference routing, stereo 48 kHz preservation through MP3, 235 Hz pitch/duration preservation across preview/resampling/splice, exact untouched PCM, leading-quiet selection, cumulative two edits, ASR, Undo/Redo and export. Frontend tests and production build passed. All provider tests used HTTP mocks/local fixture audio, not live Fish Audio. No paid calls; preferred $3 / maximum $4 testing budget untouched by this work.

Backend changes require a restart. The active backend was deliberately left running so the user's in-memory session is not discarded. Finish/export it before restarting; reupload to obtain the improved reference and preserved recording format. Existing edited files cannot recover discarded stereo information or acquire a new generated voice without regeneration.

Files: backend/app/audio.py; backend/app/main.py; backend/tests/test_audio_quality.py; backend/tests/test_voice_setup.py; frontend/src/deliveryText.js; frontend/src/DeliveryControls.jsx; frontend/src/EditorWorkspace.jsx; frontend/src/App.jsx (UTF-8 punctuation repair only); README.md; IMPLEMENTATION.md; QUALITY_DIAGNOSIS.md.

Official sources checked: https://docs.fish.audio/features/text-to-speech/drama-3 ; https://docs.fish.audio/features/voice-cloning ; https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech . Drama 3 uses the model HTTP header and plain bracketed directions. Voice cloning uses reference_id; clean mono single-speaker samples are recommended. Standard WAV output is 16-bit mono up to 44.1 kHz. No documented hard speaker-identity lock was introduced.
