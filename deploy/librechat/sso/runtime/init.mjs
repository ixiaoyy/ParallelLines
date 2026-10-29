import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createLiveSessionGuard, createSessionStateClient } from './core/live-session.mjs';
import { createLibreChatBearerSessionMiddleware, createLibreChatPrivateImageSessionMiddleware } from './adapters/librechat-draft.mjs';
import { createJobTracker } from './job-tracker.mjs';
import documentEntry from './document-entry.cjs';
import modelAccess from './model-access.cjs';

const enabled = value => value === 'true' || value === '1';
const nonempty = value => typeof value === 'string' && value.length > 0;
const userId = user => String(user?._id ?? user?.id ?? '');
const audienceMatches = (aud, expected) => typeof aud === 'string' ? aud === expected : Array.isArray(aud) && aud.includes(expected);
const safeError = () => new Error('SSO session rejected');
const rawBearer = req => {
  const value = req.headers?.authorization;
  const match = typeof value === 'string' && /^Bearer ([^\s,]+)$/i.exec(value);
  if (!match) throw safeError();
  return match[1];
};
function canonicalPath(req) {
  const value = new URL(req.originalUrl ?? req.url, 'http://localhost').pathname;
  if (/%(?:2f|5c|00)/i.test(value) || value.includes('\\') || value.includes('//')) throw safeError();
  return value.toLowerCase().replace(/\/$/, '') || '/';
}
function reject(res) {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) return res.destroy();
  return res.status(401).json({ error: 'sso_session_required' });
}
function validJwksUrl(value) {
  const url = new URL(value);
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if (url.username || url.password || url.hash || url.search ||
      (url.protocol !== 'https:' && !(local && url.protocol === 'http:'))) throw safeError();
  return url;
}

