'use strict';
const native = require('../../sso-runtime/native/LogoutController.native.cjs');
const runtime = require('../../sso-runtime/runtime.cjs');
const landing = 'https://pingxingxian.space/auth';
async function logoutController(req, res) {
  try { await (await runtime.initialize()).revokeSession(req); }
  catch {
    return res.status(503).json({ error: 'sso_logout_unavailable' });
  }
  const send = res.send;
  res.send = function sendLogoutResult(body) {
    if (this.statusCode >= 200 && this.statusCode < 300 && body && typeof body === 'object' && !Array.isArray(body)) {
      body = { ...body, redirect: landing };
    }
    return Reflect.apply(send, this, [body]);
  };
  try { return await native.logoutController(req, res); }
  finally { res.send = send; }
}
module.exports = { ...native, logoutController };
