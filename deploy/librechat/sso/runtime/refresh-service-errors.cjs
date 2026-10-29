'use strict';
// Packaged beside the shared server candidate errors.cjs; no error text is sent.
const transient = require('./errors.cjs');
const { ResponseBodyError } = require('openid-client');
function isRefreshServiceUnavailable(error) {
  if (error?.code === 'OPENID_REFRESH_OWNERSHIP_LOST' || error?.error === 'invalid_grant' ||
      error instanceof Error && error.message === 'failed to load session') return false;
  if (transient.isUnavailable(error) || transient.verifierUnavailable(error)) return true;
  // These are actual trusted SDK response boundaries, not guessed body/error text.
  if (error instanceof ResponseBodyError) return error.status === 429 || error.status >= 500 && error.status <= 599;
  const response = error?.cause;
  return typeof Response !== 'undefined' && response instanceof Response &&
    (response.status === 429 || response.status >= 500 && response.status <= 599);
}
function sendRefreshUnavailable(res) { return transient.sendFailure(res, transient.unavailable()); }
module.exports = { isRefreshServiceUnavailable, sendRefreshUnavailable };
