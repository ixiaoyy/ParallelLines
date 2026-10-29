'use strict';
let pending;
function initialize() {
  if (!pending) pending = import('./init.mjs').then(module => module.createRuntime());
  return pending;
}
function deny(res, telemetry = false) {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) return res.destroy();
  if (telemetry) return res.status(204).end();
  return res.status(401).json({ error: 'sso_session_required' });
}
async function ingress(req, res, next) {
  try { return (await initialize()).ingress(req, res, next); }
  catch { return deny(res); }
}
function wrapRequired(native, { telemetry = false } = {}) {
  return function ssoRequiredNative(req, res, next) {
    initialize().then(async runtime => {
      if (!req.ssoCleanupOnly) await runtime.preverify(req);
      native(req, res, error => {
        if (error) return next(error);
        if (req.ssoCleanupOnly) {
          if (!runtime.allowCleanup(req)) return deny(res, telemetry);
          return next();
        }
        Promise.resolve(runtime.bearer(req, res, next)).catch(() => deny(res, telemetry));
      });
    }).catch(() => deny(res, telemetry));
  };
}
function wrapOptional(native) {
  return function ssoOptionalNative(req, res, next) {
    if (req.headers?.authorization === undefined) return native(req, res, next);
    initialize().then(async runtime => {
      await runtime.preverify(req);
      native(req, res, error => {
        if (error) return next(error);
        Promise.resolve(runtime.bearer(req, res, next)).catch(() => deny(res));
      });
    }).catch(() => deny(res));
  };
}
function image(nativeOwnerAcl) {
  return function nativeImageThenLiveSession(req, res, next) {
    nativeOwnerAcl(req, res, error => {
      if (error) return next(error);
      initialize().then(runtime => runtime.image(req, res, next)).catch(() => deny(res));
    });
  };
}
function document(sendIndexHtml) {
  return function ssoDocument(req, res) {
    initialize().then(runtime => runtime.document(req, res, sendIndexHtml)).catch(() => deny(res));
  };
}
module.exports = { initialize, ingress, wrapRequired, wrapOptional, image, document };
