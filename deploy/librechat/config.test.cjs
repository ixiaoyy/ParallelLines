const test = require('node:test');
const assert = require('node:assert/strict');
const { buildConfig, disabledMessage } = require('./config.cjs');

test('missing key exposes no GPT models and a clear disabled message', () => {
  const r = buildConfig({ OPENAI_CHAT_MODELS: 'gpt-6-luna' });
  assert.equal(r.enabled, false);
  assert.equal(r.runtimeKey, '');
  assert.deepEqual(r.selectedModels, ['gpt-6-luna']);
  assert.deepEqual(r.approvedProfile.endpoints.openAI.models, []);
  assert.deepEqual(r.config.endpoints.openAI.models, []);
  assert.deepEqual(r.config.modelSpecs.list, []);
  assert.equal(r.config.interface.modelSelect, false);
  assert.equal(r.config.interface.customWelcome, disabledMessage);
  assert.equal(r.reason, 'missing_server_key');
});
test('key without an administrator-selected model stays disabled', () => {
  const r = buildConfig({ OPENAI_API_KEY: 'synthetic-unit-only-not-a-provider-key' });
  assert.equal(r.enabled, false);
  assert.equal(r.runtimeKey, '');
  assert.equal(r.reason, 'missing_model_selection');
});
test('personal-key sentinel and placeholders never enable family-provided credentials', () => {
  for (const key of ['user_provided', 'replace-with-key', 'your_key', '<key>']) {
    const r = buildConfig({ OPENAI_API_KEY: key, OPENAI_CHAT_MODELS: 'gpt-6-luna' });
    assert.equal(r.enabled, false);
    assert.equal(r.runtimeKey, '');
  }
});
test('explicit GPT list uses native OpenAI and Responses without serializing the server credential', () => {
  const key = 'synthetic-unit-only-not-a-provider-key';
  const r = buildConfig({ OPENAI_API_KEY: key, OPENAI_CHAT_MODELS: 'gpt-6-luna,gpt-6.1-sol,gpt-6-luna' });
  assert.equal(r.enabled, true);
  assert.deepEqual(r.models, ['gpt-6-luna', 'gpt-6.1-sol']);
  assert.deepEqual(r.selectedModels, ['gpt-6-luna', 'gpt-6.1-sol']);
  assert.deepEqual(Object.keys(r.config.endpoints), ['openAI']);
  assert.equal(r.config.modelSpecs.enforce, true);
  assert.deepEqual(r.config.endpoints.openAI.models, []);
  assert.deepEqual(r.config.modelSpecs.list, []);
  assert.equal(r.config.interface.modelSelect, false);
  assert.ok(r.approvedProfile.modelSpecs.list.length === 2);
  assert.ok(r.approvedProfile.modelSpecs.list.every(x => x.preset.useResponsesApi && x.preset.endpoint === 'openAI'));
  assert.deepEqual(r.approvedProfile.endpoints.openAI.models, ['gpt-6-luna', 'gpt-6.1-sol']);
  assert.ok(!JSON.stringify(r.approvedProfile).includes(key));
  assert.ok(!JSON.stringify(r.config).includes(key));
  assert.ok(!JSON.stringify(r.config).includes('FamilyMock'));
});
test('non-GPT or specialized image/audio model IDs fail closed', () => {
  for (const model of ['claude-sonnet', 'gpt-image-2', 'gpt-audio', 'gpt-6-luna,other-provider', 'gpt-6-luna/../../bad']) {
    const r = buildConfig({ OPENAI_API_KEY: 'synthetic-unit-only-not-a-provider-key', OPENAI_CHAT_MODELS: model });
    assert.equal(r.enabled, false);
    assert.deepEqual(r.models, []);
  }
});
test('production upload policy enables only JPEG PNG WEBP on OpenAI; no arbitrary files or custom provider', () => {
  const { config } = buildConfig({});
  const endpoints = config.fileConfig.endpoints;
  assert.deepEqual(endpoints.openAI.supportedMimeTypes, ['^image/(jpeg|png|webp)$']);
  for (const name of ['agents', 'assistants', 'azureAssistants', 'azureOpenAI', 'anthropic', 'google', 'bedrock', 'custom']) {
    assert.equal(endpoints[name].disabled, true);
  }
  assert.equal(config.secureImageLinks, true);
});
