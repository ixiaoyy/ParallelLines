const base = require('./base-config.json');

const disabledMessage = 'GPT 尚未启用，请联系管理员在服务器完成密钥和模型配置。';

/** Build secret-free LibreChat config; credentials remain only in the server process environment. */
function buildConfig(env) {
  const rawKey = (env.OPENAI_API_KEY || '').trim();
  const keyConfigured = Boolean(rawKey) && !/^(user_provided|replace.*|change.*|your[_ -].*|<.*>)$/i.test(rawKey);
  const requestedModels = [...new Set((env.OPENAI_CHAT_MODELS || '').split(',').map(s => s.trim()).filter(Boolean))];
  const invalidModel = requestedModels.some(id => !/^gpt-[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/.test(id) || /^gpt-(image|audio|realtime|transcribe|live|oss)(-|$)/i.test(id));
  const enabled = keyConfigured && requestedModels.length > 0 && !invalidModel;
  const models = enabled ? requestedModels : [];
  const config = structuredClone(base);
  const grantedModels = {
    enforce: true,
    prioritize: true,
    list: models.map((model, index) => ({
      name: `family-gpt-${index + 1}`,
      label: model,
      default: index === 0,
      preset: { endpoint: 'openAI', model, useResponsesApi: true, maxContextTokens: 128000, max_tokens: 4096 }
    }))
  };
  // Configured provider is not an account grant. Every account starts with an empty catalog.
  config.interface.customWelcome = enabled ? '此账号尚未启用 GPT，请联系管理员确认适用条件并授权。' : disabledMessage;
  config.interface.modelSelect = false;
  config.endpoints = { openAI: { models: [], titleConvo: false, activityLabel: false, reasoningLabel: false } };
  config.modelSpecs = { enforce: true, prioritize: true, list: [] };
  const approvedProfile = {
    interface: { modelSelect: enabled, customWelcome: enabled ? 'GPT 文字与图片聊天：仅在适用的支持地区使用。' : disabledMessage },
    endpoints: { openAI: { models } },
    modelSpecs: grantedModels
  };
  return {
    config, approvedProfile, enabled, models,
    reason: enabled ? null : !keyConfigured ? 'missing_server_key' : invalidModel ? 'invalid_gpt_model_id' : 'missing_model_selection',
    // A placeholder, personal-key sentinel or absent model must never authorize a model request.
    runtimeKey: enabled ? rawKey : '',
    footer: enabled ? 'GPT 按账号授权 · 仅在适用的支持地区使用' : disabledMessage
  };
}
module.exports = { buildConfig, disabledMessage };
