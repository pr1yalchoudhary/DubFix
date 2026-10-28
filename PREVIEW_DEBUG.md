# Preview → Apply investigation — 25 October 2026

## Confirmed failure

The running backend's access log recorded repeated `POST /api/preview` responses with **HTTP 502**, followed by playback of revision 0. The affected session's folder contained only `uploaded.mp3`, `original.wav` and `reference.wav`, with no generated preview clip. No successful preview/apply sequence appeared in those recorded requests.

This explains the reported state: the click reached the backend, but no successful preview ID/audio response was stored. Apply correctly remained disabled and Current stayed identical to Original. Previously the request error appeared only in the global page-top alert, while the preview area reverted to its initial “Generate a preview” text, making the failure look like a lost React state update.

The historical log contained only the application HTTP status. It did **not** record the underlying provider status or whether the failure was connectivity, a timeout, malformed audio or a provider rejection. Claiming a particular Fish Audio credential, credit, model or network problem from that evidence would be speculation. No paid request was made to reproduce it.

## Targeted changes

- Preview failures now persist beside the preview controls, including the application HTTP status, safe error detail and diagnostic code. Dismissing the page-top alert does not hide that local failure.
- Loading, failed and successful-preview states have distinct messages. A valid response still stores its preview ID and URL, displays the audio player and enables Apply. No validation is bypassed.
- A preview player load failure now invalidates the unusable preview and shows an explicit error. Missing/null clip responses are rejected clearly.
- Backend errors retain safe diagnostic categories (`fish_http_401`, `fish_http_402`, `fish_http_403`, etc.; connection, timeout, interrupted stream or invalid audio). The existing error JSON keeps `detail` and adds `error_code` and `upstream_status`. Logs record only those controlled fields, never API keys, request text/audio or raw provider error bodies.
- Apply still calls `/api/replace` with the saved preview and selection; no synthesis occurs. Current waveform/comparison sources reload using the updated revision; Original stays unchanged; export uses the edited recording.
- No layout redesign, provider/model fallback, runtime mock mode or unrelated feature was added.

## Verification without paid requests

Frontend regression tests explicitly enter **Friday**, simulate an HTTP 502, assert the local diagnostic and disabled Apply, retry with a successful mocked response, and assert the generated player and enabled Apply. Another test fires waveform time, pause, resize and unchanged-region events after success; the preview survives and Apply sends only the existing preview ID, without another generation call.

A backend integration test exercises the actual Fish adapter using an HTTP test transport returning locally generated WAV bytes. It verifies `replacement_text=Friday` in the serialized provider payload, HTTP 200 with a preview ID/URL, playable WAV response bytes, unchanged Current before Apply, changed Current after Apply, unchanged Original, valid export response and exactly one synthesis request. The broader audio suite validates the exported MP3 codec and 192 kbps bitrate.

Validation totals: **27 frontend tests**, **45 backend tests**, and production build passed. No paid Fish Audio requests were made. The real API key is not used by the regression tests.

The backend was restarted to load the new diagnostics; in-memory sessions expire on restart, so refresh and upload again. Real Fish Audio generation remains unresolved/unverified until an explicitly approved live request or other safe evidence identifies the provider-side failure. Browser visual/listening verification remains incomplete under the previously declined browser permission.
