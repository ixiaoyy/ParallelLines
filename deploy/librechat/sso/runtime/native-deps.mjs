/** Pinned-LibreChat adapter. LOCAL CANDIDATE: must be called inside that API runtime. */
import { createRotationGate } from './rotation-gate.mjs';

export function createNativeRotationGate({ nativeRequire, env, verifyIdToken, verifyRefreshIdToken, getSessionState }) {
  const api = nativeRequire('@librechat/api');
  const models = nativeRequire('~/models');
  const { runAsSystem } = nativeRequire('@librechat/data-schemas');
  const cookie = nativeRequire('cookie');
  const flight = nativeRequire('~/server/services/OpenIDRefreshFlight');
  const bridge = nativeRequire('~/server/services/RefreshTokenBridge');
  const call = fn => (...args) => runAsSystem(() => fn(...args));
  return createRotationGate({
    issuer: env.OPENID_ISSUER, clientId: env.OPENID_CLIENT_ID,
    parseCookies: cookie.parse,
    verifyCookie: (cookies, token) => api.getValidOpenIDReuseCredential(cookies, env.JWT_REFRESH_SECRET, token),
    getUser: id => runAsSystem(() => models.getUserById(id, '-password -__v -totpSecret -backupCodes -federatedTokens')),
    findDurable: call(models.findSession),
    verifyIdToken: async (token, { allowExpired, ...options }) => allowExpired ?
      { payload: await verifyRefreshIdToken(token) } : verifyIdToken(token, options),
    mainState: getSessionState,
    native: {
      createOpenIDRefreshFlightKey: flight.createOpenIDRefreshFlightKey,
      createRefreshTokenBridgeFlightKey: bridge.createRefreshTokenBridgeFlightKey,
      getRefreshTokenBridge: call(bridge.getRefreshTokenBridge),
      waitForOpenIDRefreshFlight: call(flight.waitForOpenIDRefreshFlight),
      findOpenIDRefreshFlight: call(models.findOpenIDRefreshFlight),
      assertOpenIDRefreshFlightAvailable: call(flight.assertOpenIDRefreshFlightAvailable),
      assertOpenIDRefreshSessionGenerationAvailable: call(flight.assertOpenIDRefreshSessionGenerationAvailable),
    },
  });
}
