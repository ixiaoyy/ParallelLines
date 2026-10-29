const base = require('./base-config.json');
const forumTheme = require('./sso/branding/forum-theme.json');

const brandTitle = '平行线 · AI 聊天';
const disabledMessage = 'GPT 暂未启用，等待管理员加载服务器配置并开通账号。';
const accountRestrictedMessage = '此账号尚未启用 GPT，请联系管理员确认适用条件并授权。';
const approvedMessage = 'GPT 文字与图片聊天：仅在适用的支持地区使用。';
const modelLabels = {
  'gpt-6-luna': 'GPT-6 Luna',
  'gpt-6.1-terra': 'GPT-6.1 Terra',
  'gpt-6.1-sol': 'GPT-6.1 Sol'
};
// Keep existing spec identities stable when a candidate is inserted in the menu.
const specNames = { 'gpt-6-luna': 'family-gpt-1', 'gpt-6.1-sol': 'family-gpt-2', 'gpt-6.1-terra': 'family-gpt-3' };

/** Native menu metadata is independent from the resolved per-user endpoint allowlist. */
function modelSpecs(models, description) {
  return {
    enforce: true,
    prioritize: true,
    list: models.map((model, index) => ({
      name: specNames[model] || `family-${model}`,
      label: modelLabels[model] || model,
      description,
      default: index === 0,
      iconURL: '/logo-lines-mark.png',
      showIconInMenu: true,
      showIconInHeader: true,
      showOnLanding: false,
      preset: { endpoint: 'openAI', model, iconURL: '/logo-lines-mark.png', useResponsesApi: true, maxContextTokens: 128000, max_tokens: 4096 }
    }))
  };
}

/** Build secret-free LibreChat config; credentials remain only in the server process environment. */
function buildConfig(env) {
  const rawKey = (env.OPENAI_API_KEY || '').trim();
  const keyConfigured = Boolean(rawKey) && !/^(user_provided|replace.*|change.*|your[_ -].*|<.*>)$/i.test(rawKey);
  const requestedModels = [...new Set((env.OPENAI_CHAT_MODELS || '').split(',').map(s => s.trim()).filter(Boolean))];
  const invalidModel = requestedModels.some(id => !/^gpt-[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/.test(id) || /^gpt-(image|audio|realtime|transcribe|live|oss)(-|$)/i.test(id));
  const selectedModels = invalidModel ? [] : requestedModels;
  const enabled = keyConfigured && selectedModels.length > 0;
  const models = enabled ? selectedModels : [];
  const config = structuredClone(base);
  config.interface.theme = structuredClone(forumTheme);
  const grantedModels = modelSpecs(models, enabled ? approvedMessage : disabledMessage);
  // Configured provider is not an account grant. Every account starts with an empty catalog.
  config.interface.customWelcome = brandTitle;
  config.interface.landingHeading = 'greeting';
  config.interface.modelSelect = false;
  config.interface.presets = false;
  config.interface.parameters = false;
  config.endpoints = { openAI: { models: [], titleConvo: false, activityLabel: false, reasoningLabel: false } };
  // The native selector renders nonempty specs even with modelSelect=false. These
  // candidates never populate endpoints.openAI.models or grant provider access.
  config.modelSpecs = modelSpecs(selectedModels, enabled ? accountRestrictedMessage : disabledMessage);
  const approvedProfile = {
    interface: { modelSelect: false, presets: false, parameters: false, landingHeading: 'greeting', customWelcome: brandTitle },
    endpoints: { openAI: { models } },
    modelSpecs: grantedModels
  };
  return {
    config, approvedProfile, enabled, models, selectedModels,
    reason: enabled ? null : !keyConfigured ? 'missing_server_key' : invalidModel ? 'invalid_gpt_model_id' : 'missing_model_selection',
    // A placeholder, personal-key sentinel or absent model must never authorize a model request.
    runtimeKey: enabled ? rawKey : '',
    footer: enabled ? 'GPT 按账号授权 · 仅在适用的支持地区使用' : disabledMessage
  };
}
module.exports = { buildConfig, brandTitle, disabledMessage, accountRestrictedMessage, modelLabels };
