# Native strategy candidate provenance

## OAuth entry compatibility correction

The SSO GET authorization entry now presents a query-free `currentUrl` only at the
exact `/chat/oauth/openid` start pathname. `openid-client` 6.5.0 otherwise treats
`returnTo` as an authorization response; callback queries, state/PKCE/nonce checks
and fixed callback configuration remain intact. The document entry consumes the
strict chat return path and captures Passport's actual `Location` header to bind
that path to the generated state before Express saves the session.

This correction passed real Passport/Express-session tests for new and existing
state, successful PKCE/nonce/signed-ID-token callback, and invalid state/session
denials. The corrected strategy SHA256 is
`68d71e16b2bd51206ec6110eec98a47057c84d0a922ce44a3c42b149b4cc2cf7`.
The following sections retain the earlier preparation history.

Local candidate files only; no upstream/main checkout changes and no production execution.

Base: LibreChat `v0.8.9-rc1`, commit `8d3da9bbb220a0a96be9330a2e1cbd385fb786d5`, API image index `sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5`.

Both source strategy files had no working-tree diff against that commit before copying. The existing `sso-integration/patches/strict-subject.patch` was applied to byte copies; its forward/reverse checks and both syntax checks passed at that stage. The callback candidate additionally has the narrow local HTTP discovery exception and explicit SSO client authentication below; the JWT candidate remains unchanged from that patch. Syntax checking does not prove dependency loading or runtime integration. These `.js` files are CommonJS when mounted under LibreChat's `/app/api`, and should not be imported directly as ESM from this standalone package.

| File | SHA-256 |
|---|---|
| Original `api/strategies/openidStrategy.js` | `71c9f03c4f4bb60a140657a76eb383c073d8645b7883498c60eaf418a1009812` |
| Original `api/strategies/openIdJwtStrategy.js` | `fd8e255fb1462b5a6ad1e55a48ac7e9dccc1474b40688c6748f6cf3533372e11` |
| `strict-subject.patch` | `cecc66256213455bedf6a31a3f50073cef066c1e300e60f3d0b5d9f48d24440c` |
| Candidate `openidStrategy.js` (including local discovery, SSO Basic auth and internal placeholder email) | `573cedb8cd11b212b3e03c6b7950821b11e7b7ed868a1a3834fdbbd73591744d` |
| Candidate `openIdJwtStrategy.js` | `99679ea310b1ebb9debc7be5bf808f0f8c9f5dad46eee32c86c3d20b33698027` |

Read-only mount targets, preserving the pinned runtime dependencies:

- `strategies/openidStrategy.js` -> `/app/api/strategies/openidStrategy.js:ro`
- `strategies/openIdJwtStrategy.js` -> `/app/api/strategies/openIdJwtStrategy.js:ro`

With `SSO_REQUIRED=true`, callback and JWT lookups require token `sub` and `iss`; only an exact subject plus issuer query may reach native `findUser`. Email fallback, `oid` fallback, and legacy issuer-less queries return no result. The callback keeps native first-login provisioning for an admitted new OpenID subject; same-email existing accounts cannot be silently linked. The JWT strategy disables its user-document cache in this mode. Profile subject comes from the verified token's claims, not a different userinfo subject. With the option disabled, native behavior is retained.

These copies do not remove the native global local-JWT fallback, enforce central live-session status, or alter role/JIT admission policy. The additional required middleware must reject non-OpenID authentication and perform the central guard check. Keep IdP invitation/application assignment and any required-role gate in effect; native `ALLOW_SOCIAL_REGISTRATION=false` alone does not disable OIDC first-login provisioning.

## Local HTTP discovery exception

The callback candidate passes discovery's fifth-argument `execute: [client.allowInsecureRequests]` only when `LOCAL_SSO_TEST` is exactly the string `true`, the parsed `OPENID_ISSUER` protocol is `http:`, and its hostname is exactly `127.0.0.1`, `localhost`, or `[::1]`. For example, the local test issuer can be `http://127.0.0.1:3190/auth/oidc`. Other hosts (including Docker aliases/gateways), HTTPS URLs, and absent/false/nonexact flags have no insecure execute extension. Production uses HTTPS and must not enable the local test flag.

The installed `openid-client` package was read locally and confirmed as 6.5.0. `build/index.js:242–255` accepts `discovery(server, clientId, metadata, clientAuthentication, options)` and executes these extensions on the Configuration; the discovery request also checks `options.execute.includes(allowInsecureRequests)` (`270`). The exported extension is declared in `build/index.d.ts:1326`, and the discovery signature in `858`. No discovery/network call was made for this verification.

The focused `test/librechat-local-discovery.test.mjs` ran alone: 4/4 passed. It evaluates the actual candidate helper against permitted loopbacks, absent/nonexact flags, HTTPS, Docker aliases, misleading suffixes/userinfo, and nonloopback IPs; it checks conditional wiring and the installed library signature. The callback candidate passed `node --check` after this change. These source checks do not replace the parent-controlled local-container discovery test.

## Explicit SSO client authentication