/** Runtime env is injected by the owner. This module never logs or writes credentials. */
export async function createRuntime({ env = process.env, dependencies = {} } = {}) {
  if (!enabled(env.SSO_REQUIRED) || !enabled(env.OPENID_REUSE_TOKENS) ||
      !nonempty(env.OPENID_ISSUER) || !nonempty(env.OPENID_CLIENT_ID) ||
      !nonempty(env.JWT_REFRESH_SECRET) || !nonempty(env.CHAT_SSO_BRIDGE_SECRET)) throw safeError();
  const nativeRequire = createRequire('/app/api/package.json');
  const api = dependencies.api ?? nativeRequire('@librechat/api');
  const models = dependencies.models ?? nativeRequire('~/models');
  const runAsSystem = dependencies.runAsSystem ?? nativeRequire('@librechat/data-schemas').runAsSystem;
  const cookie = dependencies.cookie ?? nativeRequire('cookie');
  let jose;
  let jwks;
  const algorithm = env.CHAT_SSO_ID_TOKEN_ALG || 'RS256';
  if (!['RS256', 'ES256', 'EdDSA'].includes(algorithm)) throw safeError();
  if (!dependencies.verifyIdToken || !dependencies.verifyRefreshIdToken) {
    jose = dependencies.jose ?? await import(pathToFileURL(nativeRequire.resolve('jose')).href);
    const config = (dependencies.getOpenIdConfig ?? nativeRequire('~/strategies').getOpenIdConfig)();
    const metadata = config.serverMetadata();
    if (metadata.issuer !== env.OPENID_ISSUER) throw safeError();
    jwks = jose.createRemoteJWKSet(validJwksUrl(metadata.jwks_uri), { timeoutDuration: 500 });
  }
  const verifyIdToken = dependencies.verifyIdToken ?? ((token, { issuer, audience }) =>
    jose.jwtVerify(token, jwks, { issuer, audience, algorithms: [algorithm] }));
  const getSessionState = dependencies.getSessionState ?? createSessionStateClient({
    url: env.CHAT_SSO_SESSION_STATE_URL, bridgeSecret: env.CHAT_SSO_BRIDGE_SECRET,
    clientId: env.OPENID_CLIENT_ID,
  });
  const options = { verifyIdToken, getSessionState, issuer: env.OPENID_ISSUER, audience: env.OPENID_CLIENT_ID,
    clientId: env.OPENID_CLIENT_ID, pollIntervalMs: 200, authorityTimeoutMs: 500 };
  const guard = createLiveSessionGuard(options);
  const admission = createLiveSessionGuard({ ...options, requireExpectedUser: false });
  const tracker = createJobTracker({ guard, manager: api.GenerationJobManager });
  const expectedUser = user => ({ _id: userId(user), provider: user.provider,
    openidId: user.openidId, openidIssuer: user.openidIssuer });
  function trust(req, user, context) {
    if (!req.ssoVerifiedUser) Object.defineProperty(req, 'ssoVerifiedUser', {
      value: Object.freeze({ id: userId(user), provider: 'openid', openidId: user.openidId, openidIssuer: user.openidIssuer }),
      enumerable: false, writable: false, configurable: false,
    });
    req.ssoVerifiedContext = context;
  }
  async function exactUser(subject, issuer) {
    const user = await runAsSystem(() => models.findUser({
      provider: 'openid', openidId: subject, openidIssuer: issuer, tenantId: { $exists: false },
    }, '-password -__v -totpSecret -backupCodes'));
    if (!user || user.provider !== 'openid' || user.openidId !== subject ||
        user.openidIssuer !== issuer || user.tenantId || !userId(user)) throw safeError();
    return user;
  }
  async function preverify(req) {
    if (req.ssoVerifiedUser && req.ssoVerifiedContext) return req.ssoVerifiedContext;
    if (req.headers?.['x-tenant-id']) throw safeError();
    const token = rawBearer(req);
    const context = await admission.authorize({ idToken: token });
    const user = await exactUser(context.subject, context.issuer);
    trust(req, user, context);
    return context;
  }
  const bearerMiddleware = createLibreChatBearerSessionMiddleware({ guard });
  const authorizeModel = modelAccess.createModelAccess({ env, getConfig: dependencies.getConfig ?? (user =>
    nativeRequire('~/server/services/Config').getAppConfig(api.getAppConfigOptionsFromUser(user))) });
  async function bearer(req, res, next) {
    let authenticated = false;
    await bearerMiddleware(req, res, () => { authenticated = true; });
    if (!authenticated || !await authorizeModel(req, res)) return;
    tracker.capture(req, res, { idToken: rawBearer(req), expectedUser: expectedUser(req.user), context: req.ssoLiveSession.context });
    return next();
  }
  const image = createLibreChatPrivateImageSessionMiddleware({
    guard, parseCookies: cookie.parse, jwtRefreshSecret: env.JWT_REFRESH_SECRET,
    getValidOpenIDReuseCredential: api.getValidOpenIDReuseCredential,
    findSession: query => runAsSystem(() => models.findSession(query)),
    getUserById: id => runAsSystem(() => models.getUserById(id, '-password -__v -totpSecret -backupCodes')),
  });
  async function cookieProof(req) {
    const cookies = cookie.parse(req.headers?.cookie || '');
    if (cookies.token_provider !== 'openid' || !nonempty(cookies.refreshToken)) throw safeError();
    const signed = api.getValidOpenIDReuseCredential(cookies, env.JWT_REFRESH_SECRET, cookies.refreshToken);
    if (!signed?.userId) throw safeError();
    const [session, user] = await Promise.all([
      runAsSystem(() => models.findSession({ userId: signed.userId, refreshToken: cookies.refreshToken })),
      runAsSystem(() => models.getUserById(signed.userId, '-password -__v -totpSecret -backupCodes')),
    ]);
    const tokens = req.session?.openidTokens;
    const expiration = new Date(session?.expiration).getTime();
    if (!session || String(session.user) !== signed.userId || !Number.isFinite(expiration) || expiration <= Date.now() ||
        !user || userId(user) !== signed.userId || user.provider !== 'openid' || user.tenantId ||
        !tokens || tokens.appUserId !== signed.userId || tokens.openidSubject !== user.openidId ||
        tokens.openidIssuer !== user.openidIssuer || tokens.refreshToken !== cookies.refreshToken || !nonempty(tokens.idToken)) throw safeError();
    return { user, tokens };
  }
  // Only refresh is allowed to prove a signed-but-expired ID token. It never grants private API
  // access: native OP refresh must issue a new token and all resulting API calls re-enter ingress.
  const verifyRefreshIdToken = dependencies.verifyRefreshIdToken ?? (async token => {
    const verified = await jose.compactVerify(token, jwks, { algorithms: [algorithm] });
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(verified.payload));
  });
  async function authorizeRefresh(req) {
    const { user, tokens } = await cookieProof(req);
    const claims = await verifyRefreshIdToken(tokens.idToken);
    const now = Date.now() / 1000;
    if (claims.iss !== env.OPENID_ISSUER || claims.sub !== user.openidId || user.openidIssuer !== claims.iss ||
        !audienceMatches(claims.aud, env.OPENID_CLIENT_ID) || !nonempty(claims.pl_binding) ||
        !Number.isFinite(claims.exp) || claims.exp <= 0 ||
        (claims.nbf !== undefined && (!Number.isFinite(claims.nbf) || claims.nbf > now)) ||
        (claims.pl_auth_exp !== undefined && (!Number.isFinite(claims.pl_auth_exp) || claims.pl_auth_exp <= now))) throw safeError();
    const state = await getSessionState({ binding_id: claims.pl_binding, client_id: env.OPENID_CLIENT_ID }, { signal: AbortSignal.timeout(500) });
    const deliveredAt = Date.now() / 1000;
    if (state.active !== true || state.sub !== claims.sub || state.binding_id !== claims.pl_binding ||
        !Number.isFinite(state.auth_expires_at) || state.auth_expires_at <= deliveredAt ||
        (claims.pl_auth_exp !== undefined && claims.pl_auth_exp <= deliveredAt)) throw safeError();
    trust(req, user, { subject: claims.sub, issuer: claims.iss, bindingId: claims.pl_binding });
  }
  const documentNavigation = documentEntry.createDocumentEntry({
    domainClient: env.DOMAIN_CLIENT,
    authenticateDocument: authorizeRefresh,
  });
  async function revokeSession(req) {
    const { user, tokens } = await cookieProof(req);
    const claims = await verifyRefreshIdToken(tokens.idToken);
    if (claims.iss !== env.OPENID_ISSUER || claims.sub !== user.openidId || user.openidIssuer !== claims.iss ||
        !audienceMatches(claims.aud, env.OPENID_CLIENT_ID) || !nonempty(claims.pl_binding) ||
        claims.pl_binding.length > 1024 || !Number.isFinite(claims.exp) || claims.exp <= 0) throw safeError();
    if (req.headers?.authorization !== undefined) {
      const presentedToken = rawBearer(req);
      const presented = presentedToken === tokens.idToken ? claims : await verifyRefreshIdToken(presentedToken);
      if (presented.iss !== claims.iss || presented.sub !== claims.sub ||
          !audienceMatches(presented.aud, env.OPENID_CLIENT_ID) || presented.pl_binding !== claims.pl_binding) throw safeError();
    }
    // A signed expired ID token may revoke its own binding; it cannot authorize private data.
    // The endpoint is derived from the fixed trusted status URL, never from request data.
    let revokeBinding = dependencies.revokeBinding;
    if (!revokeBinding) {
      const url = new URL(env.CHAT_SSO_SESSION_STATE_URL);
      if (!url.pathname.endsWith('/session-state')) throw safeError();
      url.pathname = url.pathname.slice(0, -'/session-state'.length) + '/revoke';
      revokeBinding = createSessionStateClient({ url: url.href, bridgeSecret: env.CHAT_SSO_BRIDGE_SECRET,
        clientId: env.OPENID_CLIENT_ID });
    }
    const controller = new AbortController();
    let timer;
    try {
      const state = await Promise.race([
        Promise.resolve().then(() => revokeBinding({ binding_id: claims.pl_binding, client_id: env.OPENID_CLIENT_ID },
          { signal: controller.signal })),
        new Promise((_, reject) => { timer = setTimeout(() => { controller.abort(); reject(safeError()); }, 500); }),
      ]);
      if (!state || state.active !== false ||
          (state.sub !== undefined && state.sub !== null && state.sub !== claims.sub) ||
          (state.binding_id !== undefined && state.binding_id !== claims.pl_binding)) throw safeError();
    } finally { clearTimeout(timer); }
  }
  const disabledPaths = /^\/api\/(?:auth\/(?:login|register|requestpasswordreset|resetpassword|passkey)|admin(?:\/|$)|api-keys(?:\/|$)|keys(?:\/|$)|agents\/v1(?:\/|$)|v1(?:\/|$))/;
  async function ingress(req, res, next) {
    try {
      const pathname = canonicalPath(req);
      if (pathname.startsWith('/oauth/')) {
        if (req.method === 'GET' && ['/oauth/openid', '/oauth/openid/callback'].includes(pathname)) {
          documentNavigation.prepareOAuth(req, res, pathname);
          return next();
        }
        return reject(res);
      }
      if (!/^\/api(?:\/|$)/.test(pathname)) return next();
      if (disabledPaths.test(pathname)) return reject(res);
      // The initial ordinary-user flow uses an explicit provider endpoint. Do not admit
      // unregistered default-agent/resume jobs through a route without binding capture.
      if (req.method === 'POST' && ['/api/agents/chat', '/api/agents/chat/resume'].includes(pathname)) return reject(res);
      if ((req.method === 'GET' || req.method === 'HEAD') && pathname === '/api/config' && req.headers?.authorization === undefined) return next();
      if (req.method === 'POST' && pathname === '/api/auth/refresh') {
        await authorizeRefresh(req);
        return next();
      }
      if (req.method === 'POST' && pathname === '/api/auth/logout') {
        const { user } = await cookieProof(req);
        trust(req, user, null);
        req.ssoCleanupOnly = true;
        return next();
      }
      const context = await preverify(req);
      await tracker.authorizeAttachment(req, { context, expectedUser: req.ssoVerifiedUser, res });
      next();
    } catch { reject(res); }
  }
  function allowCleanup(req) {
    return req.ssoCleanupOnly === true && req.authStrategy === 'openidJwt' && req.user?.provider === 'openid' &&
      userId(req.user) === req.ssoVerifiedUser?.id && req.user.openidId === req.ssoVerifiedUser.openidId &&
      req.user.openidIssuer === req.ssoVerifiedUser.openidIssuer;
  }
  return Object.freeze({ ingress, preverify, bearer, image, allowCleanup, revokeSession,
    document: documentNavigation.document, close: () => tracker.close() });
}
