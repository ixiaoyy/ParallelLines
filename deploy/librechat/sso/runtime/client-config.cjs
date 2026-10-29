'use strict';

// Presentation only. Native server-side balance configuration and checks stay enabled.
function clientConfig(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) ||
      typeof payload.appTitle !== 'string') return payload;
  return { ...payload, balance: { ...payload.balance, enabled: false } };
}

function hideBalancePresentation(req, res, next) {
  const pathname = String(req.originalUrl ?? req.url ?? '').split('?', 1)[0].replace(/\/$/, '').toLowerCase();
  if (req.method !== 'GET' || pathname !== '/api/config') return next();
  const send = res.send;
  res.send = function sendClientConfig(payload) {
    return Reflect.apply(send, this, [clientConfig(payload)]);
  };
  return next();
}

module.exports = { clientConfig, hideBalancePresentation };
