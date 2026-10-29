/** LOCAL CANDIDATE ONLY. No mounts, publication, session mutation, cache or logging. */
import transientErrors from './errors.cjs';
export class RotationGateError extends Error {
  constructor(code, status = 401) { super(code); this.code = code; this.status = status; }
}
const reject = (code, status) => { throw new RotationGateError(code, status); };
const value = item => typeof item === 'string' && item.length > 0;
const id = user => String(user?._id ?? user?.id ?? '');
const audience = (aud, expected) => typeof aud === 'string' ? aud === expected :
  Array.isArray(aud) && aud.length > 0 && aud.every(value) && aud.includes(expected);
// Shared candidate error contract; do not maintain a divergent JWKS classifier.
export const verifierUnavailable = transientErrors.verifierUnavailable;
const nativeRetired = error => error?.code === 'OPENID_REFRESH_OWNERSHIP_LOST';

/**
 * Dependencies MUST use the pinned native credential/flight services; never accept
 * browser-provided identity, a decoded-only token, or a synthetic bridge in production.
 * This gate authorizes only entry to the unchanged native refresh controller.
 */
export function createRotationGate({ issuer, clientId, clock = Date.now,
  parseCookies, verifyCookie, getUser, findDurable, verifyIdToken, mainState, native }) {
  const pending = new WeakMap(); // Per-request expected identity, never a positive auth cache.
  async function available(operation, code) {
    try { return await operation(); }
    catch { reject(code, 503); }
  }

  const identity = user => ({ appUserId: id(user), openidSubject: user.openidId,
    openidIssuer: user.openidIssuer, tenantId: user.tenantId });
  function exactUser(user, expectedId) {
    if (!user || !value(id(user)) || id(user) !== expectedId || user.provider !== 'openid' ||
        user.tenantId || !value(user.openidId) || user.openidIssuer !== issuer) reject('identity_mismatch');
  }
  function exactSession(tokens, user) {
    if (!tokens || tokens.appUserId !== id(user) || tokens.openidSubject !== user.openidId ||
        tokens.openidIssuer !== issuer || tokens.tenantId || !value(tokens.idToken) ||
        !value(tokens.refreshToken)) reject('session_identity_mismatch');
  }
  async function claims(token, user, { expired = false, binding } = {}) {
    let result;
    try { result = await verifyIdToken(token, { issuer, audience: clientId, allowExpired: expired }); }
    catch (error) {
      if (verifierUnavailable(error)) reject('key_service_unavailable', 503);
      reject('invalid_signature_or_token');
    }
    const c = result?.payload;
    const now = clock() / 1000;
    if (!c || c.iss !== issuer || c.sub !== user.openidId || !audience(c.aud, clientId) ||
        !value(c.pl_binding) || (binding && c.pl_binding !== binding) ||
        !Number.isFinite(c.exp) || c.exp <= 0 || (!expired && c.exp <= now) ||
        (c.nbf !== undefined && (!Number.isFinite(c.nbf) || c.nbf > now)) ||
        (c.pl_auth_exp !== undefined && (!Number.isFinite(c.pl_auth_exp) || c.pl_auth_exp <= now || c.exp > c.pl_auth_exp))) {
      reject('signed_identity_or_binding_mismatch');
    }
    return c;
  }
  async function live(c) {
    let state, timer;
    const controller = new AbortController();
    try {
      state = await Promise.race([
        mainState({ binding_id: c.pl_binding, client_id: clientId }, { signal: controller.signal }),
        new Promise((_, no) => { timer = setTimeout(() => {
          controller.abort(); no(new RotationGateError('authority_unavailable', 503));
        }, 500); }),
      ]);
    } catch { reject('authority_unavailable', 503); }
    finally { clearTimeout(timer); }
    if (!state || typeof state.active !== 'boolean') reject('invalid_authority_response', 503);
    if (!state.active || state.sub !== c.sub || state.binding_id !== c.pl_binding ||
        !Number.isFinite(state.auth_expires_at) || state.auth_expires_at <= clock() / 1000) reject('main_session_inactive');
  }
  function durableMatches(record, user) {
    return record && String(record.user) === id(user) &&
      Number.isFinite(new Date(record.expiration).getTime()) && new Date(record.expiration).getTime() > clock();
  }

  async function publishedRotation(req, cookies, user, originalClaims) {
    const input = { req, user, refreshToken: cookies.refreshToken, identityContext: identity(user) };
    const normalKey = native.createOpenIDRefreshFlightKey(input);
    if (!value(normalKey)) reject('native_flight_key_unavailable', 503);
    const keys = [normalKey];
    // An opaque bridge alone is NOT a binding proof. Its completed native recovery
    // flight may provide signed successor material; no bridge token is copied to req.
    let bridge;
    try {
      bridge = await native.getRefreshTokenBridge({ oldRefreshToken: cookies.refreshToken,
        userId: id(user), tenantId: user.tenantId, openidIssuer: issuer });
    } catch { reject('native_bridge_unavailable', 503); }
    if (value(bridge)) {
      const bridgeKey = native.createRefreshTokenBridgeFlightKey({ oldRefreshToken: cookies.refreshToken,
        userId: id(user), tenantId: user.tenantId, openidIssuer: issuer });
      if (value(bridgeKey) && !keys.includes(bridgeKey)) keys.push(bridgeKey);
    }
    for (const key of keys) {
      let result;
      try {
        // Exact native key. A short explicit deadline cannot become a long wait/cache.
        result = await native.waitForOpenIDRefreshFlight({ key, requirePublication: true,
          timeoutMs: 500, intervalMs: 25 });
      } catch (error) {
        if (nativeRetired(error)) reject('native_generation_retired');
        const record = await available(() => native.findOpenIDRefreshFlight({ key }), 'native_store_unavailable');
        if (record?.status === 'revoked' || record?.revocationRequestedAt) reject('native_generation_revoked');
        // A known failed normal grant may already have a completed bridge recovery.
        // Availability errors/unknown records are never converted to authorization.
        if (record?.status === 'failed') continue;
        reject('native_flight_unavailable', 503);
      }
      if (!result) continue;
      if (result.__deferredPublication || !value(result.__flightOwnerId)) reject('native_publication_not_complete', 503);
      const accepted = result.acceptedIdentity;
      if (accepted && (accepted.appUserId !== id(user) || accepted.openidSubject !== user.openidId ||
          accepted.openidIssuer !== issuer || accepted.tenantId)) reject('native_result_identity_mismatch');
      const successor = result.tokenset ?? result;
      // appAuthToken/decoded claims are deliberately not accepted as ID-token proof.
      if (!value(successor.id_token) || !value(successor.refresh_token)) continue;
      await claims(successor.id_token, user, { binding: originalClaims.pl_binding });
      const durable = await available(() => findDurable({ userId: id(user), refreshToken: successor.refresh_token }), 'durable_store_unavailable');
      if (!durableMatches(durable, user)) reject('successor_durable_missing', 503);
      let generation;
      try { generation = await native.assertOpenIDRefreshFlightAvailable({ key, ownerId: result.__flightOwnerId }); }
      catch (error) {
        if (nativeRetired(error)) reject('native_generation_retired');
        reject('native_generation_store_unavailable', 503);
      }
      if (generation?.status === 'revoked' || generation?.revocationRequestedAt) reject('native_generation_revoked');
      if (!generation || generation === true || generation.status !== 'completed' || generation.ownerId !== result.__flightOwnerId) {
        reject('native_generation_result_unknown', 503);
      }
      await live(originalClaims);
      return;
    }
    reject('rotation_proof_not_yet_available', 503);
  }

  async function authorize(req) {
    const cookies = parseCookies(req.headers?.cookie || '');
    if (cookies.token_provider !== 'openid' || !value(cookies.refreshToken)) reject('missing_cookie_credential');
    let marker;
    try { marker = await verifyCookie(cookies, cookies.refreshToken); }
    catch { reject('invalid_signed_cookie'); }
    if (!value(marker?.userId)) reject('invalid_signed_cookie');
    const user = await available(() => getUser(marker.userId), 'user_store_unavailable');
    exactUser(user, marker.userId);
    const tokens = req.session?.openidTokens;
    exactSession(tokens, user);
    const originalClaims = await claims(tokens.idToken, user, { expired: true });
    // A stale tab may carry a different user's/binding's bearer after profile cookies
    // changed. Cookie-only bootstrap remains valid; a presented bearer must agree.
    if (req.headers?.authorization !== undefined) {
      const header = req.headers.authorization;
      const match = typeof header === 'string' && /^Bearer ([^\s,]+)$/i.exec(header);
      if (!match || match[1].length > 65536) reject('invalid_presented_bearer');
      await claims(match[1], user, { expired: true, binding: originalClaims.pl_binding });
    }
    await live(originalClaims);
    const oldDurable = await available(() => findDurable({ userId: id(user), refreshToken: cookies.refreshToken }), 'durable_store_unavailable');
    if (oldDurable && String(oldDurable.user) !== id(user)) reject('durable_owner_mismatch');
    if (!(durableMatches(oldDurable, user) && tokens.refreshToken === cookies.refreshToken)) {
      await publishedRotation(req, cookies, user, originalClaims);
    }
    const context = Object.freeze({ userId: id(user), subject: user.openidId, issuer,
      bindingId: originalClaims.pl_binding });
    pending.set(req, context);
    return context;
  }

  async function verifyNativeResponse(req, body) {
    const expected = pending.get(req);
    if (!expected) reject('refresh_was_not_admitted');
    const user = await available(() => getUser(expected.userId), 'user_store_unavailable');
    exactUser(user, expected.userId);
    if (user.openidId !== expected.subject) reject('identity_changed_during_refresh');
    const tokens = req.session?.openidTokens;
    exactSession(tokens, user);
    if (!body || id(body.user) !== expected.userId || !value(body.token) || body.token !== tokens.idToken) {
      reject('native_response_identity_mismatch');
    }
    const fresh = await claims(body.token, user, { binding: expected.bindingId });
    const durable = await available(() => findDurable({ userId: id(user), refreshToken: tokens.refreshToken }), 'durable_store_unavailable');
    if (!durableMatches(durable, user)) reject('native_response_durable_missing');
    let generation;
    try { generation = await native.assertOpenIDRefreshSessionGenerationAvailable({ key: tokens.publicationFlightKey,
      ownerId: tokens.publicationFlightOwnerId }); }
    catch (error) {
      if (nativeRetired(error)) reject('native_generation_retired');
      reject('native_generation_store_unavailable', 503);
    }
    if (generation?.status === 'revoked' || generation?.revocationRequestedAt) reject('native_generation_revoked');
    // The pinned session-generation API explicitly permits true for no retained row.
    if (generation !== true && (!generation || generation.status !== 'completed' ||
        generation.ownerId !== tokens.publicationFlightOwnerId)) reject('native_generation_result_unknown', 503);
    await live(fresh); // Required AGAIN after native refresh, immediately before delivery.
    pending.delete(req);
    return true;
  }
  return Object.freeze({ authorize, verifyNativeResponse, forget: req => pending.delete(req) });
}
