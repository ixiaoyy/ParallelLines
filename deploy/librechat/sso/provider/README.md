# ParallelLines OIDC provider

Single-process `oidc-provider` 9.13.2 service for the existing Main login and the
official LibreChat OpenID client. It has no login form, user provisioning endpoint,
model gateway, provider API key, or fallback identity source.

## Runtime configuration

| Variable | Meaning |
| --- | --- |
| `PUBLIC_MAIN_ORIGIN` | `https://pingxingxian.space` in production |
| `PUBLIC_ISSUER` | `https://pingxingxian.space/auth/oidc` |
| `MAIN_BACKEND_URL` | Main **API root**, `https://pingxingxian.space/api/v1`; the service appends `/auth/chat-sso/exchange` or `/session-state` |
| `CHAT_OIDC_CLIENT_SECRET` | Confidential client secret, at least 32 characters |
| `CHAT_OIDC_COOKIE_KEYS` | JSON array of cookie-signing keys, each at least 32 characters; first signs, remaining keys verify during rotation |
| `CHAT_OIDC_SIGNING_JWKS_FILE` | Read-only private RSA/RS256 JWKS file, normally `/secrets/signing.jwks.json`; POSIX mode 0600 |
| `CHAT_SSO_BRIDGE_SECRET` | Main's server bridge bearer secret, at least 32 characters |
| `OIDC_DATABASE_PATH` | Dedicated persistent SQLite path, default `/data/oidc.sqlite` |
| `HOST`, `PORT` | Default `0.0.0.0`, `3002` |

The production origin, issuer path, and callback are checked, not accepted from a
browser request. The only callback is
`https://pingxingxian.space/chat/oauth/openid/callback`, and the only client ID is
`parallellines-chat`. Explicit loopback HTTP origins with the same paths are
accepted for isolated local protocol tests; other HTTP targets are rejected.

Mount `/data` as a dedicated writable directory owned by the container's `node`
user. It is chmod 0700, and its database is chmod 0600. The service sets umask
0077 and uses SQLite DELETE journaling. Do not run replicas against this database.
Stop the service before making a consistent one-file backup. Treat backups as
credentials: they contain opaque tokens, OP sessions, and Main binding records.
`CHAT_OIDC_SIGNING_JWKS_FILE` must also be readable by this container UID; a 0600
file owned by a different UID is intentionally not made public by the service.

## HTTP routing and LibreChat

Forward `/auth/oidc/` to the service **preserving the whole request path**; the
Node handler strips the prefix before invoking the standard provider router.
For example, `proxy_pass http://chat-oidc:3002` has no trailing slash. Keep the
rest of `/auth` on Main. `/health` returns 200 and includes no configuration.

The discovery URL is
`https://pingxingxian.space/auth/oidc/.well-known/openid-configuration`. Use
authorization-code + PKCE S256, `client_secret_basic`, and scopes
`openid profile offline_access`. A refresh token is also issued for this one
confidential client when it asks for `openid profile`, for LibreChat's native
OpenID token reuse. Refresh tokens rotate and can never outlive their original
Main binding.

All OP cookies stay under `/auth` (the standard resume cookie can be narrower).
They are HttpOnly, SameSite=Lax and Secure in production. Neither a root-path
cookie nor Main's bearer JWT is required by the OP. The handler fixes forwarded
public host/protocol to its validated configuration instead of trusting client
forwarding headers. Do not expose the container port publicly.

## Main authority contract

Every new authorization, including one with an existing OP session, redirects
through Main's `/auth?redirect=/auth/chat?...`. Main authenticates the browser and
POSTs only `interaction_id` and a one-use `approval_code` to
`/auth/oidc/interaction/finish`. Origin, OP interaction cookie, client ID and the
fixed callback must agree before the OP calls Main's exchange endpoint.

Backend calls use `Authorization: Bearer <CHAT_SSO_BRIDGE_SECRET>`, require the
`{ "data": ... }` response envelope, reject redirects, enforce a 1-second timeout
and 16-KiB response ceiling, and fail closed. Exchange bodies include
`client_id`, `interaction_id`, `approval_code`; session-state bodies contain
`client_id`, `binding_id`.

The exchange identity supplies `active`, stable `sub`, `binding_id`, absolute
`auth_expires_at`, and display `name`. These are persisted with the grant. No
email matching, browser-supplied identity, privilege changes, or account linking
heuristic is used. Binding identity cannot be changed or its original expiry
extended. Every refresh and userinfo lookup rechecks Main's live session-state.
An inactive Main binding revokes its local grant; an unavailable Main rejects the
request without using cached positive authority.

ID tokens contain `pl_binding` and `pl_auth_exp` and last at most 300 seconds and
the remaining Main binding lifetime. Access tokens have the same ceiling.
The `profile` scope supplies `preferred_username` as the fixed `pl-` prefix plus
the trusted Main `sub`, and `name` from Main. Profile claims are included in ID
tokens as well as userinfo, for native LibreChat ID-token reuse. No email, role,
password, or primary Main JWT is supplied. These claims must not be used to take
over an existing LibreChat email account; issuer + subject is the identity key.
Authorization codes last at most 30 seconds. Refresh/Grant storage is capped by
the original Main expiry. This service does not itself terminate LibreChat's
already-open streams: retain the separate live-session guard in LibreChat.

When the user switches Main identity, the standard provider may emit its own
CSRF-protected automatic session-switch confirmation form before completing the
new authorization; this remains the upstream OIDC protocol flow.

## Commands and evidence

```sh
npm ci --ignore-scripts
npm test
npm start
```

The dependency lock is pinned from the already-installed successful local harness
lock (same exact dependency versions and integrity hashes); runtime installs omit
the test-only `openid-client` dependency. The Dockerfile installs from this lock,
runs as `node`, and uses Node's built-in `node:sqlite`.

Tests use synthetic loopback Main and RP fixtures only. They cover restart
recovery, concurrent consume, expiry, revocation tombstones, immutable binding,
real code+PKCE tokens, private claims, rotating refresh, Main outage/revocation,
and repeated Main confirmation despite an OP session. Windows cannot establish
POSIX permission behavior; that check is skipped there and must pass on Linux.

No production account, existing secret, Main permissions, or model API is touched
by these tests. Production deployment and real-user acceptance remain separate.
