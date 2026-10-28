# Fish Audio authentication check — 25 October 2026

- `backend/.env` exists and contains a non-placeholder key. The file remains Git-ignored and was not changed.
- Fresh application startup loads the exact value from that file. No inherited environment key overrides it in the inspected launch environment; no surrounding whitespace, line breaks or duplicate Bearer prefix were detected. No key, fragment or fingerprint was displayed.
- The adapter uses `Authorization: Bearer <key>` and `POST https://api.fish.audio/v1/tts`, matching the official TTS contract. Inline reference bytes continue to use the supported MessagePack request type.
- A single authenticated, read-only `GET https://api.fish.audio/wallet/self/api-credit` returned **HTTP 200** using the current file's key. Only the HTTP status was reported; the account response body was not displayed. No speech generation or paid API request was made.
- The old backend process started at 02:38 IST; `.env` was updated at 02:48 IST. Startup-only environment loading meant the server had not reloaded that change. The server was restarted; the application now loads the current file and health reports `fish_configured=true`.

No authentication header or endpoint implementation change was necessary. No evidence currently requires replacing or regenerating this key: Fish Audio accepted it for authenticated account access. This does not establish permission for every TTS model or successful speech generation; those remain subject to a separately approved test. If a fresh TTS request still returns 401, investigate endpoint-specific authorization with Fish Audio rather than assuming a loading failure.

Mocked regression checks cover the actual adapter's Authorization header, model header, serialized reference request, credential error handling and secret suppression. No production key is used by those tests.

Restart the backend after changing `backend/.env`. Existing in-memory sessions expire on restart, so upload the recording again. Do not paste an API key into chat, frontend files or logs.

Sources: https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech and https://api.fish.audio/openapi.json.
