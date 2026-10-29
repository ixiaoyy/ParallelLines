'use strict';
const errorPolicy = require('./errors.cjs');
const documentEntry = require('./document-entry.cjs');
let pending;
function initialize() {
  if (!pending) pending = import('./init.mjs').then(module => module.createRuntime());
  return pending;
}
function deny(res, telemetry = false, error) { return errorPolicy.sendFailure(res, error, { telemetry }); }
async function ingress(req, res, next) {
  try { return await (await initialize()).ingress(req, res, next); }
  catch (error) { return deny(res, false, error); }
}
function wrapRequired(native, { telemetry = false } = {}) {
  return function ssoRequiredNative(req, res, next) {
    initialize().then(async runtime => {
      if (!req.ssoCleanupOnly) await runtime.preverify(req);
      native(req, res, error => {
        if (error) return errorPolicy.isUnavailable(error) ? deny(res, telemetry, error) : next(error);
        if (req.ssoCleanupOnly) {
          if (!runtime.allowCleanup(req)) return deny(res, telemetry);
          return next();
        }
        Promise.resolve(runtime.bearer(req, res, next)).catch(error => deny(res, telemetry, error));
      });
    }).catch(error => deny(res, telemetry, error));
  };
}
function wrapOptional(native) {
  return function ssoOptionalNative(req, res, next) {
    if (req.headers?.authorization === undefined) return native(req, res, next);
    initialize().then(async runtime => {
      await runtime.preverify(req);
      native(req, res, error => {
        if (error) return errorPolicy.isUnavailable(error) ? deny(res, false, error) : next(error);
        Promise.resolve(runtime.bearer(req, res, next)).catch(error => deny(res, false, error));
      });
    }).catch(error => deny(res, false, error));
  };
}
function image(nativeOwnerAcl) {
  return function nativeImageThenLiveSession(req, res, next) {
    nativeOwnerAcl(req, res, error => {
      if (error) return errorPolicy.isUnavailable(error) ? deny(res, false, error) : next(error);
      initialize().then(runtime => runtime.image(req, res, next)).catch(error => deny(res, false, error));
    });
  };
}
function document(sendIndexHtml) {
  return function ssoDocument(req, res) {
    initialize().then(runtime => runtime.document(req, res, sendIndexHtml)).catch(error =>
      errorPolicy.isUnavailable(error) ? documentEntry.unavailablePage(req, res) : deny(res, false, error));
  };
}
module.exports = { initialize, ingress, wrapRequired, wrapOptional, image, document };
