import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createRuntime } from '../init.mjs';

// Synthetic opaque handles only. Injected verifiers stand for the JOSE verification
// boundary; these tests exercise ingress/session binding, not native crypto or network.
const issuer = 'http://127.0.0.1:3190/auth/oidc';
const clientId = 'fixture-chat-client';
const userA = Object.freeze({ _id: 'app-a', provider: 'openid', openidId: 'subject-a', openidIssuer: issuer, email: 'same@fixture.test' });
const userB = Object.freeze({ _id: 'app-b', provider: 'openid', openidId: 'subject-b', openidIssuer: issuer, email: 'same@fixture.test' });
const goodCookies = 'token_provider=openid; refreshToken=fixture-refresh-a; openid_user_id=fixture-signed-marker-a';

function request(path = '/api/convos', extra = {}) {
  return Object.assign(new EventEmitter(), { method: 'GET', originalUrl: path, headers: {} }, extra);
}

function response() {
  return Object.assign(new EventEmitter(), {
    statusCode: 200, headersSent: false, writableEnded: false, destroyed: false,
    status(code) { this.statusCode = code; return this; },
    json(body) { this.body = body; this.writableEnded = true; this.emit('finish'); return this; },
    destroy() { this.destroyed = true; this.emit('close'); },
  });
}

async function fixture(t, options = {}) {
  const now = Date.now() / 1000;
  const claims = { iss: issuer, aud: clientId, sub: userA.openidId, pl_binding: 'binding-a', exp: now + 600, ...options.claims };
  const control = {
    claims,
    refreshClaims: { ...claims, exp: now - 600 }, // refresh alone may verify signed-but-expired ID claims
    state: { active: true, sub: claims.sub, binding_id: claims.pl_binding, auth_expires_at: now + 300 },
    lookupUser: { ...userA }, cookieUser: { ...userA },
    durable: { user: userA._id, expiration: new Date(Date.now() + 60000) },
    markerAccepted: true, keyAccepted: true, refreshKeyAccepted: true, authorityError: false,
    ...options.control,
  };
  const calls = { find: [], getUser: [], session: [], marker: [], verify: [], refreshVerify: [], state: [], revoke: [], system: 0, manager: 0 };
  const env = {
    SSO_REQUIRED: 'true', OPENID_REUSE_TOKENS: 'true', OPENID_ISSUER: issuer,
    OPENID_CLIENT_ID: clientId, JWT_REFRESH_SECRET: 'fixture-only-refresh-signing-value',
    CHAT_SSO_BRIDGE_SECRET: 'fixture-only-bridge-value', ...options.env,
    DOMAIN_CLIENT: 'http://127.0.0.1:3190/chat',
  };
  const dependencies = {
    getConfig: options.getConfig,
    api: {
      GenerationJobManager: {
        async getJob() { calls.manager++; throw new Error('unexpected fixture job lookup'); },
        async abortJob() { calls.manager++; throw new Error('unexpected fixture job abort'); },
      },
      getValidOpenIDReuseCredential(cookies, secret, refreshToken) {
        calls.marker.push({ provider: cookies.token_provider, marker: cookies.openid_user_id, refreshToken });
        assert.equal(secret, 'fixture-only-refresh-signing-value');
        return control.markerAccepted && cookies.openid_user_id === 'fixture-signed-marker-a' &&
          refreshToken === 'fixture-refresh-a' ? { userId: userA._id } : null;
      },
    },
    models: {
      async findUser(query, projection) { calls.find.push({ query, projection }); return control.lookupUser; },
      async getUserById(id, projection) { calls.getUser.push({ id, projection }); return control.cookieUser; },
      async findSession(query) { calls.session.push(query); return control.durable; },
    },
    async runAsSystem(callback) { calls.system++; return callback(); },
    cookie: {
      parse(raw) {
        assert.equal(typeof raw, 'string');
        return Object.fromEntries(raw.split(';').filter(Boolean).map(pair => {
          const [key, ...value] = pair.trim().split('=');
          return [key, value.join('=')];
        }));
      },
    },
    async verifyIdToken(token, expected) {
      calls.verify.push({ token, issuer: expected.issuer, audience: expected.audience });
      if (!control.keyAccepted || token !== 'fixture-id-a') throw new Error('fixture rejected key/signature');
      return { payload: { ...control.claims } };
    },
    async verifyRefreshIdToken(token) {
      calls.refreshVerify.push(token);
      if (control.refreshKeyAccepted && token === 'fixture-other-binding') return { ...control.refreshClaims, pl_binding: 'binding-other' };
      if (!control.refreshKeyAccepted || token !== 'fixture-expired-id-a') throw new Error('fixture rejected refresh signature');
      return { ...control.refreshClaims };
    },
    async getSessionState(body, { signal }) {
      calls.state.push(body);
      assert.equal(signal instanceof AbortSignal, true);
      if (control.authorityError) throw new Error('fixture authority failure');
      return control.state == null ? control.state : { ...control.state };
    },
    async revokeBinding(body, { signal }) {
      calls.revoke.push(body);
      assert.equal(signal instanceof AbortSignal, true);
      if (control.revokeError) throw new Error('synthetic revoke unavailable');
      if (control.revokeHang) return new Promise(() => {});
      if (control.revokeResult !== undefined) return control.revokeResult;
      control.state.active = false;
      return { active: false, sub: body.binding_id === 'binding-a' ? userA.openidId : 'unexpected', binding_id: body.binding_id };
    },
  };
  const runtime = await createRuntime({ env, dependencies });
  t.after(() => {
    runtime.close();
    assert.equal(calls.manager, 0, 'ingress/preverify tests never start a job watcher');
  });
  return { runtime, calls, control, env, dependencies };
}

