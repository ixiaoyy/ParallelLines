'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createModelAccess, generationEndpoint } = require('../model-access.cjs');

const fixtureKey = 'synthetic-fixture-only';
const user = { id: 'synthetic-a', provider: 'openid' };
const candidate = { name: 'family-gpt-1', preset: { endpoint: 'openAI', model: 'gpt-6-luna' } };
function config(models = []) {
  return { endpoints: { openAI: { models } }, modelSpecs: { enforce: true, list: [structuredClone(candidate)] } };
}
function request(extra = {}) {
  return { method: 'POST', originalUrl: '/api/agents/chat/openAI', user,
    body: { endpoint: 'openAI', spec: candidate.name }, ...extra };
}
function response() {
  return { status(code) { this.statusCode = code; return this; }, json(body) { this.body = body; return this; } };
}
async function authorize(req = request(), profile = config(), key = fixtureKey) {
  const seen = [];
  const guard = createModelAccess({ env: { OPENAI_API_KEY: key }, getConfig: async current => { seen.push(current); return profile; } });
  const res = response();
  return { allowed: await guard(req, res), req, res, seen };
}

test('candidate specs do not grant a user with an empty endpoint catalog', async () => {
  const result = await authorize();
  assert.equal(result.allowed, false);
  assert.equal(result.res.statusCode, 403);
  assert.equal(result.res.body.error, 'gpt_account_not_enabled');
  assert.deepEqual(result.seen, [user]);
  assert.equal(result.req.config, undefined);
});

test('Key presence never replaces the independent user grant', async () => {
  const result = await authorize(request(), config([]));
  assert.equal(result.allowed, false);
  assert.equal(result.res.statusCode, 403);
});

test('missing, placeholder and personal-key sentinels return 503 before config lookup', async () => {
  for (const key of ['', ' ', 'user_provided', 'replace-key', 'your_key', '<key>']) {
    const result = await authorize(request(), config(['gpt-6-luna']), key);
    assert.equal(result.allowed, false);
    assert.equal(result.res.statusCode, 503);
    assert.equal(result.res.body.error, 'gpt_server_not_enabled');
    assert.equal(result.seen.length, 0);
  }
});

test('only a current user profile with the selected model is admitted', async () => {
  const profile = config(['gpt-6-luna']);
  const result = await authorize(request(), profile);
  assert.equal(result.allowed, true);
  assert.equal(result.req.config, profile);
  assert.equal(result.res.body, undefined);
});

test('the enforced spec determines the model instead of forged body.model', async () => {
  const req = request({ body: { endpoint: 'openAI', spec: candidate.name, model: 'gpt-6.1-sol' } });
  const result = await authorize(req, config(['gpt-6.1-sol']));
  assert.equal(result.allowed, false);
  assert.equal(result.res.body.error, 'gpt_model_not_allowed');
});

test('an ungranted selected spec cannot be hidden behind an allowed body.model', async () => {
  const profile = config(['gpt-6-luna']);
  profile.modelSpecs.list.push({ name: 'family-gpt-2', preset: { endpoint: 'openAI', model: 'gpt-6.1-sol' } });
  const result = await authorize(request({ body: { endpoint: 'openAI', spec: 'family-gpt-2', model: 'gpt-6-luna' } }), profile);
  assert.equal(result.allowed, false);
  assert.equal(result.res.statusCode, 403);
});

test('missing or unknown specs and an unenforced config fail closed', async () => {
  for (const spec of [undefined, '', 'unknown', ['family-gpt-1']]) {
    const result = await authorize(request({ body: { endpoint: 'openAI', spec } }), config(['gpt-6-luna']));
    assert.equal(result.allowed, false);
    assert.equal(result.res.body.error, 'gpt_model_not_allowed');
  }
  const profile = config(['gpt-6-luna']);
  profile.modelSpecs.enforce = false;
  assert.equal((await authorize(request(), profile)).allowed, false);
});

test('alternate provider endpoint, body, and spec cannot escape the OpenAI restriction', async () => {
  for (const req of [request({ originalUrl: '/api/agents/chat/anthropic' }),
    request({ body: { endpoint: 'anthropic', spec: candidate.name } }),
    request({ body: { endpoint: 'openAI', endpointType: 'anthropic', spec: candidate.name } })]) {
    const result = await authorize(req, config(['gpt-6-luna']));
    assert.equal(result.allowed, false);
    assert.equal(result.res.body.error, 'gpt_provider_not_enabled');
  }
  const profile = config(['gpt-6-luna']);
  profile.modelSpecs.list[0].preset.endpoint = 'anthropic';
  assert.equal((await authorize(request(), profile)).allowed, false);
});

test('resolver failure returns 503 without falling back to a wider profile', async () => {
  const guard = createModelAccess({ env: { OPENAI_API_KEY: fixtureKey }, getConfig: async () => { throw new Error('fixture'); } });
  const res = response();
  assert.equal(await guard(request(), res), false);
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.error, 'gpt_config_unavailable');
});

test('case variants and trailing slash of the native route receive the same check', async () => {
  for (const path of ['/API/Agents/Chat/OpenAI', '/api/agents/chat/openAI/']) {
    const result = await authorize(request({ originalUrl: path }), config([]));
    assert.equal(result.allowed, false);
    assert.equal(result.res.body.error, 'gpt_account_not_enabled');
  }
});

test('control/read routes remain the responsibility of existing binding and native ACL guards', async () => {
  for (const req of [request({ method: 'GET', originalUrl: '/api/convos' }),
    request({ originalUrl: '/api/agents/chat/abort' }), request({ originalUrl: '/api/auth/refresh' }),
    request({ originalUrl: '/api/agents/chat/steer' })]) {
    const result = await authorize(req, config([]), '');
    assert.equal(result.allowed, true);
    assert.equal(result.seen.length, 0);
  }
});

test('ambiguous route segments are denied instead of normalizing into admitted endpoints', async () => {
  for (const path of ['/api/agents/chat/%6fpenAI', '/api/agents/chat/openAI//', '/api/agents/chat/openAI\\']) {
    assert.equal(generationEndpoint(request({ originalUrl: path })), '!invalid');
    const result = await authorize(request({ originalUrl: path }), config(['gpt-6-luna']));
    assert.equal(result.allowed, false);
    assert.equal(result.res.statusCode, 403);
  }
});