When `SSO_REQUIRED` is enabled and a client secret exists, the callback candidate sets metadata `token_endpoint_auth_method: 'client_secret_basic'` and passes `client.ClientSecretBasic(clientSecret)` as `client.discovery`'s fourth argument. `OPENID_GENERATE_NONCE` and `OPENID_USE_PKCE` remain independent and unchanged. Outside SSO mode, the previous nonce-enabled `client_secret_post` metadata behavior is preserved; the previous public-client PKCE `none` branch is also preserved.

Metadata alone is insufficient in this installed 6.5.0: `build/index.js:242–244` passes the fourth argument into Configuration, and the constructor (`478–488`) uses an explicit callback if present but otherwise defaults any nonempty client secret to `ClientSecretPost`, regardless of the metadata auth-method string. The exported Basic factory is at `41–54`. Therefore the candidate deliberately supplies both metadata and callback, rather than relying on discovery selection.

Only `test/librechat-client-auth.test.mjs` was run for this change: 5/5 passed. The checks evaluate the actual candidate metadata branch across SSO/nonce/PKCE combinations, verify explicit fourth-argument wiring and the installed default-selection implementation, and invoke the installed Basic authentication callback on synthetic URLSearchParams/Headers in memory. This makes no token/discovery/network request and uses no real credentials. The final callback candidate also passed `node --check`.

## Safe generation-cancellation API in this pin

Source references below are against the same pinned commit, not a claim of an executed cancellation test.

- `packages/api/src/stream/GenerationJobManager.ts:9881` exports the existing singleton `GenerationJobManager`; do not create a second independent manager.
- `getActiveJobIdsForUser(userId, tenantId)` at `9700–9701` delegates to the user/tenant scoped store index. It returns IDs, not an authorization guarantee. Use the authenticated native user ID and tenant, never user-supplied account selectors.
- `getJob(streamId)` at `3364–3383` returns the job facade; native abort route `api/server/routes/agents/index.js:698–706` rechecks `job.metadata.userId` and tenant. The source helper `hasTenantMismatch` is at `87–89`. Recheck these on every candidate, including IDs recovered from an index.
- `abortJob(streamId, { expectedCreatedAt, awaitProviderDrain, beforePublish, transformAbortContent })` is at `4673–4693`. It does **not** accept an actor or perform owner authorization itself. `expectedCreatedAt` is the observed generation epoch; missing it can cancel a replacement on the same conversation stream. Stale epoch is rejected at `4697–4715` and subsequent transitions are fenced at `4831–4835`.
- Native routing demonstrates `getActiveJobIdsForUser(userId, req.user.tenantId)` followed by running/requires-action, owner, tenant, and epoch checks (`routes/agents/index.js:662–675`), and `abortJob(..., { expectedCreatedAt: job.createdAt, ... })` (`762–764`). A concrete unknown request ID must not fall back to an arbitrary active job (`654–659`); native `new` placeholder handling rejects multiple candidates (`680–686`).
- The actual provider receives the job's abort-controller signal (`controllers/agents/request.js:2004–2011`). Native abort publishes an epoch-specific cross-replica abort and aborts the local controller (`GenerationJobManager.ts:4923–4936`). Set `awaitProviderDrain:true` when the caller needs acknowledgement of trailing provider work, then inspect the result. `isStopConfirmed(result)` (`stream/interfaces/IJobStore.ts:906–907`, exported by `stream/index.ts:41`) accepts success or `already_settled`. `job_not_found`, `generation_replaced`, and `job_still_active` are not stop confirmations. Preserve native partial-message persistence, usage settlement, paused-action cleanup and terminal publication; the native abort route supplies substantial host work through `beforePublish`, beyond merely closing a socket.

For a single request, the native controller sets `req._resumableStreamId` only after the job exists (`controllers/agents/request.js:1839`). Ordinary POST requests return `{ streamId, conversationId, generationCreatedAt }` immediately (`1861–1881`) while provider work continues. A watcher released at HTTP response completion therefore cannot protect that detached generation. Bind an independent lease to the authenticated `(userId, tenantId, streamId, createdAt, SSO bindingId)` after job creation, keep it until terminal/provider-drained state, and bridge revocation to the fenced owner-checked abort path. Subscription requests still need their own authorization.

The native user index includes all that user's sessions, and native jobs do not already carry an SSO binding ID. Revoking one login must cancel only jobs bound to that login; it must not indiscriminately cancel the user's other valid sessions. Store the binding on each admitted job or retain the exact job/lease association. User-wide enumeration is appropriate only for a confirmed account-wide disable or equivalent global policy transition. Never call global `destroy()` or iterate all manager jobs for a single-user/session revocation.

The mount/restart, real native strategy loading, central middleware wiring, detached-job lease and abort/settlement integration remain for the parent-controlled local container test. No API or provider request was made while preparing these files.


## Required internal email metadata

Strict SSO does not receive or authorize by a real email claim. To satisfy the pinned required native email schema, it stores lowercase SHA256 of exact normalized issuer, a NUL separator and the verified subject, followed by @chat.invalid. emailVerified is explicitly false. This internal placeholder is not a verified or deliverable address. Lookup email/oid remain undefined, username selection is unchanged, and duplicate native email conflicts fail closed rather than merge accounts. Only the focused placeholder source/synthetic-hash checks ran (2/2 passed) plus callback syntax check; no real account or production request was made.
