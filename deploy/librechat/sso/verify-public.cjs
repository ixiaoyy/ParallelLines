'use strict';
// Public checks only. No account credentials, model requests or response tokens are logged.
const assert = require('node:assert/strict');
const origin = 'https://pingxingxian.space';
const results = {};
const request = (path, options = {}) => fetch(origin + path, { ...options, redirect: 'manual', signal: AbortSignal.timeout(15000) });
async function main() {
  const discovery = await request('/auth/oidc/.well-known/openid-configuration');
  assert.equal(discovery.status, 200);
  const metadata = await discovery.json();
  assert.equal(metadata.issuer, origin + '/auth/oidc');
  assert.equal(new URL(metadata.jwks_uri).origin, origin);
  const jwks = await fetch(metadata.jwks_uri, { signal: AbortSignal.timeout(15000), redirect: 'error' }).then(r => r.json());
  assert.ok(jwks.keys.length > 0 && jwks.keys.every(k => k.kty === 'RSA' && k.alg === 'RS256' && !k.d && !k.p && !k.q));
  results.publicDiscovery = true;
  const configResponse = await request('/chat/api/config');
  assert.equal(configResponse.status, 200);
  const config = await configResponse.json();
  assert.equal(config.appTitle, '\u5e73\u884c\u7ebf \u00b7 AI \u804a\u5929');
  assert.equal(config.emailLoginEnabled, false);
  assert.equal(config.registrationEnabled, false);
  assert.equal(config.socialLoginEnabled, true);
  results.singleLoginConfiguration = true;
  for (const [path, method] of [['/chat/api/user', 'GET'], ['/chat/api/auth/refresh', 'POST'], ['/chat/api/auth/login', 'POST'], ['/chat/api/auth/register', 'POST'], ['/chat/api/admin/config', 'GET'], ['/chat/api/v1/models', 'GET']]) {
    const r = await request(path, { method });
    assert.equal(r.status, 401, 'Anonymous or local authentication must fail: ' + path);
  }
  results.localAndAnonymousPrivateAccessDenied = true;
  const privateImage = await request('/chat/images/000000000000000000000001/sso-check.png');
  assert.ok([401, 403, 404].includes(privateImage.status));
  results.anonymousImageDenied = true;
  const cookies = new Map();
  let url = origin + '/chat/oauth/openid';
  let arrived = false;
  for (let attempt = 0; attempt < 10; attempt++) {
    const parsed = new URL(url);
    assert.equal(parsed.origin, origin);
    if (parsed.pathname === '/auth') {
      const target = parsed.searchParams.get('redirect');
      assert.ok(/^\/auth\/chat\?interaction_id=[A-Za-z0-9_-]{10,200}$/.test(target || ''));
      arrived = true;
      break;
    }
    const response = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(15000), headers: { cookie: [...cookies.values()].join('; ') } });
    for (const value of response.headers.getSetCookie()) {
      const pair = value.split(';', 1)[0];
      cookies.set(pair.slice(0, pair.indexOf('=')), pair);
    }
    assert.ok([301, 302, 303, 307, 308].includes(response.status), 'OIDC start must redirect to the main login');
    url = new URL(response.headers.get('location'), url).href;
  }
  assert.ok(arrived);
  results.anonymousChatRedirectsToMainAuth = true;
  const chatPage = await request('/chat/');
  assert.equal(chatPage.status, 200);
  const html = await chatPage.text();
  const base = new URL(/<base[^>]+href="([^"]+)"/.exec(html)?.[1] || '/chat/', origin);
  const assets = [...html.matchAll(/(?:src|href)="((?:\/chat\/)?assets\/[^"?#]+)[^"]*"/g)].map(match => new URL(match[1], base));
  assert.ok(assets.length > 0);
  assert.equal(assets[0].origin, origin);
  assert.equal((await request(assets[0].pathname)).status, 200);
  assert.equal((await request('/games')).status, 200);
  assert.equal((await request('/auth/chat?interaction_id=invalid')).status, 200);
  results.chatAssetsAndMainRoutesHealthy = true;
  console.log(JSON.stringify({ verified: true, results, authenticatedBrowserFlow: 'requires normal main-site session; no test account created', modelRequests: 0 }));
}
main().catch(() => { console.error(JSON.stringify({ verified: false, results, error: 'public_sso_check_failed' })); process.exitCode = 1; });
