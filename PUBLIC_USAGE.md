# Public AI allowance rollout

Implemented locally only. No deployment, Redis provisioning, credentials, counter
initialization or paid Fish Audio requests were performed. The default remains
`AI_ACCESS_MODE=demo`, preserving the existing demo guard until explicit rollout.
Public mode ignores demo bearer codes; there is no owner-token bypass of its budget.

## What is counted

The limits are **2 provider-operation reservations per anonymous visitor** and
**10 across the entire public launch**, with no daily/monthly reset. Each provider
HTTP attempt reserves one slot immediately before dispatch. This includes:

- Correct Speech/Edit Text, Change Delivery, previews, and regenerations (TTS).
- Private voice/model setup, which may itself be billable.
- Speech detection/ASR, including explicit retry after a failure.
- Every automatic TTS transport retry. A retry cannot use a previous reservation.
- Voice-status polling, conservatively counted even if the provider does not bill it.

Consequently two uses do **not** guarantee two finished previews: the first preview
usually needs voice setup + TTS (two uses). Change Delivery may additionally require
ASR; users can manually enter words as before. Pending voice setup or retries can
exhaust the allowance before a playable clip exists. These strict semantics protect
the requested maximum of ten billable operations. A different product allowance
would require explicitly changing the budget, not relabelling these counters.

Cached transcripts, uploads, local quality/cleanup processing, applying a saved
preview, multiple edits, Undo/Redo, playback and exports do not consume Fish calls.
The editing workflow and model parameters are unchanged. Provider requests have
no automatic quota/storage retries. Reservations are never refunded on failed or
ambiguous provider responses, timeouts, client disconnects or backend crashes.
An uncertain Redis response can burn a slot without dispatching a provider request.

## Datastore and setup

Use a dedicated Upstash Redis database independent of Render's filesystem. The
production adapter uses the existing `httpx` dependency with the HTTPS REST API.
The same Lua script checks enabled state, schema, visitor, IP and global quotas,
then increments counters atomically. All keys use the same Redis hash tag.

Create a database in the Upstash console, enable durable storage, and **disable
eviction**. Do not use an expiring/test datastore. Confirm the chosen plan's
retention, backup and inactivity policies before launch. Copy its REST URL and
standard read/write REST token (not the read-only token) into Render's backend
environment. Do not put them in Vercel or commit them.

Configure these backend variables:

| Variable | Value |
|---|---|
| `AI_ACCESS_MODE` | Keep `demo` during setup; use `public` only at final rollout |
| `PUBLIC_GENERATIONS_ENABLED` | Keep `false` during setup; `true` to permit public reservations |
| `UPSTASH_REDIS_REST_URL` | The database's HTTPS REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | Its standard read/write REST token |
| `PUBLIC_IP_HASH_SECRET` | Independent random secret, at least 32 characters; preserve across deploys |
| `PUBLIC_IP_SOURCE` | `render` on Render; `peer` on localhost |
| `PUBLIC_RENDER_IP_VERIFIED` | `true` only after the ingress verification below |
| `DEMO_ACCESS_TOKEN` | Retain for rollback to demo mode |
| `FISH_AUDIO_API_KEY`, `FISH_AUDIO_MODEL` | Existing backend-only configuration |

Generate the IP secret locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Do not rotate this secret routinely: changing it changes IP bucket identities.
Do not change the fixed `tweeq:{public-v1}:` key prefix or initialize a new database
on redeploy. Visitor, IP and global quota records have **no expiry**. Only the
short-window abuse keys expire. Loss/deletion/rollback of the database can undermine
the historical budget; missing global state disables public use rather than
silently recreating it. Never restore an old counter snapshot while generations
are enabled. Disable first and reconcile reservations conservatively.

## IP trust boundary

Run Uvicorn with `--no-proxy-headers` so arbitrary forwarding headers cannot rewrite
`request.client` implicitly. Local `peer` mode ignores forwarding headers. On Render,
`peer` mode is deliberately refused; `render` mode requires `RENDER=true` (provided
by Render), `PUBLIC_RENDER_IP_VERIFIED=true`, and a valid single `True-Client-IP`
header. It does not fall back to client-provided X-Forwarded-For values.

Before setting the verification flag, confirm on your actual Render ingress that
`True-Client-IP` is supplied/overwritten by its trusted edge and cannot be forged by
sending your own `True-Client-IP`, `CF-Connecting-IP` or `X-Forwarded-For` headers.
Use a temporary private/logging check or Render support while AI remains disabled;
do not publish a debug endpoint or log visitor credentials. Confirm distinct clients
produce distinct IP buckets. If this header is absent or not protected on your
service, **leave public mode disabled** and configure a verified trusted ingress
before adapting the resolver. No live ingress assertion was made during local tests.
All traffic must traverse that ingress, including direct calls to onrender.com.

