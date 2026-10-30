'use strict';
const { isUnavailable } = require('./errors.cjs');

const lifetimeMs = 10 * 60 * 1000;
const reserved = /^(?:api|oauth|images|assets|fonts|auth|login|register|forgot-password|reset-password|verify|chat|health|livez|readyz|metrics|index\.html)$/i;
const staticExtension = /\.(?:html?|js|mjs|css|map|json|wasm|webmanifest|png|jpe?g|gif|svg|ico|webp|avif|woff2?|ttf|otf|eot)$/i;

/** Path only: no query, fragment, encodings, normalization or external destination. */
function safeChatReturn(value, base = '/chat') {
  if (typeof value !== 'string' || value.length > 2048 || !value.startsWith('/') ||
      /[^A-Za-z0-9/._~-]/.test(value) || value.includes('//')) return null;
  if (value === base || value === base + '/') return value;
  if (!value.startsWith(base + '/')) return null;
  const segments = value.slice(base.length + 1).split('/');
  if (segments.some(segment => !segment || segment === '.' || segment === '..') ||
      reserved.test(segments[0]) || staticExtension.test(segments.at(-1))) return null;
  return value;
}

function documentTarget(req, base) {
  const raw = String(req.originalUrl ?? req.url ?? '').split(/[?#]/)[0];
  if (raw === '/' || raw === '/index.html') return base + '/';
  return safeChatReturn(base + raw, base) || base + '/';
}

function neutralPage(res, retry, status = 503) {
  res.set('Cache-Control', 'private, no-store');
  res.set('Referrer-Policy', 'no-referrer');
  if (status === 503) res.set('Retry-After', '1');
  return res.status(status).type('html').send('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>平行线 · AI 聊天</title><link rel="icon" type="image/svg+xml" href="/favicon.svg"></head><body style="margin:0;min-height:100vh;display:grid;place-content:center;background:#f8fafc;color:#475569;font:16px system-ui;text-align:center"><main><p>暂时无法完成登录验证</p><a style="color:#409eff" href="' + retry + '">重新验证</a></main></body></html>');
}

function saveSession(req) {
  if (!req.session || typeof req.session.save !== 'function') return Promise.reject(new Error('SSO session unavailable'));
  return new Promise((resolve, reject) => req.session.save(error => error ? reject(error) : resolve()));
}

function createDocumentEntry({ domainClient, authenticateDocument, clock = Date.now }) {
  const client = new URL(domainClient);
  const base = client.pathname.replace(/\/$/, '');
  if (base !== '/chat' || client.username || client.password || client.search || client.hash ||
      typeof authenticateDocument !== 'function') throw new Error('SSO document configuration invalid');
  const oauthStart = base + '/oauth/openid';
  const fallback = base + '/';
  const retry = oauthStart;
  const fresh = item => item && typeof item.createdAt === 'number' && item.createdAt <= clock() &&
    clock() - item.createdAt < lifetimeMs && safeChatReturn(item.target, base);
  const entries = req => Array.isArray(req.session?.plChatReturns) ? req.session.plChatReturns.filter(fresh).slice(-7) : [];

  async function document(req, res, sendIndexHtml) {
    if (!['GET', 'HEAD'].includes(req.method)) return sendIndexHtml(req, res);
    const url = new URL(req.originalUrl ?? req.url, 'http://localhost');
    if (/^\/login(?:\/|$)/i.test(url.pathname) && (url.searchParams.has('error') || url.searchParams.get('redirect') === 'false')) {
      return neutralPage(res, retry, 401);
    }
    let target = documentTarget(req, base);
    if (/^\/login(?:\/|$)/i.test(url.pathname)) {
      const continuation = url.searchParams.get('redirect_to');
      target = safeChatReturn(continuation, base) || safeChatReturn(base + continuation, base) || fallback;
    }
    try {
      // Same signed-cookie/durable/Express token proof and live Main check as refresh.
      // This admits only the public shell; every API still requires a current ID token.
      await authenticateDocument(req);
      if (/^\/login(?:\/|$)/i.test(url.pathname)) {
        res.set('Cache-Control', 'private, no-store');
        return res.redirect(302, target);
      }
      req.ssoDocumentTarget = target;
      return sendIndexHtml(req, res);
    } catch (error) {
      if (isUnavailable(error)) return neutralPage(res, target, 503);
      try {
        req.session.plChatPendingReturn = { target, createdAt: clock() };
        await saveSession(req);
        res.set('Cache-Control', 'private, no-store');
        res.set('Referrer-Policy', 'no-referrer');
        return res.redirect(302, oauthStart);
      } catch { return neutralPage(res, retry); }
    }
  }

  function prepareOAuth(req, res, pathname) {
    if (pathname !== '/oauth/openid' && pathname !== '/oauth/openid/callback') return;
    if (!req.session) throw new Error('SSO session unavailable');
    const url = new URL(req.originalUrl ?? req.url, 'http://localhost');
    const original = res.redirect;
    if (pathname === '/oauth/openid') {
      const provided = url.searchParams.getAll('returnTo');
      const pending = req.session.plChatPendingReturn;
      const target = (provided.length === 1 ? safeChatReturn(provided[0], base) : null) ||
        (provided.length === 0 && fresh(pending) ? pending.target : fallback);
      delete req.session.plChatPendingReturn;
      // Native Passport generates state/PKCE/nonce. Associate the target with exactly
      // that outgoing state; never replace state, fixed callback URL or token parameters.
      const originalSetHeader = res.setHeader;
      res.setHeader = function rememberNativeState(name, value) {
        if (typeof name === 'string' && name.toLowerCase() === 'location') {
          if (typeof value !== 'string') throw new Error('Native OIDC state unavailable');
          const destination = new URL(value, client.origin);
          const states = destination.searchParams.getAll('state');
          if (states.length !== 1 || !/^[A-Za-z0-9_-]{8,512}$/.test(states[0])) throw new Error('Native OIDC state unavailable');
          req.session.plChatReturns = [...entries(req), { state: states[0], target, createdAt: clock() }];
        }
        return Reflect.apply(originalSetHeader, this, arguments);
      };
      return;
    }
    const states = url.searchParams.getAll('state');
    const state = states.length === 1 ? states[0] : null;
    const saved = entries(req).find(item => item.state === state);
    res.redirect = function restoreNativeDestination(...args) {
      const tokens = req.session?.openidTokens;
      if (args.at(-1) === domainClient && req.user?.provider === 'openid' &&
          tokens?.appUserId === String(req.user.id ?? req.user._id ?? '') &&
          tokens.openidSubject === req.user.openidId && tokens.openidIssuer === req.user.openidIssuer) {
        args[args.length - 1] = saved?.target || fallback;
        req.session.plChatReturns = entries(req).filter(item => item.state !== state);
      }
      return Reflect.apply(original, this, args);
    };
  }
  return Object.freeze({ document, prepareOAuth });
}

/** Deployment hint for a pre-render router redirect; never an authentication proof. */
function injectSsoDocumentMeta(html, req) {
  if (!safeChatReturn(req.ssoDocumentTarget)) return html;
  return html.replace(/<head(?:\s[^>]*)?>/i,
    match => match + '<meta name="pl-sso-only" content="true">');
}

function unavailablePage(req, res) { return neutralPage(res, documentTarget(req, '/chat'), 503); }

module.exports = { safeChatReturn, createDocumentEntry, injectSsoDocumentMeta, unavailablePage };
