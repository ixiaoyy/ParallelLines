/** Local integration core. A verifier must perform real JOSE verification before returning claims.
 * No JWT decoding, credentials, user headers, positive-result cache, or permission writes live here.
 */
import errorPolicy from '../errors.cjs';

export class LiveSessionError extends Error {
  constructor(code, status = 401) {
    super(code);
    this.name = 'LiveSessionError';
    this.code = code;
    this.status = status;
    this.statusCode = status;
  }
}

const fail = (code, status) => new LiveSessionError(code, status);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const identifier = value => typeof value === 'string' && value.length > 0 && value.length <= 1024;
const numericDate = value => typeof value === 'number' && Number.isFinite(value) && value > 0;

function abortReason() { return fail('REQUEST_ABORTED', 499); }

/** Bound even a dependency that ignores AbortSignal; do not expose its error/token contents. */
async function bounded(operation, { signal, timeoutMs, failureCode }) {
  if (signal?.aborted) throw abortReason();
  const controller = new AbortController();
  let timer;
  let onAbort;
  const cancellation = new Promise((_, reject) => {
    onAbort = () => {
      controller.abort(abortReason());
      reject(abortReason());
    };
    signal?.addEventListener('abort', onAbort, { once: true });
    timer = setTimeout(() => {
      const error = fail(failureCode === 'TOKEN_VERIFICATION_FAILED' ? 'TOKEN_VERIFICATION_UNAVAILABLE' : failureCode, 503);
      controller.abort(error);
      reject(error);
    }, timeoutMs);
  });
  try {
    return await Promise.race([
      Promise.resolve().then(() => operation(controller.signal)),
      cancellation,
    ]);
  } catch (error) {
    if (signal?.aborted) throw abortReason();
    if (error instanceof LiveSessionError) throw error;
    if (errorPolicy.verifierUnavailable(error)) throw fail(failureCode, 503);
    throw fail(failureCode, failureCode === 'TOKEN_VERIFICATION_FAILED' ? 401 : 503);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

function validEndpoint(url) {
  let parsed;
  try { parsed = new URL(url); } catch { throw fail('CONFIGURATION_ERROR', 500); }
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  if (parsed.username || parsed.password || parsed.hash || parsed.search ||
      (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && loopback))) {
    throw fail('CONFIGURATION_ERROR', 500);
  }
  return parsed;
}

async function limitedJson(response, signal, limit = 16384) {
  const advertised = response.headers?.get('content-length');
  if (advertised !== null && advertised !== undefined &&
      (!/^\d+$/.test(advertised) || Number(advertised) > limit)) {
    response.body?.cancel().catch(() => {});
    throw fail('AUTHORITY_UNAVAILABLE', 503);
  }
  const reader = response.body?.getReader();
  if (!reader) throw fail('AUTHORITY_UNAVAILABLE', 503);
  const cancel = () => { reader.cancel().catch(() => {}); };
  signal?.addEventListener('abort', cancel, { once: true });
  const chunks = [];
  let size = 0;
  try {
    if (signal?.aborted) throw abortReason();
    while (true) {
      const { value, done } = await reader.read();
      if (signal?.aborted) throw abortReason();
      if (done) break;
      if (!(value instanceof Uint8Array) || value.byteLength > limit - size) {
        cancel();
        throw fail('AUTHORITY_UNAVAILABLE', 503);
      }
      chunks.push(value);
      size += value.byteLength;
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } finally {
    signal?.removeEventListener('abort', cancel);
    reader.releaseLock();
  }
}

/** Backend-only POST client; inject bridgeSecret at runtime, never from a browser or source file.
 * The caller/guard supplies timeout and cancellation. Redirects cannot forward the bridge secret.
 */
export function createSessionStateClient({ url, bridgeSecret, clientId = 'parallellines-chat', fetchImpl = globalThis.fetch }) {
  const endpoint = validEndpoint(url);
  if (!identifier(bridgeSecret) || /[\r\n]/.test(bridgeSecret) || !identifier(clientId) || typeof fetchImpl !== 'function') {
    throw fail('CONFIGURATION_ERROR', 500);
  }
  return async ({ binding_id, client_id }, { signal } = {}) => {
    if (!identifier(binding_id) || client_id !== clientId) throw fail('INVALID_BINDING');
    try {
      const response = await fetchImpl(endpoint, {
        method: 'POST', redirect: 'error', cache: 'no-store', signal,
        headers: { authorization: `Bearer ${bridgeSecret}`, 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify({ binding_id, client_id: clientId }),
      });
      if (!response.ok) {
        response.body?.cancel().catch(() => {});
        throw fail('AUTHORITY_UNAVAILABLE', 503);
      }
      const envelope = await limitedJson(response, signal);
      if (!object(envelope) || !Object.hasOwn(envelope, 'data') || !object(envelope.data)) {
        throw fail('AUTHORITY_UNAVAILABLE', 503);
      }
      return envelope.data;
    } catch {
      if (signal?.aborted) throw abortReason();
      throw fail('AUTHORITY_UNAVAILABLE', 503);
    }
  };
}

/** verifyIdToken(token,{issuer,audience,signal}) must return jose.jwtVerify's {payload} shape.
 * getSessionState({binding_id,client_id},{signal}) returns the main authority's session state.
 * expectedUser uses LibreChat's real {provider,openidId,openidIssuer} fields. Mock RP callers may
 * explicitly opt out only after they have bound the session themselves; real adapters may not.
 */
export function createLiveSessionGuard({
  verifyIdToken, getSessionState, issuer, audience, clientId = 'parallellines-chat',
  requireExpectedUser = true, clock = Date.now, pollIntervalMs = 200,
  authorityTimeoutMs = 500, verificationTimeoutMs = 500,
}) {
  validEndpoint(issuer);
  const audiences = typeof audience === 'string' ? [audience] : audience;
  if (typeof verifyIdToken !== 'function' || typeof getSessionState !== 'function' ||
      typeof clock !== 'function' || !identifier(clientId) || !Array.isArray(audiences) ||
      audiences.length === 0 || !audiences.every(identifier) ||
      !Number.isFinite(pollIntervalMs) || pollIntervalMs < 1 ||
      !Number.isFinite(authorityTimeoutMs) || authorityTimeoutMs < 1 ||
      pollIntervalMs + authorityTimeoutMs > 900 ||
      !Number.isFinite(verificationTimeoutMs) || verificationTimeoutMs < 1 ||
      typeof requireExpectedUser !== 'boolean') {
    throw fail('CONFIGURATION_ERROR', 500);
  }

  function validateClaims(payload, expectedUser) {
    if (!object(payload) || payload.iss !== issuer || !identifier(payload.sub) || !identifier(payload.pl_binding)) {
      throw fail('INVALID_TOKEN_BINDING');
    }
    const tokenAudiences = typeof payload.aud === 'string' ? [payload.aud] : payload.aud;
    if (!Array.isArray(tokenAudiences) || !tokenAudiences.every(identifier) ||
        !audiences.some(expected => tokenAudiences.includes(expected))) throw fail('INVALID_TOKEN_AUDIENCE');
    const now = clock() / 1000;
    if (!Number.isFinite(now) || !numericDate(payload.exp) || payload.exp <= now ||
        (payload.nbf !== undefined && (!numericDate(payload.nbf) || payload.nbf > now))) {
      throw fail('TOKEN_EXPIRED_OR_NOT_ACTIVE');
    }
    if (payload.pl_auth_exp !== undefined &&
        (!numericDate(payload.pl_auth_exp) || payload.pl_auth_exp <= now || payload.exp > payload.pl_auth_exp)) {
      throw fail('INVALID_SIGNED_AUTH_EXPIRY');
    }
    if (requireExpectedUser || expectedUser !== undefined) {
      if (!object(expectedUser) || expectedUser.provider !== 'openid' ||
          expectedUser.openidId !== payload.sub || expectedUser.openidIssuer !== issuer) {
        throw fail('LIBRECHAT_IDENTITY_MISMATCH');
      }
    }
    return Object.freeze({
      iss: payload.iss, sub: payload.sub,
      aud: Object.freeze([...tokenAudiences]), exp: payload.exp, pl_binding: payload.pl_binding,
      ...(payload.pl_auth_exp === undefined ? {} : { pl_auth_exp: payload.pl_auth_exp }),
    });
  }

  async function checkState(claims, signal) {
    if (signal?.aborted) throw abortReason();
    const state = await bounded(
      requestSignal => getSessionState({ binding_id: claims.pl_binding, client_id: clientId }, { signal: requestSignal }),
      { signal, timeoutMs: authorityTimeoutMs, failureCode: 'AUTHORITY_UNAVAILABLE' },
    );
    if (!object(state) || (state.active !== true && state.active !== false)) throw fail('INVALID_AUTHORITY_RESPONSE', 503);
    if (state.active === false) throw fail('SESSION_INACTIVE');
    if (!identifier(state.sub) || !identifier(state.binding_id)) throw fail('INVALID_AUTHORITY_RESPONSE', 503);
    if (state.sub !== claims.sub || state.binding_id !== claims.pl_binding) throw fail('AUTHORITY_BINDING_MISMATCH');
    const now = clock() / 1000;
    if (!Number.isFinite(now) || !numericDate(state.auth_expires_at)) throw fail('INVALID_AUTHORITY_EXPIRY', 503);
    const expiresAt = Math.min(claims.exp, state.auth_expires_at, claims.pl_auth_exp ?? Infinity);
    if (expiresAt <= now) throw fail('SESSION_EXPIRED');
    return Object.freeze({
      subject: claims.sub, issuer, bindingId: claims.pl_binding,
      expiresAt, verifiedClaims: claims,
    });
  }

  async function authorize({ idToken, expectedUser, signal } = {}) {
    if (typeof idToken !== 'string' || idToken.length === 0 || idToken.length > 65536 || signal?.aborted) {
      throw signal?.aborted ? abortReason() : fail('MISSING_ID_TOKEN');
    }
    const verified = await bounded(
      requestSignal => verifyIdToken(idToken, { issuer, audience, signal: requestSignal }),
      { signal, timeoutMs: verificationTimeoutMs, failureCode: 'TOKEN_VERIFICATION_FAILED' },
    );
    const claims = validateClaims(verified?.payload, expectedUser);
    return checkState(claims, signal);
  }

  /** Continuous local liveness lease, for a caller that actually observes its AbortSignal.
   * A poll plus failed-authority timeout is capped below 1s, excluding event-loop stalls.
   * This does not wire a real provider/GenerationJobManager abort by itself.
   */
  async function watch({ idToken, expectedUser, signal } = {}) {
    let context = await authorize({ idToken, expectedUser, signal });
    const controller = new AbortController();
    let timer;
    let expiryTimer;
    let settle;
    let active = true;
    const closed = new Promise(resolve => { settle = resolve; });
    const stop = (reason = fail('WATCH_STOPPED', 499)) => {
      if (!active) return;
      active = false;
      clearTimeout(timer);
      clearTimeout(expiryTimer);
      signal?.removeEventListener('abort', callerAborted);
      const safeReason = reason instanceof LiveSessionError ? reason : fail('WATCH_STOPPED', 499);
      controller.abort(safeReason);
      settle(Object.freeze({ code: safeReason.code }));
    };
    const callerAborted = () => stop(abortReason());
    const scheduleExpiry = () => {
      clearTimeout(expiryTimer);
      const delay = Math.max(0, context.expiresAt * 1000 - clock());
      // Avoid Node's >2^31ms timeout overflow turning a long-lived session into an immediate expiry.
      expiryTimer = setTimeout(() => {
        if (context.expiresAt * 1000 <= clock()) stop(fail('SESSION_EXPIRED'));
        else if (active) scheduleExpiry();
      }, Math.min(delay, 2147483647));
    };
    const poll = async () => {
      if (!active) return;
      try {
        const next = await checkState(context.verifiedClaims, controller.signal);
        if (!active) return;
        // A live lease cannot gain lifetime from a changed authority response without a new login.
        context = Object.freeze({ ...next, expiresAt: Math.min(context.expiresAt, next.expiresAt) });
        scheduleExpiry();
        timer = setTimeout(poll, pollIntervalMs);
      } catch (error) {
        stop(error instanceof LiveSessionError ? error : fail('AUTHORITY_UNAVAILABLE', 503));
      }
    };
    signal?.addEventListener('abort', callerAborted, { once: true });
    if (signal?.aborted) callerAborted();
    if (active) {
      scheduleExpiry();
      timer = setTimeout(poll, pollIntervalMs);
    }
    return Object.freeze({ get context() { return context; }, signal: controller.signal, closed, stop });
  }

  return Object.freeze({ authorize, watch });
}