async function ingress(f, req) {
  const res = response();
  let nextCalls = 0;
  await f.runtime.ingress(req, res, () => { nextCalls++; });
  return { req, res, nextCalls };
}

function denied(result) {
  assert.equal(result.nextCalls, 0);
  assert.equal(result.res.statusCode, 401);
  assert.deepEqual(result.res.body, { error: 'sso_session_required' });
  assert.equal(result.req.ssoVerifiedUser, undefined);
}

function refreshRequest(path = '/api/auth/refresh') {
  return request(path, { method: 'POST', headers: { cookie: goodCookies }, session: { openidTokens: {
    appUserId: userA._id, openidSubject: userA.openidId, openidIssuer: issuer,
    refreshToken: 'fixture-refresh-a', idToken: 'fixture-expired-id-a',
  } } });
}

test('anonymous config and OIDC navigation are allowed without private identity', async t => {
  const f = await fixture(t);
  for (const req of [request('/api/config'), request('/api/config', { method: 'HEAD' }),
    request('/oauth/openid', { session: {} }), request('/oauth/openid/callback', { session: {} })]) {
    const result = await ingress(f, req);
    assert.equal(result.nextCalls, 1);
    assert.equal(req.ssoVerifiedUser, undefined);
  }
  assert.equal(f.calls.verify.length, 0);
  assert.equal(f.calls.state.length, 0);
});

test('verified bearer checks the effective model grant before generation capture or native routing', async t => {
  const config = { endpoints: { openAI: { models: [] } }, modelSpecs: { enforce: true,
    list: [{ name: 'family-gpt-1', preset: { endpoint: 'openAI', model: 'gpt-6-luna' } }] } };
  const f = await fixture(t, { env: { OPENAI_API_KEY: 'synthetic-fixture-only' },
    getConfig: async user => { assert.equal(user._id, userA._id); return config; } });
  const req = request('/api/agents/chat/openAI', { method: 'POST', user: userA,
    authStrategy: 'openidJwt', headers: { authorization: 'Bearer fixture-id-a' },
    body: { endpoint: 'openAI', spec: 'family-gpt-1' } });
  const res = response(); let called = false;
  await f.runtime.bearer(req, res, () => { called = true; });
  assert.equal(called, false);
  assert.equal(res.statusCode, 403);
  assert.equal(res.body.error, 'gpt_account_not_enabled');
  assert.equal(f.calls.manager, 0);
});

