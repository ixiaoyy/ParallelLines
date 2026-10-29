'use strict';

const controlRoutes = new Set(['abort', 'resume', 'steer', 'queued-turns', 'stream', 'status', 'active']);

function generationEndpoint(req) {
  if (req.method !== 'POST') return null;
  const path = String(req.originalUrl ?? req.url ?? '').split('?', 1)[0];
  // These URLs have no encoded segments. Reject ambiguous input rather than normalize it.
  if (/[%\\\0]/.test(path) || path.includes('//')) {
    return /^\/api\/agents\/chat(?:\/|$)/i.test(path) ? '!invalid' : null;
  }
  const match = /^\/api\/agents\/chat\/([^/]+)\/?$/i.exec(path);
  return match && !controlRoutes.has(match[1].toLowerCase()) ? match[1] : null;
}

function serverKeyConfigured(env) {
  const value = typeof env.OPENAI_API_KEY === 'string' ? env.OPENAI_API_KEY.trim() : '';
  return Boolean(value) && !/^(user_provided|replace.*|change.*|your[_ -].*|<.*>)$/i.test(value);
}

function reject(res, status, error, message) {
  res.status(status).json({ error, message });
  return false;
}

/**
 * Called only AFTER native bearer authentication plus the live Main-session guard.
 * getConfig must strictly resolve the current native user's effective profile (no fallback).
 * Displayed model specs do not grant access: only the resolved endpoint allowlist does.
 */
function createModelAccess({ env = process.env, getConfig }) {
  if (typeof getConfig !== 'function') throw new TypeError('Missing effective config resolver');
  return async function authorizeModel(req, res) {
    const endpoint = generationEndpoint(req);
    if (!endpoint) return true;
    if (endpoint.toLowerCase() !== 'openai' || req.body?.endpoint !== 'openAI' ||
        (req.body.endpointType != null && req.body.endpointType !== 'openAI')) {
      return reject(res, 403, 'gpt_provider_not_enabled', '此聊天入口仅支持已授权的 GPT 模型。');
    }
    if (!serverKeyConfigured(env)) {
      return reject(res, 503, 'gpt_server_not_enabled', 'GPT 暂未启用，请联系管理员加载服务器配置。');
    }
    let config;
    try { config = await getConfig(req.user); }
    catch { return reject(res, 503, 'gpt_config_unavailable', '暂时无法读取模型权限，请稍后重试。'); }
    const allowed = config?.endpoints?.openAI?.models;
    if (!Array.isArray(allowed) || allowed.length === 0) {
      return reject(res, 403, 'gpt_account_not_enabled', '本账号尚未开通 GPT，请联系管理员设置模型权限和额度。');
    }
    const specs = config?.modelSpecs;
    // This deployment uses enforced native specs. Never guess a model from caller data.
    const spec = specs?.enforce === true && typeof req.body?.spec === 'string' &&
      Array.isArray(specs.list) && specs.list.find(item => item.name === req.body.spec);
    const model = spec?.preset?.model;
    if (!spec || spec.preset?.endpoint !== 'openAI' ||
        (spec.preset.endpointType != null && spec.preset.endpointType !== 'openAI') ||
        typeof model !== 'string' || !allowed.includes(model)) {
      return reject(res, 403, 'gpt_model_not_allowed', '所选模型未获授权，请选择已开通的模型。');
    }
    // Reuse the strictly resolved profile downstream; native chatConfigMiddleware
    // skips reloading an existing req.config. Native quota/model checks still run.
    req.config = config;
    return true;
  };
}

module.exports = { createModelAccess, generationEndpoint, serverKeyConfigured };
