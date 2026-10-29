import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import entry from '../document-entry.cjs';

const domainClient = 'https://fixture.test/chat';
const makeSession = () => ({ saves: 0, save(callback) { this.saves++; callback(); } });
const request = (url, extra = {}) => ({ method: 'GET', originalUrl: url, headers: {}, session: makeSession(), ...extra });
const response = () => ({
  statusCode: 200, headers: {},
  set(name, value) { this.headers[name] = value; return this; },
  setHeader(name, value) { this.headers[name] = value; return this; },
  status(value) { this.statusCode = value; return this; },
  type(value) { this.contentType = value; return this; },
  send(value) { this.body = value; return this; },
  redirect(...args) { this.redirectArgs = args; return this; },
});

test('only canonical chat UI pathnames can be retained', () => {
  for (const value of ['/chat', '/chat/', '/chat/c/new', '/chat/c/8f627cc4-bd40-4db7-a81e-20a1036af4ab', '/chat/settings']) {
    assert.equal(entry.safeChatReturn(value), value);
  }
  for (const value of ['https://evil.test/chat', '//evil.test/chat', '/other/chat', '/chat//c/new', '/chat/../auth',
    '/chat/c/./new', '/chat/c/../new', '/chat/%2fapi', '/chat/%252e%252e/auth', '/chat/c/%41', '/chat/c\\new',
    '/chat/chat/c/new', '/chat/CHAT/c/new', '/chat/api/user', '/chat/oauth/openid', '/chat/images/x',
    '/chat/assets/x', '/chat/login', '/chat/index.html', '/chat/c/x.js', '/chat/c/new?token=x', '/chat/c/new#x',
    '/chat/c/x\r\nLocation:evil', '/chat/c/%zz']) assert.equal(entry.safeChatReturn(value), null, value);
});

test('unauthenticated root/index/deep documents save a path then enter the native OIDC route', async () => {
  const navigation = entry.createDocumentEntry({ domainClient, authenticateDocument: async () => { throw new Error('no proof'); } });
  for (const [url, target] of [['/', '/chat/'], ['/index.html', '/chat/'], ['/c/conversation-id', '/chat/c/conversation-id']]) {
    const req = request(url); const res = response(); let shells = 0;
    await navigation.document(req, res, () => { shells++; });
    assert.equal(shells, 0);
    assert.equal(req.session.plChatPendingReturn.target, target);
    assert.equal(req.session.saves, 1);
    assert.deepEqual(res.redirectArgs, [302, '/chat/oauth/openid']);
    assert.equal(res.headers['Cache-Control'], 'private, no-store');
  }
});

test('verified document proof loads the original chat directly; login documents never render a form', async () => {
  const calls = [];
  const navigation = entry.createDocumentEntry({ domainClient, authenticateDocument: async req => { calls.push(req); } });
  const req = request('/c/conversation-id'); const res = response(); let shells = 0;
  await navigation.document(req, res, () => { shells++; });
  assert.equal(shells, 1); assert.equal(req.ssoDocumentTarget, '/chat/c/conversation-id');
  assert.equal(res.redirectArgs, undefined); assert.equal(calls[0], req);
  const login = response();
  await navigation.document(request('/login?redirect_to=%2Fc%2Fconversation-id'), login, () => assert.fail('login shell'));
  assert.deepEqual(login.redirectArgs, [302, '/chat/c/conversation-id']);
});

test('missing session or native OAuth failure is a neutral stopped page, never an automatic loop/form', async () => {
  const navigation = entry.createDocumentEntry({ domainClient, authenticateDocument: async () => { throw new Error('failed'); } });
  for (const req of [request('/', { session: undefined }), request('/login?redirect=false&error=AUTH_FAILED')]) {
    const res = response();
    await navigation.document(req, res, () => assert.fail('login shell'));
    assert.equal([401, 503].includes(res.statusCode), true);
    assert.match(res.body, /重新验证/); assert.doesNotMatch(res.body, /<form|<script|http-equiv/i);
    assert.equal(res.redirectArgs, undefined);
  }
});

test('native outgoing state binds the return path and successful callback consumes only its matching path', () => {
  const navigation = entry.createDocumentEntry({ domainClient, authenticateDocument: async () => {} });
  const req = request('/oauth/openid?returnTo=%2Fchat%2Fc%2Fconversation-id'); const res = response();
  navigation.prepareOAuth(req, res, '/oauth/openid');
  const original = 'https://fixture.test/auth/oidc/auth?state=fixture_state_123&code_challenge=fixture-pkce&nonce=fixture-nonce&redirect_uri=https%3A%2F%2Ffixture.test%2Fchat%2Foauth%2Fopenid%2Fcallback';
  res.setHeader('Location', original);
  assert.equal(res.headers.Location, original, 'state/PKCE/nonce/fixed callback are untouched');
  assert.equal(req.session.plChatReturns[0].target, '/chat/c/conversation-id');
  req.session.openidTokens = { appUserId: 'user-a', openidSubject: 'sub-a', openidIssuer: 'https://fixture.test/auth/oidc' };
  const callback = request('/oauth/openid/callback?state=fixture_state_123&code=fixture-code', { session: req.session,
    user: { _id: 'user-a', provider: 'openid', openidId: 'sub-a', openidIssuer: 'https://fixture.test/auth/oidc' } });
  const out = response(); navigation.prepareOAuth(callback, out, '/oauth/openid/callback'); out.redirect(domainClient);
  assert.deepEqual(out.redirectArgs, ['/chat/c/conversation-id']);
  assert.equal(callback.session.plChatReturns.length, 0);
});