test('private APIs reject no Bearer, fake identity headers, and API-key-looking handles', async t => {
  const f = await fixture(t);
  for (const headers of [{}, { 'x-user-id': userA._id, 'x-user-email': userA.email },
    { 'x-api-key': 'fixture-key' }, { authorization: 'Bearer fixture-api-key' },
    { authorization: 'Basic fixture-id-a' }, { authorization: ['Bearer fixture-id-a'] },
    { authorization: 'Bearer fixture-id-a,Bearer fixture-other' }]) {
    denied(await ingress(f, request('/api/convos', { headers })));
  }
  assert.equal(f.calls.find.length, 0);
  assert.equal(f.calls.state.length, 0);
});

test('local auth, admin exchange and API-key routes stay disabled even with valid Bearer', async t => {
  const f = await fixture(t);
  for (const path of ['/api/auth/login', '/api/auth/register', '/api/auth/requestPasswordReset',
    '/api/auth/resetPassword', '/api/auth/passkey/authenticate', '/api/admin/login/local',
    '/api/admin/oauth/exchange', '/api/api-keys', '/api/keys', '/api/agents/v1/responses',
    '/api/v1/chat/completions', '/oauth/google']) {
    denied(await ingress(f, request(path, { method: 'POST', headers: { authorization: 'Bearer fixture-id-a' } })));
  }
  assert.equal(f.calls.verify.length, 0);
});

test('valid Bearer without cookies looks up only exact native subject/issuer and stores read-only server identity', async t => {
  const f = await fixture(t);
  const req = request('/api/convos', { headers: {
    authorization: 'Bearer fixture-id-a', 'x-user-id': userB._id, 'x-user-email': userB.email,
  } });
  const result = await ingress(f, req);
  assert.equal(result.nextCalls, 1);
  assert.deepEqual(f.calls.find, [{ query: {
    provider: 'openid', openidId: userA.openidId, openidIssuer: issuer, tenantId: { $exists: false },
  }, projection: '-password -__v -totpSecret -backupCodes' }]);
  assert.deepEqual(req.ssoVerifiedUser, { id: userA._id, provider: 'openid', openidId: userA.openidId, openidIssuer: issuer });
  const descriptor = Object.getOwnPropertyDescriptor(req, 'ssoVerifiedUser');
  assert.deepEqual({ writable: descriptor.writable, enumerable: descriptor.enumerable, configurable: descriptor.configurable },
    { writable: false, enumerable: false, configurable: false });
  assert.equal(Object.isFrozen(req.ssoVerifiedUser), true);
  assert.throws(() => { req.ssoVerifiedUser = { id: userB._id }; }, TypeError);
  assert.throws(() => { req.ssoVerifiedUser.id = userB._id; }, TypeError);
  assert.deepEqual(f.calls.state, [{ binding_id: 'binding-a', client_id: clientId }]);
  assert.equal(f.calls.marker.length, 0);
});

