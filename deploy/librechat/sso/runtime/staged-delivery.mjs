/** LOCAL CANDIDATE. Stage one refresh response; no cookies/body leave before proof. */
const retired = error => error?.code === 'OPENID_REFRESH_OWNERSHIP_LOST';
function statusFor(error) {
  if ([401, 403].includes(error?.status)) return error.status;
  if ([401, 403].includes(error?.statusCode)) return error.statusCode;
  if (retired(error)) return 401;
  return 503; // Unknown source/return shapes never become authorization or false logout.
}
const unavailable = () => Object.assign(new Error('Refresh delivery unavailable'), { status: 503 });

/**
 * Wrap the native createOpenIDResponseDelivery FACTORY, not the controller. A plain
 * async res.send wrapper is unsafe: it would move proof after the native final lease
 * assertion. Here send() is captured first, then native sendAuthorized performs its
 * real final assertion immediately before the synchronous commit.
 */
export function createStagedRefreshDelivery() {
  const stages = new WeakMap();
  function install(req, res, { verify, forget = () => {} }) {
    if (stages.has(res) || res.headersSent || typeof verify !== 'function') throw unavailable();
    const original = Object.fromEntries(['send', 'setHeader', 'getHeader', 'removeHeader', 'end', 'write', 'writeHead']
      .filter(name => typeof res[name] === 'function').map(name => [name, res[name]]));
    const beforeCookies = original.getHeader.call(res, 'set-cookie');
    let cookies = beforeCookies, mode = 'waiting', captured, sent = false;
    const restore = () => {
      for (const [name, fn] of Object.entries(original)) res[name] = fn;
      stages.delete(res); forget(req);
    };
    res.once?.('finish', restore); res.once?.('close', restore);
    res.setHeader = function (name, val) {
      if (String(name).toLowerCase() === 'set-cookie' && mode !== 'committing') {
        if (mode !== 'rejecting') cookies = Array.isArray(val) ? [...val] : val;
        return this;
      }
      return original.setHeader.call(this, name, val);
    };
    res.getHeader = function (name) {
      return String(name).toLowerCase() === 'set-cookie' && mode !== 'committing' ? cookies : original.getHeader.call(this, name);
    };
    res.removeHeader = function (name) {
      if (String(name).toLowerCase() === 'set-cookie' && mode !== 'committing') { if (mode !== 'rejecting') cookies = undefined; return; }
      return original.removeHeader.call(this, name);
    };
    function fail(error) {
      if (sent || res.writableEnded || res.destroyed) return res;
      mode = 'rejecting'; cookies = beforeCookies; captured = undefined;
      if (res.headersSent) { res.destroy(); return res; }
      if (beforeCookies === undefined) original.removeHeader.call(res, 'set-cookie');
      else original.setHeader.call(res, 'set-cookie', beforeCookies);
      // Discard success representation headers as well as success credentials.
      for (const name of ['content-length', 'content-encoding', 'etag', 'location']) original.removeHeader.call(res, name);
      const status = statusFor(error); res.statusCode = status;
      if (status === 503) original.setHeader.call(res, 'retry-after', '1');
      sent = true;
      return original.send.call(res, { error: [401, 403].includes(status) ? 'sso_session_required' : 'sso_temporarily_unavailable' });
    }
    res.send = function (body) {
      if (mode === 'capturing') {
        if (captured || this.headersSent) throw unavailable();
        if (!(this.statusCode >= 200 && this.statusCode < 300) || !body || typeof body !== 'object' || Array.isArray(body)) {
          throw Object.assign(unavailable(), { status: [401, 403].includes(this.statusCode) ? this.statusCode : 503 });
        }
        // Match Express res.json's wire boundary before proof: ObjectId/toJSON,
        // Date and application JSON settings must run exactly once. Proof sees
        // the parsed wire shape, never a prototype-stripped clone of native data.
        const replacer = this.app?.get?.('json replacer');
        const spaces = this.app?.get?.('json spaces');
        let wire = JSON.stringify(body, replacer, spaces);
        if (typeof wire !== 'string') throw unavailable();
        if (this.app?.get?.('json escape')) {
          wire = wire.replace(/[<>&]/g, character => ({ '<': '\\u003c', '>': '\\u003e', '&': '\\u0026' })[character]);
        }
        captured = { body: JSON.parse(wire), wire, status: this.statusCode };
        return this;
      }
      if (mode === 'committing' || mode === 'rejecting') return original.send.call(this, body);
      return fail(Object.assign(unavailable(), { status: [401, 403].includes(this.statusCode) ? this.statusCode : 503 }));
    };
    for (const name of ['end', 'write', 'writeHead']) {
      if (!original[name]) continue;
      res[name] = function (...args) {
        if (mode === 'committing' || mode === 'rejecting') return original[name].apply(this, args);
        // Unexpected unverified write/redirect is rejected, never published.
        fail(Object.assign(unavailable(), { status: [401, 403].includes(this.statusCode) ? this.statusCode : 503 }));
        return name === 'write' ? false : this;
      };
    }
    const stage = {
      async prepare(send) {
        if (mode !== 'waiting' || sent) throw unavailable();
        mode = 'capturing';
        const result = send();
        if (result?.then || !captured) throw unavailable(); // Native send closure must stay synchronous.
        mode = 'verifying';
        await verify(req, captured.body);
      },
      commit() {
        if (mode !== 'verifying' || !captured || sent || res.headersSent || res.closed || res.destroyed || res.writableEnded) throw unavailable();
        mode = 'committing'; sent = true;
        if (cookies === undefined) original.removeHeader.call(res, 'set-cookie');
        else original.setHeader.call(res, 'set-cookie', cookies);
        res.statusCode = captured.status;
        if (!original.getHeader.call(res, 'content-type')) original.setHeader.call(res, 'Content-Type', 'application/json');
        // Send the SAME JSON text as a string, so Express must not run replacer or
        // toJSON again. The actual write remains synchronous under the native lease.
        return original.send.call(res, captured.wire);
      },
      fail,
    };
    stages.set(res, stage);
    return stage;
  }
  function wrapFactory(nativeCreate) {
    return function createWithStagedDelivery(deps) {
      const nativeWithDelivery = nativeCreate(deps);
      return async function withStagedDelivery(input, operation) {
        const stage = stages.get(input.res);
        if (!stage) return nativeWithDelivery(input, operation);
        try {
          return await nativeWithDelivery(input, nativeSendAuthorized => operation(async send => {
            await stage.prepare(send);
            return nativeSendAuthorized(() => stage.commit());
          }));
        } catch (error) { return stage.fail(error); }
      };
    };
  }
  return Object.freeze({ install, wrapFactory });
}
