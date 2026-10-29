# Mounted LibreChat SSO runtime candidate

Targets API image/source commit `8d3da9bbb220a0a96be9330a2e1cbd385fb786d5` only. This directory
is a runnable mount layer, not an upstream build or a production operation. It uses the API
image's original backend dependencies and its existing `GenerationJobManager` singleton.
The session release builds the native frontend with `patches/native-session.patch` from that
same pin, then mounts a verified immutable client tree read-only. No secret value is included or printed.

## Mount before process startup

`compose.sso.yaml` includes nine read-only runtime mounts: this whole folder at
`/app/api/server/sso-runtime`, patched `index.js`, the three middleware wrappers, and the two
strict OpenID strategies, the logout-result wrapper and the patched native `AuthController`.
Keep the whole folder mount: wrappers load differently named native
copies from it, not their own overwritten module paths. The small index change runs
`await chatSsoRuntime.initialize(); app.use(chatSsoRuntime.ingress);` immediately after
`capabilityContextMiddleware`, before `/oauth` and **all** `/api` routes. This must be in place
before the first request; middleware exports are loaded/destructured at process startup.

`scripts/prepare-librechat-runtime.mjs` recreates pinned public middleware/index copies and
copies the reviewed core/adapters into this folder. It does not rewrite the strategy copies,
whose strict-subject and loopback-test discovery changes are documented in `strategies/SOURCE.md`.
`SOURCE.json` records generated-file hashes. The native controller retains the upstream
license in `UPSTREAM-LICENSE.txt`. Use the `session` mode of the chat deployment workflow for
the current server/client release; the legacy preparation script above is not a session release.

## Required runtime settings (values supplied by the owner)

- `SSO_REQUIRED=true`, `OPENID_REUSE_TOKENS=true`, `ALLOW_SOCIAL_LOGIN=true`.
- `OPENID_ISSUER`, `OPENID_CLIENT_ID=parallellines-chat`, `OPENID_SCOPE`, accurate external
  `OPENID_CALLBACK_URL` plus `DOMAIN_SERVER`/`DOMAIN_CLIENT`; native OIDC session/client
  settings and `OPENID_SESSION_SECRET` remain required.
- `OPENID_USE_PKCE=true`, `OPENID_GENERATE_NONCE=true` for the reviewed OIDC contract.
  SSO mode explicitly supplies `ClientSecretBasic` to native discovery; metadata alone is
  insufficient with openid-client 6.5.0. Keep `OPENID_USE_END_SESSION_ENDPOINT=false` so
  an ID token is not placed into an external logout URL.
- `CHAT_SSO_SESSION_STATE_URL`: production **HTTPS** endpoint
  `https://pingxingxian.space/api/v1/auth/chat-sso/session-state`; never an implicit private
  `http://api` exception. The CI-only host-network gateway uses loopback URLs.
- `CHAT_SSO_BRIDGE_SECRET`: backend-only runtime secret for
  `Authorization: Bearer ...`; never put it in the browser or a generated YAML artifact.
- Existing `JWT_REFRESH_SECRET` is used only to verify the native signed refresh-cookie marker.
- `CHAT_SSO_ID_TOKEN_ALG` defaults to `RS256`; explicitly choose `ES256` or `EdDSA` only if
  the approved provider uses it. JWKS comes from native issuer discovery and is checked by
  the API image's `jose` import with the fixed issuer/audience/algorithm. No arbitrary JWKS
  endpoint override is accepted.
- `LOCAL_SSO_TEST=true` is the only way the copied native discovery permits HTTP, and then
  only for exactly `127.0.0.1`, `localhost` or `[::1]`. Production has no insecure discovery.
- Single LibreChat replica / non-tenant instance only. Incoming `X-Tenant-Id` cannot select
  an account; account lookup requires the exact provider, signed issuer and subject with no
  tenant. No email/oid linking, new ADMIN mapping or role changes are made here.
- Keep GPT disabled/empty by the separately reviewed disabled provider overlay; this mount
  layer does not set or enable a model Key or grant a model catalog.

## Request boundaries

All `/api` requests first enter the global gate. The only anonymous API bootstrap is GET/HEAD
`/api/config` without Authorization. If a token is sent, even config must pass real ID-token
verification, exact native-user lookup and online binding state. `req.ssoVerifiedUser` is a
nonwritable server property set from that result; it is never read from client headers.