test('same-email native account, local provider, tenant override and different authority subject cannot bind', async t => {
  for (const change of [
    f => { f.control.lookupUser = { ...userB }; },
    f => { f.control.lookupUser = { ...userA, provider: 'local' }; },
    f => { f.control.lookupUser = { ...userA, tenantId: 'other-tenant' }; },
    f => { f.control.lookupUser = null; },
    f => { f.control.state.sub = userB.openidId; },
  ]) {
    const f = await fixture(t);
    change(f);
    denied(await ingress(f, request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a' } })));
    for (const { query } of f.calls.find) {
      assert.equal(query.openidId, userA.openidId);
      assert.equal(Object.hasOwn(query, 'email'), false);
    }
  }
  const f = await fixture(t);
  denied(await ingress(f, request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a', 'x-tenant-id': 'other-tenant' } })));
  assert.equal(f.calls.verify.length, 0);
});

test('inactive, absent, unavailable, expired or mismatched main state denies private ingress', async t => {
  for (const change of [
    f => { f.control.state.active = false; }, f => { f.control.state = null; },
    f => { f.control.authorityError = true; }, f => { f.control.state.auth_expires_at = 1; },
    f => { f.control.state.binding_id = 'binding-b'; },
  ]) {
    const f = await fixture(t);
    change(f);
    denied(await ingress(f, request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a' } })));
    assert.equal(f.calls.find.length, 0);
  }
});

test('wrong issuer/audience, expired ID token or rejected signing key fails before native lookup', async t => {
  for (const change of [
    f => { f.control.claims.iss = 'https://wrong-issuer.fixture.test'; },
    f => { f.control.claims.aud = 'other-client'; },
    f => { f.control.claims.exp = 1; },
    f => { f.control.keyAccepted = false; },
  ]) {
    const f = await fixture(t);
    change(f);
    denied(await ingress(f, request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a' } })));
    assert.equal(f.calls.state.length, 0);
    assert.equal(f.calls.find.length, 0);
  }
});

test('refresh requires signed OpenID cookie proof, matching Express ID token and a live main binding', async t => {
  const f = await fixture(t);
  const req = refreshRequest();
  const result = await ingress(f, req);
  assert.equal(result.nextCalls, 1);
  assert.equal(req.ssoVerifiedUser.id, userA._id);
  assert.equal(req.ssoCleanupOnly, undefined);
  assert.deepEqual(f.calls.marker, [{ provider: 'openid', marker: 'fixture-signed-marker-a', refreshToken: 'fixture-refresh-a' }]);
  assert.deepEqual(f.calls.session, [{ userId: userA._id, refreshToken: 'fixture-refresh-a' }]);
  assert.deepEqual(f.calls.refreshVerify, ['fixture-expired-id-a']);
  assert.deepEqual(f.calls.state, [{ binding_id: 'binding-a', client_id: clientId }]);
  assert.equal(f.calls.verify.length, 0, 'expired signed ID is accepted only by refresh verifier');
});

test('refresh refuses local/legacy cookies, absent Express state, rotated refresh or cross-user state', async t => {
  for (const change of [
    (f, req) => { req.headers.cookie = ''; },
    (f, req) => { req.headers.cookie = goodCookies.replace('token_provider=openid', 'token_provider=local'); },
    f => { f.control.markerAccepted = false; },
    f => { f.control.durable = null; },
    f => { f.control.durable.expiration = new Date(1); },
    (f, req) => { delete req.session; },
    (f, req) => { req.session.openidTokens.refreshToken = 'fixture-rotated-refresh'; },
    (f, req) => { req.session.openidTokens.appUserId = userB._id; },
    (f, req) => { req.session.openidTokens.openidSubject = userB.openidId; },
    f => { f.control.cookieUser = { ...userB }; },
    f => { f.control.cookieUser = { ...userA, provider: 'local' }; },
  ]) {
    const f = await fixture(t);
    const req = refreshRequest();
    change(f, req);
    denied(await ingress(f, req));
    assert.equal(f.calls.state.length, 0);
  }
});

test('refresh does not extend missing/expired main sessions or accept wrong ID-token claims/key', async t => {
  for (const change of [
    f => { f.control.state = null; }, f => { f.control.state.active = false; },
    f => { f.control.state.auth_expires_at = 1; }, f => { f.control.authorityError = true; },
    f => { f.control.state.sub = userB.openidId; },
    f => { f.control.refreshClaims.iss = 'https://wrong-issuer.fixture.test'; },
    f => { f.control.refreshClaims.aud = 'other-client'; },
    f => { f.control.refreshClaims.pl_auth_exp = 1; },
    f => { f.control.refreshClaims.nbf = Date.now() / 1000 + 6000; },
    f => { f.control.refreshKeyAccepted = false; },
  ]) {
    const f = await fixture(t);
    change(f);
    denied(await ingress(f, refreshRequest()));
  }
});

test('logout cleanup is cookie-scoped and still requires the same native openidJwt identity', async t => {
  const f = await fixture(t, { control: { state: null } });
  const req = refreshRequest('/api/auth/logout');
  const result = await ingress(f, req);
  assert.equal(result.nextCalls, 1);
  assert.equal(req.ssoCleanupOnly, true);
  assert.equal(req.ssoVerifiedContext, null);
  assert.equal(f.calls.state.length, 0, 'cleanup does not grant or revive an authority session');
  assert.equal(f.runtime.allowCleanup(req), false);
  req.authStrategy = 'openidJwt';
  req.user = { ...userA };
  assert.equal(f.runtime.allowCleanup(req), true);
  for (const patch of [
    { authStrategy: 'jwt' }, { user: { ...userA, provider: 'local' } },
    { user: { ...userB } }, { user: { ...userA, openidIssuer: 'https://other.fixture.test' } },
  ]) {
    const altered = { ...req, ...patch, ssoVerifiedUser: req.ssoVerifiedUser };
    assert.equal(f.runtime.allowCleanup(altered), false);
  }
});

test('unverified cleanup flags or request headers cannot authorize logout or private data', async t => {
  const f = await fixture(t);
  for (const path of ['/api/auth/logout', '/api/convos']) {
    const req = request(path, { method: 'POST', headers: { 'x-user-id': userA._id, 'x-sso-cleanup-only': 'true' } });
    denied(await ingress(f, req));
    assert.equal(req.ssoCleanupOnly, undefined);
    assert.equal(f.runtime.allowCleanup(req), false);
  }
});

test('revokeSession consumes only the signed cookie-session binding and old ID-token replay fails', async t => {
  const f = await fixture(t);
  await f.runtime.preverify(request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a' } }));
  const req = refreshRequest('/api/auth/logout');
  req.body = { binding_id: 'attacker-binding' };
  req.headers['x-pl-binding'] = 'attacker-binding';
  await f.runtime.revokeSession(req);
  assert.deepEqual(f.calls.revoke, [{ binding_id: 'binding-a', client_id: clientId }]);
  await assert.rejects(f.runtime.preverify(request('/api/convos', { headers: { authorization: 'Bearer fixture-id-a' } })));
  await f.runtime.revokeSession(req); // idempotent inactive binding may be cleaned up again
  assert.equal(f.calls.revoke.length, 2);
});

test('revokeSession rejects unsigned, cross-user, wrong-issuer/audience or missing binding before revoke', async t => {
  for (const change of [
    f => { f.control.refreshKeyAccepted = false; },
    f => { f.control.refreshClaims.sub = userB.openidId; },
    f => { f.control.refreshClaims.iss = 'https://wrong.fixture.test'; },
    f => { f.control.refreshClaims.aud = 'another-client'; },
    f => { delete f.control.refreshClaims.pl_binding; },
    f => { f.control.markerAccepted = false; },
  ]) {
    const f = await fixture(t);
    change(f);
    await assert.rejects(f.runtime.revokeSession(refreshRequest('/api/auth/logout')));
    assert.equal(f.calls.revoke.length, 0);
  }
});

test('revokeSession rejects active/mismatched acknowledgements and bounds unavailable authority', async t => {
  for (const result of [{ active: true }, null, { active: false, sub: userB.openidId }, { active: false, binding_id: 'other' }]) {
    const f = await fixture(t, { control: { revokeResult: result } });
    await assert.rejects(f.runtime.revokeSession(refreshRequest('/api/auth/logout')));
  }
  const unavailable = await fixture(t, { control: { revokeError: true } });
  await assert.rejects(unavailable.runtime.revokeSession(refreshRequest('/api/auth/logout')));
  const hangs = await fixture(t, { control: { revokeHang: true } });
  const began = performance.now();
  await assert.rejects(hangs.runtime.revokeSession(refreshRequest('/api/auth/logout')));
  assert.ok(performance.now() - began < 1000);
});

test('revokeSession accepts real null-sub inactive ACK but rejects a different presented-token binding', async t => {
  const f = await fixture(t, { control: { revokeResult: {
    active: false, sub: null, binding_id: 'binding-a', auth_expires_at: null,
  } } });
  const req = refreshRequest('/api/auth/logout');
  req.headers.authorization = 'Bearer fixture-expired-id-a';
  await f.runtime.revokeSession(req);
  assert.equal(f.calls.revoke.length, 1);
  const different = await fixture(t);
  const altered = refreshRequest('/api/auth/logout');
  altered.headers.authorization = 'Bearer fixture-other-binding';
  await assert.rejects(different.runtime.revokeSession(altered));
  assert.equal(different.calls.revoke.length, 0);
});
