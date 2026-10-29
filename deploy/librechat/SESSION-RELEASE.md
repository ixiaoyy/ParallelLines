# Native session refresh release

Run the existing `Deploy family chat` workflow with `mode=session`. It builds the
original LibreChat client at commit `8d3da9bbb220a0a96be9330a2e1cbd385fb786d5`
with `patches/native-session.patch`, then transfers the complete verified client
artifact using the existing deployment connection. Build and deployment use separate jobs.

The server installs public assets in an immutable `.runtime/native-client/<commit>`
directory, checks every file against the source/patch manifest, and recreates only
LibreChat. Startup verifies the mounted assets again. The existing OIDC container,
`.env` files, application secrets, OpenAI Key, users, grants and balances remain in place.
Other chat maintenance modes load `.runtime/session-release.env` to retain this client.

Temporary authority/database failures remain unavailable responses, with bounded
client retries. They do not grant access or end an already verified UI session.
A successful same-user refresh preserves native draft/model state; failed business
requests after refresh retain their own errors. Invalid, disabled or mismatched
sessions still fail authentication. The normal composer hint is model-independent.

Validation before release included full native build/typechecks, real Axios error
paths, patched AuthController/Express/native Mongo refresh publication, independent
native browser checks across a real refresh window, and denial cases. The local
Mongo test binary was 8.2.6; production remains pinned to 8.0.20. No paid model
request or automatic account/model permission change is part of this release.
