'use strict';
const { unavailable } = require('./errors.cjs');

/** Only the fixed, already validated public JWKS endpoint may be fetched. */
function createJwksFetch({ url, fetchImpl = globalThis.fetch }) {
  const trusted = new URL(url);
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(trusted.hostname);
  if (trusted.username || trusted.password || trusted.search || trusted.hash ||
      (trusted.protocol !== 'https:' && !(loopback && trusted.protocol === 'http:'))) {
    throw new TypeError('Invalid JWKS endpoint');
  }
  const expected = trusted.href;
  if (typeof fetchImpl !== 'function') throw new TypeError('Missing JWKS fetch');
  return async function fetchTrustedJwks(input, options = {}) {
    let response;
    try {
      if (new URL(input).href !== expected || options.signal?.aborted) throw unavailable();
      response = await fetchImpl(input, { ...options, method: 'GET', redirect: 'error', credentials: 'omit' });
      if (response.status !== 200) {
        response.body?.cancel().catch(() => {});
        throw unavailable();
      }
      // Check only the trusted endpoint's response framing. JOSE still parses the
      // same original bytes, validates JWK structure and performs JWT verification.
      const clone = response.clone();
      const reader = clone.body?.getReader();
      if (!reader) throw unavailable();
      const cancel = () => { reader.cancel().catch(() => {}); };
      options.signal?.addEventListener('abort', cancel, { once: true });
      const chunks = []; let size = 0; let detached;
      try {
        while (true) {
          if (options.signal?.aborted) throw unavailable();
          const { value, done } = await reader.read();
          if (options.signal?.aborted) throw unavailable();
          if (done) break;
          if (!(value instanceof Uint8Array) || (size += value.byteLength) > 262144) {
            cancel(); throw unavailable();
          }
          chunks.push(value);
        }
        const bytes = new Uint8Array(size); let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        const body = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
        if (!body || typeof body !== 'object' || !Array.isArray(body.keys)) throw unavailable();
        // After the bounded read, network abort must not turn JOSE's subsequent
        // JSON read into an unclassified generic error. No reserialization occurs.
        detached = new Response(bytes, { status: 200, headers: response.headers });
      } finally {
        options.signal?.removeEventListener('abort', cancel);
        reader.releaseLock();
      }
      response.body?.cancel().catch(() => {});
      return detached;
    } catch {
      response?.body?.cancel().catch(() => {});
      throw unavailable();
    }
  };
}

module.exports = { createJwksFetch };
