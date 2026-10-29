import Provider, { interactionPolicy, errors } from 'oidc-provider';
import { createMainBridge, MainAuthorityError } from './main-bridge.mjs';

export const CLIENT_ID = 'parallellines-chat';
const now = () => Math.floor(Date.now() / 1000);
const interactionIdPattern = /^[A-Za-z0-9_-]{8,128}$/;
const approvalPattern = /^[A-Za-z0-9_-]{32,128}$/;

function grantIdFor(ctx, token) {
  const entities = ctx.oidc.entities;
  return token?.grantId || entities.RefreshToken?.grantId || entities.AuthorizationCode?.grantId ||
    entities.AccessToken?.grantId || entities.Grant?.jti || ctx.oidc.result?.consent?.grantId;
}
function reply(res, status, code) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' });
  res.end(JSON.stringify({ error: code }));
}
const recoveryDocument = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>平行线 · 重新进入聊天</title></head><body><main><h1>聊天登录未完成</h1><p>登录链接可能已失效，请重新进入聊天。</p><a href="/chat/">重新进入聊天</a></main></body></html>';
function replyFinishFailure(req, res, code) {
  const form = (req.headers['content-type'] || '').split(';')[0].trim() === 'application/x-www-form-urlencoded';
  const html = String(req.headers.accept || '').split(',').some(part => {
    const [mime, ...params] = part.trim().toLowerCase().split(';').map(value => value.trim());
    const q = params.find(value => value.startsWith('q='));
    const quality = q === undefined ? 1 : Number(q.slice(2));
    return mime === 'text/html' && Number.isFinite(quality) && quality > 0 && quality <= 1;
  });
  if (!form || !html) return reply(res, 403, code);
  res.writeHead(403, {
    'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
    'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
    'Content-Security-Policy': "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  });
  res.end(recoveryDocument);
}
async function finishBody(req) {
  const mime = (req.headers['content-type'] || '').split(';')[0].trim();
  if (!['application/json', 'application/x-www-form-urlencoded'].includes(mime)) throw new Error('invalid_finish_body');
  const chunks = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 2048) throw new Error('invalid_finish_body');
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString('utf8');
  let body;
  if (mime === 'application/json') body = JSON.parse(text);
  else {
    const entries = new URLSearchParams(text);
    if ([...entries.keys()].some(key => entries.getAll(key).length !== 1)) throw new Error('invalid_finish_body');
    body = Object.fromEntries(entries);
  }
  if (!body || typeof body !== 'object' || Array.isArray(body) ||
      Object.keys(body).some(key => !['interaction_id', 'approval_code'].includes(key)) ||
      !interactionIdPattern.test(body.interaction_id || '') || !approvalPattern.test(body.approval_code || '')) throw new Error('invalid_finish_body');
  return body;
}

/** Standard OIDC OP, backed exclusively by Main approval/session-state and durable grants. */
export function createIdentityProvider({ config, store, fetchImpl }) {
  const bridge = createMainBridge({ apiRoot: config.apiRoot, bridgeSecret: config.bridgeSecret, fetchImpl });
  const policy = interactionPolicy.base();
  // The OP session can never silently stand in for the browser's current Main identity.
  policy.get('login').checks.add(new interactionPolicy.Check(
    'main_session_confirmation', 'Confirm the current main-site session', 'login_required',
    ctx => !ctx.oidc.result?.login,
  ));
  const identityFor = (ctx, token) => {
    const grantId = grantIdFor(ctx, token);
    const identity = grantId && store.getGrantBinding(grantId);
    if (!identity || identity.auth_expires_at <= now()) throw new errors.InvalidGrant('Main session binding expired');
    return identity;
  };
  const ttl = (maximum = Infinity) => (ctx, token) => {
    const identity = identityFor(ctx, token);
    const live = ctx.state.plMainIdentity;
    const expiry = Math.min(identity.auth_expires_at, live?.binding_id === identity.binding_id ? live.auth_expires_at : Infinity);
    const remaining = Math.min(maximum, expiry - now());
    if (remaining < 1) throw new errors.InvalidGrant('Main session binding expired');
    return remaining;
  };
  const provider = new Provider(config.issuer, {
    adapter: store.Adapter,
    clients: [{
      client_id: CLIENT_ID, client_secret: config.clientSecret,
      redirect_uris: [config.callbackUri], grant_types: ['authorization_code', 'refresh_token'],
      response_types: ['code'], token_endpoint_auth_method: 'client_secret_basic',
      id_token_signed_response_alg: 'RS256',
    }],
    jwks: config.jwks,
    cookies: {
      keys: config.cookieKeys,
      names: { session: 'pl_oidc_session', interaction: 'pl_oidc_interaction', resume: 'pl_oidc_resume' },
      short: { httpOnly: true, sameSite: 'lax', secure: config.secureCookies, path: '/auth' },
      long: { httpOnly: true, sameSite: 'lax', secure: config.secureCookies, path: '/auth' },
    },
    features: { devInteractions: { enabled: false }, userinfo: { enabled: true } },
    pkce: { required: () => true },
    scopes: ['openid', 'profile', 'offline_access'],
    claims: { openid: ['sub', 'pl_binding', 'pl_auth_exp'], profile: ['name', 'preferred_username'] },
    // LibreChat's ID-token reuse path must receive the stable profile identifier too.
    conformIdTokenClaims: false,
    issueRefreshToken: (_ctx, client, source) => client.clientId === CLIENT_ID && client.grantTypeAllowed('refresh_token') && source.scopes.has('openid'),
    rotateRefreshToken: true,
    expiresWithSession: () => false,
    ttl: {
      Grant: 86400, Interaction: 120, Session: 300,
      AuthorizationCode: ttl(30), AccessToken: ttl(300), IdToken: ttl(300), RefreshToken: ttl(),
    },
    interactions: {
      policy,
      url: async (_ctx, interaction) => config.mainOrigin + '/auth/chat?interaction_id=' + encodeURIComponent(interaction.uid),
    },
    findAccount: async (ctx, sub, token) => {
      let identity;
      try {
        identity = identityFor(ctx, token);
        if (identity.sub !== sub) return undefined;
        const state = await bridge.sessionState(identity);
        const effective = { ...identity, auth_expires_at: Math.min(identity.auth_expires_at, state.auth_expires_at) };
        if (effective.auth_expires_at <= now()) return undefined;
        ctx.state.plMainIdentity = effective;
        return {
          accountId: sub,
          claims: async () => ({ sub, preferred_username: 'pl-' + sub, name: identity.name, pl_binding: identity.binding_id, pl_auth_exp: effective.auth_expires_at }),
        };
      } catch (error) {
        if (error instanceof MainAuthorityError && error.code === 'main_binding_inactive') {
          const grantId = grantIdFor(ctx, token);
          if (grantId) store.revokeGrant(grantId);
        }
        return undefined;
      }
    },
    renderError: async (ctx) => {
      ctx.type = 'application/json'; ctx.body = { error: 'oidc_request_rejected' };
    },
  });
  provider.proxy = true;
  const callback = provider.callback();
  const publicPrefix = new URL(config.issuer).pathname;
  const handler = async (req, res) => {
    const requested = new URL(req.url, config.issuer);
    if (req.method === 'GET' && requested.pathname === '/health') return reply(res, 200, 'ok');
    if (requested.pathname !== publicPrefix && !requested.pathname.startsWith(publicPrefix + '/')) return reply(res, 404, 'not_found');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');
    // There is one configured external authority; never derive public URLs from caller forwarding headers.
    req.headers['x-forwarded-proto'] = new URL(config.issuer).protocol.slice(0, -1);
    req.headers['x-forwarded-host'] = new URL(config.issuer).host;
    if (req.method === 'POST' && requested.pathname === publicPrefix + '/interaction/finish') {
      if (req.headers.origin !== config.mainOrigin) return reply(res, 403, 'origin_rejected');
      let grantId;
      try {
        const input = await finishBody(req);
        const details = await provider.interactionDetails(req, res);
        if (details.uid !== input.interaction_id || details.params.client_id !== CLIENT_ID || details.params.redirect_uri !== config.callbackUri) return replyFinishFailure(req, res, 'interaction_mismatch');
        const identity = await bridge.exchange({ interactionId: details.uid, approvalCode: input.approval_code });
        const grant = new provider.Grant({ accountId: identity.sub, clientId: CLIENT_ID });
        const requestedScopes = String(details.params.scope || '').split(' ').filter(scope => ['openid', 'profile', 'offline_access'].includes(scope));
        grant.addOIDCScope(requestedScopes.join(' '));
        grantId = await grant.save(identity.auth_expires_at - now());
        store.setGrantBinding(grantId, identity);
        await provider.interactionFinished(req, res, {
          login: { accountId: identity.sub, remember: false }, consent: { grantId },
        }, { mergeWithLastSubmission: false });
      } catch {
        if (grantId) store.revokeGrant(grantId);
        if (!res.headersSent) return replyFinishFailure(req, res, 'approval_rejected');
        res.destroy();
      }
      return;
    }
    // Equivalent to mounting the OP at /auth/oidc in Express: oidc-provider owns relative routes.
    req.originalUrl = req.url;
    req.url = (requested.pathname.slice(publicPrefix.length) || '/') + requested.search;
    return callback(req, res);
  };
  return { provider, handler };
}