Native required-JWT copies use that server proof to select `openidJwt` even when a legitimate
Bearer has no cookies. That path has **no** local-JWT fallback. The outer wrapper retains the
native `requireRumProxyAuth` and `requireTermsAcceptance` exports; the native RUM drop
behavior is retained when that handler is reached, while ingress can reject earlier.
Native route auth, role, ban, tenant and ownership/ACL checks still run.

Direct images keep the existing canonical path parser, owner/ACL and `/chat` prefix-stripping
fix, then add the live cookie-session guard. It parses the raw cookie header, requires the
signed marker bound to that exact refresh token, checks its native durable Session, and
requires matching Express `openidTokens` identity/refresh token/ID token. Missing Express
proof is rejected instead of substituting `user.federatedTokens` or a legacy cookie token.

Refresh is a narrow exception, not private data access: only OpenID signed-marker + durable
Session + exact Express token identity can enter it. Its stored ID token is cryptographically
verified for issuer/audience/subject/binding and the **current** main authority is checked;
the old ID-token expiration alone may be past for this refresh-only route. The main auth
expiry must still be in the future. The native OP refresh/recovery runs afterward and all
resulting API calls must again present a live real ID token. Local refresh is rejected.
Logout is limited to proven OpenID-session cleanup; native JWT identity must still match
the proven cookie user, but an already inactive main session may clear its chat cookies.
Before native cleanup, the logout wrapper verifies the cookie-bound signed ID token and
POSTs `{client_id,binding_id}` to the same trusted status URL with its final `/session-state`
segment replaced by `/revoke`. It uses the same backend bridge authentication, no redirects
and a 500ms deadline. Only an inactive acknowledgement is accepted. Failure returns 503
and keeps the native session/cookies for an idempotent retry; no logout success is reported.
After success it preserves the original refresh-chain/session/cookie cleanup and fixes
navigation to `https://pingxingxian.space/auth`. The consumed binding makes old ID-token
replay fail the normal online gate without revoking the main SID or putting JWTs in URLs.
Main logout/expiry/disable also closes all associated chat access.

Only `/oauth/openid` and its callback are permitted OAuth entrypoints. Email/password
login, registration, password recovery, passkeys, old API-key routes, machine `/v1` routes
and **all native `/api/admin` routes** are explicitly rejected. Admin SSO/exchange is **not
open**: the original exchange hands out LibreChat JWTs, which this gate intentionally does
not accept. Existing admin identities/roles have not been migrated. This does not stop the
ordinary `/chat` USER OIDC flow; admin enablement needs a separately named identity/scope.
Bare default-agent `/api/agents/chat` and agent `/chat/resume` starts are fail-closed in
this release; ordinary explicit `/api/agents/chat/openAI` starts are captured and guarded.

## Per-generation cancellation and limits

The runtime captures only native successful new-chat responses containing
`streamId + generationCreatedAt`. A process-local registry associates that exact owner,
tenant and epoch with the verified SSO binding. It creates an independent `guard.watch`
lease; HTTP POST completion does not stop it. Revocation re-reads the native job, verifies
the same owner/tenant/epoch and calls the original singleton's
`abortJob(id,{expectedCreatedAt,awaitProviderDrain:true})`. It never enumerates all users'
or all of one user's other-binding jobs.

The registry is not durable or multi-replica. Only jobs created through this guarded process
have proof; reconnect/stream access without the matching binding/epoch evidence must be
denied. A replacement job may not inherit an old binding proof. A clean process restart
ends its in-memory jobs; this is not a cross-replica resumption design.

Native `/chat/abort` has a larger `beforePublish` partial-message persistence path. The
minimal cancellation hook does not reproduce that entire path; provider abort/drain and
partial-history behavior require the real-container joint test. A guard detecting revocation
within its 900ms polling/timeout budget does **not** prove a provider drained within 1 second.
No claim about real provider cancellation or billing is made before that test.

## Verification status

The guard/core/adapter tests and focused strict-subject/loopback tests are separate local
evidence. New runtime ingress and generation tracker tests use synthetic dependencies.
Full pinned API-image + real OP + main/session-state + proxy tests are owned by the root
task and are not claimed by these source files. No production service was started here.
