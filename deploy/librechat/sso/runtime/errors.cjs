'use strict';

const networkCodes = new Set(['ERR_JWKS_TIMEOUT', 'ERR_JWKS_INVALID', 'ECONNRESET',
  'ECONNREFUSED', 'ETIMEDOUT', 'ENOTFOUND', 'EAI_AGAIN', 'UND_ERR_CONNECT_TIMEOUT',
  'UND_ERR_HEADERS_TIMEOUT', 'UND_ERR_SOCKET']);
const databaseTransportNames = new Set(['MongoNetworkError', 'MongoNetworkTimeoutError',
  'MongoServerSelectionError', 'MongooseServerSelectionError', 'MongoNotConnectedError']);

function isUnavailable(error) {
  return error?.status === 503 || error?.statusCode === 503 || databaseTransportNames.has(error?.name);
}

function unavailable() {
  const error = new Error('SSO dependency temporarily unavailable');
  error.code = 'SSO_TEMPORARILY_UNAVAILABLE';
  error.status = error.statusCode = 503;
  return error;
}

// Only verification transport/key-source failures are retryable. Invalid JWT,
// signature, audience, issuer, time and unknown-kid errors are never promoted.
function verifierUnavailable(error) {
  return isUnavailable(error) || networkCodes.has(error?.code) ||
    networkCodes.has(error?.cause?.code) ||
    (error instanceof TypeError && error.message === 'fetch failed');
}

async function database(operation) {
  try { return await operation(); }
  catch { throw unavailable(); }
}

// This timeout belongs to the server dependency request, not caller cancellation.
// Even dependencies that ignore AbortSignal are bounded. Never return stale state.
async function authority(operation, timeoutMs = 500) {
  const controller = new AbortController();
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(() => operation(controller.signal)),
      new Promise((_, reject) => { timer = setTimeout(() => {
        controller.abort(); reject(unavailable());
      }, timeoutMs); }),
    ]);
  } catch { throw unavailable(); }
  finally { clearTimeout(timer); }
}

function sendFailure(res, error, { telemetry = false, unauthorized = 'sso_session_required' } = {}) {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) return res.destroy?.();
  if (telemetry) return res.status(204).end();
  if (isUnavailable(error)) {
    if (typeof res.set === 'function') res.set('Retry-After', '1');
    else res.setHeader?.('Retry-After', '1');
    return res.status(503).json({ error: 'sso_temporarily_unavailable' });
  }
  return res.status(401).json({ error: unauthorized });
}

module.exports = { isUnavailable, unavailable, verifierUnavailable, database, authority, sendFailure };
