'use strict';
const native = require('../sso-runtime/native/requireJwtAuth.native.cjs');
const runtime = require('../sso-runtime/runtime.cjs');
const wrapped = runtime.wrapRequired(native);
Object.assign(wrapped, native);
wrapped.requireRumProxyAuth = runtime.wrapRequired(native.requireRumProxyAuth, { telemetry: true });
// requireTermsAcceptance is a policy gate, not a second authentication strategy.
module.exports = wrapped;
