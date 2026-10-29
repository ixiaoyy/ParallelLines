const test = require('node:test');
const assert = require('node:assert/strict');
const { buildConfig, brandTitle, disabledMessage, accountRestrictedMessage } = require('./config.cjs');

test('missing key retains visible native candidates with a disabled reason and an empty authorization catalog', () => {
  const r = buildConfig({ OPENAI_CHAT_MODELS: 'gpt-6-luna' });
  assert.equal(r.enabled, false);
  assert.equal(r.runtimeKey, '');
  assert.deepEqual(r.selectedModels, ['gpt-6-luna']);
  assert.deepEqual(r.approvedProfile.endpoints.openAI.models, []);
  assert.deepEqual(r.config.endpoints.openAI.models, []);
  assert.deepEqual(r.config.modelSpecs.list.map(spec => spec.preset.model), ['gpt-6-luna']);
  assert.ok(r.config.modelSpecs.list.every(spec => spec.description === disabledMessage));
  assert.equal(r.config.interface.modelSelect, false);
  assert.equal(r.config.interface.customWelcome, brandTitle);
  assert.equal(r.footer, disabledMessage);
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
  const r = buildConfig({ OPENAI_API_KEY: key, OPENAI_CHAT_MODELS: 'gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol,gpt-6-luna' });
  assert.equal(r.enabled, true);
  assert.deepEqual(r.models, ['gpt-6-luna', 'gpt-6.1-terra', 'gpt-6.1-sol']);
  assert.deepEqual(r.selectedModels, ['gpt-6-luna', 'gpt-6.1-terra', 'gpt-6.1-sol']);
  assert.deepEqual(Object.keys(r.config.endpoints), ['openAI']);
  assert.equal(r.config.modelSpecs.enforce, true);
  assert.deepEqual(r.config.endpoints.openAI.models, []);
  assert.deepEqual(r.config.modelSpecs.list.map(spec => spec.preset.model), ['gpt-6-luna', 'gpt-6.1-terra', 'gpt-6.1-sol']);
  assert.ok(r.config.modelSpecs.list.every(spec => spec.description === accountRestrictedMessage));
  assert.equal(r.config.interface.modelSelect, false);
  assert.ok(r.approvedProfile.modelSpecs.list.length === 3);
  assert.ok(r.approvedProfile.modelSpecs.list.every(x => x.preset.useResponsesApi && x.preset.endpoint === 'openAI'));
  assert.deepEqual(r.approvedProfile.endpoints.openAI.models, ['gpt-6-luna', 'gpt-6.1-terra', 'gpt-6.1-sol']);
  assert.ok(!JSON.stringify(r.approvedProfile).includes(key));
  assert.ok(!JSON.stringify(r.config).includes(key));
  assert.ok(!JSON.stringify(r.config).includes('FamilyMock'));
});

test('native candidate menu and branding cannot grant any default account model permission', () => {
  for (const key of ['', 'synthetic-unit-only-not-a-provider-key']) {
    const r = buildConfig({ OPENAI_API_KEY: key, OPENAI_CHAT_MODELS: 'gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol' });
    assert.deepEqual(r.config.endpoints.openAI.models, []);
    assert.equal(r.config.modelSpecs.enforce, true);
    assert.equal(r.config.modelSpecs.list.length, 3);
    assert.equal(r.config.interface.modelSelect, false);
    assert.equal(r.config.interface.presets, false);
    assert.equal(r.config.interface.parameters, false);
    for (const scope of [r.config, r.approvedProfile]) {
      assert.equal(scope.interface.customWelcome, brandTitle);
      assert.equal(scope.interface.landingHeading, 'greeting');
    }
    for (const spec of [...r.config.modelSpecs.list, ...r.approvedProfile.modelSpecs.list]) {
      assert.equal(spec.iconURL, '/logo-lines-mark.png');
      assert.equal(spec.preset.iconURL, '/logo-lines-mark.png');
      assert.equal(spec.showOnLanding, false);
      assert.equal(spec.showIconInMenu, true);
      assert.equal(spec.showIconInHeader, true);
    }
  }
});

test('the three requested model names remain accurate, default to Luna, and preserve existing spec identities', () => {
  const { selectedModels } = require('./configure-models.cjs');
  const r = buildConfig({ OPENAI_CHAT_MODELS: selectedModels.join(',') });
  const menu = r.config.modelSpecs.list;
  assert.deepEqual(menu.map(spec => spec.label), ['GPT-6 Luna', 'GPT-6.1 Terra', 'GPT-6.1 Sol']);
  assert.deepEqual(menu.filter(spec => spec.default).map(spec => spec.preset.model), ['gpt-6-luna']);
  assert.equal(menu.find(spec => spec.preset.model === 'gpt-6-luna').name, 'family-gpt-1');
  assert.equal(menu.find(spec => spec.preset.model === 'gpt-6.1-sol').name, 'family-gpt-2');
  assert.ok(!JSON.stringify(menu).includes('gpt-6.1-luna'));
  assert.deepEqual(r.config.endpoints.openAI.models, []);
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