IPs are stored as HMAC digests rather than raw addresses. IPv4-mapped IPv6 is
normalized; ordinary IPv6 addresses are grouped by /64. Each network receives a
lifetime ceiling of two reservations, plus a two-per-minute operation limit and
ten anonymous-session issuances per hour. The network ceiling prevents a browser
reload/new anonymous token from granting new uses on the same network. NAT/shared
Wi-Fi can cause unrelated people to share this allowance. VPNs/network changes can
obtain different buckets; the independent global ten-operation cap still applies.

## Operator commands and emergency stop

The CLI is private tooling, never a public admin route. Configure its environment
locally (or use ignored `backend/.env`) with the **same** Upstash credentials as Render.
From the repository root:

```powershell
.\.venv\Scripts\python.exe backend/manage_public_usage.py initialize
.\.venv\Scripts\python.exe backend/manage_public_usage.py inspect
```

Initialization creates only the global schema/zero counter **disabled**, and refuses
to overwrite an existing budget. Do it once for a genuinely new public launch,
never as a startup/build step. After configuration and ingress verification:

```powershell
.\.venv\Scripts\python.exe backend/manage_public_usage.py enable
```

Then set `AI_ACCESS_MODE=public` and `PUBLIC_GENERATIONS_ENABLED=true` on Render
and restart/redeploy the backend when you authorize deployment. The public frontend
needs only `VITE_API_BASE_URL=https://tweeq-backend.onrender.com`; rebuild Vercel.
No quota secrets belong in `VITE_` variables.

For an immediate emergency stop, without waiting for a Render restart:

```powershell
.\.venv\Scripts\python.exe backend/manage_public_usage.py disable
```

Or, in the Upstash console: `HSET tweeq:{public-v1}:budget enabled 0`.
This is checked inside **every** reservation, without a cache. It blocks future
reservations, including later steps/retries in an already-started preview. Calls
already reserved/dispatched cannot be recalled. Also set
`PUBLIC_GENERATIONS_ENABLED=false` on Render for an environment-level stop.
Neither switch resets usage. To roll back to demo access set `AI_ACCESS_MODE=demo`;
the previous password gate and UI remain available in that mode only.

## Anonymous sessions and frontend behavior

`POST /api/public/session` mints a cryptographically random opaque token, stores
its hash and IP binding in Redis, and returns the token over HTTPS. The frontend
keeps this credential in sessionStorage (memory fallback if unavailable), sends it
in `X-Visitor-Session`, and refreshes authoritative usage after every AI request,
including failures. Browser-stored counts are never trusted. This avoids relying
on third-party cookies between vercel.app and onrender.com. The token is a bearer
credential; it never appears in audio URLs. Sessions do not uniquely identify people.

`GET /api/public/usage` returns remaining visitor/global allowance and explanatory
text. Public mode displays this instead of the demo password. Storage or quota
errors display an availability/limit message; no client error automatically retries
a paid operation. CORS permits the new header only for the existing allowed origins.
Direct callers must pass the same server-session/IP/quota checks. CORS itself is
not authorization. Status reads do not reserve a provider operation.

## Verification and remaining limits

Tests execute the actual production Lua in fakeredis with Lua support; concurrent
requests, new datastore clients, both quota ceilings, issuance throttling, corrupted
or missing state, disabled switches, malformed REST responses, direct API bypass
attempts, retries and partial multi-call previews are covered. Provider HTTP calls
are mocked. Existing editing regression tests remain in place. No Upstash account
or real provider was accessed. An actual Upstash persistence/restart check and Render
IP-spoofing verification still require your external setup; keep the demo mode until
those pass. Test Upstash with a separate staging database to avoid altering the
production ten-use budget. Never test a live generation just to check configuration.

The cap bounds operation count, **not dollars or characters**. Normal existing text
and duration limits still apply. This does not add user accounts, per-recording
ownership, CAPTCHA, upload/storage DoS protection or durable audio sessions.
Recordings/sessions remain subject to Render's existing ephemeral storage/restart
behavior even though quotas persist externally. A bot can exhaust a public free
allowance; IP sessions reduce abuse rather than prove identity. Upstash availability,
quota limits and data integrity are prerequisites; outages fail closed.

References: [Upstash REST API](https://upstash.com/docs/redis/features/restapi),
[durability](https://upstash.com/docs/redis/features/durability),
[Redis Lua atomic execution](https://redis.io/docs/latest/interact/programmability/eval-intro/),
[Render ingress guidance](https://render.com/articles/how-render-handles-ddos-attacks),
[Cloudflare IP headers](https://developers.cloudflare.com/fundamentals/reference/http-headers/).