test('wrong state, expired target, unsafe target and native failure cannot redirect outside chat', () => {
  let now = 1000;
  const navigation = entry.createDocumentEntry({ domainClient, clock: () => now, authenticateDocument: async () => {} });
  for (const target of ['%2F%2Fevil.test', '%2Fchat%2Fapi%2Fuser', '%2Fchat%2Fc%2Fx%3Ftoken%3Dx']) {
    const req = request('/oauth/openid?returnTo=' + target); const res = response();
    navigation.prepareOAuth(req, res, '/oauth/openid'); res.setHeader('Location', 'https://fixture.test/auth/oidc/auth?state=fixture_state_123');
    assert.equal(req.session.plChatReturns[0].target, '/chat/');
  }
  const session = makeSession();
  session.plChatReturns = [{ target: '/chat/c/secret-path', state: 'other_state_123', createdAt: now }];
  session.openidTokens = { appUserId: 'a', openidSubject: 'a', openidIssuer: 'issuer' };
  const req = request('/oauth/openid/callback?state=fixture_state_123', { session,
    user: { _id: 'a', provider: 'openid', openidId: 'a', openidIssuer: 'issuer' } });
  let res = response(); navigation.prepareOAuth(req, res, '/oauth/openid/callback'); res.redirect(domainClient);
  assert.deepEqual(res.redirectArgs, ['/chat/']);
  res = response(); navigation.prepareOAuth(req, res, '/oauth/openid/callback'); res.redirect(domainClient + '/login?error=AUTH_FAILED');
  assert.deepEqual(res.redirectArgs, [domainClient + '/login?error=AUTH_FAILED']);
  session.plChatReturns = [{ target: '/chat/c/secret-path', state: 'fixture_state_123', createdAt: now }];
  now += 600001;
  res = response(); navigation.prepareOAuth(req, res, '/oauth/openid/callback'); res.redirect(domainClient);
  assert.deepEqual(res.redirectArgs, ['/chat/']);
});

test('loading bootstrap masks early paint and converts only internal login navigation to native OIDC', () => {
  const html = entry.injectDocumentLoadingShell('<html><head><script type="module" src="app.js"></script></head><body><div id="root"><div id="loading-container"></div></div></body></html>', { ssoDocumentTarget: '/chat/c/conversation-id' });
  assert.ok(html.indexOf('data-pl-sso-entry') < html.indexOf('src="app.js"'));
  assert.match(html, /正在进入聊天/); assert.doesNotMatch(html, /document\.cookie|localStorage|access_token|id_token/);
  const script = /<script data-pl-sso-entry>([\s\S]*?)<\/script>/.exec(html)[1];
  const replacements = []; const historyCalls = []; const attributes = new Set();
  const location = { origin: 'https://fixture.test', pathname: '/chat/c/conversation-id', href: 'https://fixture.test/chat/c/conversation-id', replace(value) { replacements.push(value); } };
  const context = { URL, Array, location, history: { pushState(...args) { historyCalls.push(args); }, replaceState(...args) { historyCalls.push(args); } },
    document: { documentElement: { removeAttribute(name) { attributes.delete(name); }, setAttribute(name) { attributes.add(name); } },
      addEventListener() {}, getElementById() { return { children: [{ id: 'loading-container' }] }; } },
    MutationObserver: class { constructor(callback) { this.callback = callback; } observe() {} }, window: { addEventListener() {} } };
  vm.runInNewContext(script, context);
  context.history.pushState({}, '', '/chat/c/another'); assert.equal(historyCalls.length, 1); assert.equal(replacements.length, 0);
  context.history.replaceState({}, '', '/chat/login?redirect_to=%2Fc%2Fconversation-id');
  assert.deepEqual(replacements, ['/chat/oauth/openid?returnTo=%2Fchat%2Fc%2Fconversation-id']);
  assert.equal(attributes.has('data-pl-sso-ready'), false); assert.equal(historyCalls.length, 1);
});

test('native index applies document gate after session initialization and before shell/static index delivery', () => {
  const source = fs.readFileSync(new URL('../index.js', import.meta.url), 'utf8');
  assert.ok(source.indexOf('await configureSocialLogins(app, appConfig)') < source.indexOf("app.get('/index.html', chatSsoRuntime.document(sendIndexHtml))"));
  assert.match(source, /createSpaFallback\(chatSsoRuntime\.document\(sendIndexHtml\)\)/);
  assert.match(source, /index\\\.html\$\/i\.test\(req\.path\) \? next\(\)/);
  assert.ok(source.indexOf('injectDocumentLoadingShell(updatedIndexHtml, req)') < source.indexOf('applyCspNonce(updatedIndexHtml, csp.nonce)'));
});
