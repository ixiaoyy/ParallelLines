/** Process-local binding -> generation-epoch registry; never enumerates another session's jobs.
 * The native manager remains responsible for provider cancellation. This adapter does not
 * reproduce /chat/abort's beforePublish persistence or provide a multi-process registry.
 */
const identifier = value => typeof value === 'string' && value.length > 0 && value.length <= 1024;
const epoch = value => Number.isSafeInteger(value) && value > 0;
const activeStatuses = new Set(['running', 'requires_action']);
const controlRoutes = new Set(['abort', 'resume', 'steer', 'queued-turns', 'stream', 'status', 'active']);
const cancellation = reason => ['REQUEST_ABORTED', 'WATCH_STOPPED'].includes(reason?.code);

function userId(user) {
  const value = user?.id ?? user?._id;
  if (identifier(value)) return value;
  if (value && typeof value.toHexString === 'function') {
    const hex = value.toHexString();
    if (identifier(hex)) return hex;
  }
  return undefined;
}

function isChatStart(req) {
  if (req?.method !== 'POST') return false;
  const raw = req.originalUrl ?? req.url;
  if (typeof raw !== 'string') return false;
  const rawPath = raw.split('?', 1)[0];
  let path;
  try { path = decodeURIComponent(rawPath); } catch { return false; }
  if (/%(?:2f|5c)/i.test(rawPath) || /[%\\\0]/.test(path)) return false;
  const match = /^\/api\/agents\/chat\/([^/%\\]+)\/?$/i.exec(path);
  return Boolean(match && !controlRoutes.has(match[1].toLowerCase()));
}

export function createJobTracker({ guard, manager, pollIntervalMs = 200 } = {}) {
  if (typeof guard?.watch !== 'function' || typeof manager?.getJob !== 'function' ||
      typeof manager?.abortJob !== 'function' || !Number.isFinite(pollIntervalMs) || pollIntervalMs < 1) {
    throw new TypeError('Invalid job-tracker dependencies');
  }
  const byBinding = new Map();
  const byEpoch = new Map();
  // Terminal replay proof has no token, controller or lease, and is independently bounded.
  const proofs = new Map();
  const proofBindings = new Map();
  const wrappedResponses = new WeakSet();
  const wrappedStatusResponses = new WeakSet();
  let closed = false;

  function sameJob(entry, job) {
    return job?.createdAt === entry.createdAt && job.metadata?.userId === entry.userId &&
      (job.metadata?.tenantId ?? undefined) === entry.tenantId;
  }
  function matches(entry, job) {
    return sameJob(entry, job) && activeStatuses.has(job.status);
  }
  function forgetProof(key) {
    const proof = proofs.get(key);
    if (!proof) return;
    proofs.delete(key);
    const binding = proofBindings.get(proof.bindingId);
    binding?.delete(key);
    if (binding?.size === 0) proofBindings.delete(proof.bindingId);
  }
  function rememberProof(entry) {
    if (proofs.size >= 1000) forgetProof(proofs.keys().next().value);
    const proof = Object.freeze({ key: entry.key, streamId: entry.streamId, createdAt: entry.createdAt,
      bindingId: entry.bindingId, userId: entry.userId, tenantId: entry.tenantId });
    proofs.set(proof.key, proof);
    let binding = proofBindings.get(proof.bindingId);
    if (!binding) { binding = new Map(); proofBindings.set(proof.bindingId, binding); }
    binding.set(proof.key, proof);
  }

  function retire(entry, { keepProof = false } = {}) {
    if (!entry.active) return false;
    entry.active = false;
    clearTimeout(entry.timer);
    entry.lease?.signal?.removeEventListener?.('abort', entry.onAbort);
    entry.controller.abort();
    if (typeof entry.lease?.stop === 'function') entry.lease.stop();
    if (byEpoch.get(entry.key) === entry) byEpoch.delete(entry.key);
    const binding = byBinding.get(entry.bindingId);
    binding?.delete(entry.key);
    if (binding?.size === 0) byBinding.delete(entry.bindingId);
    if (!keepProof) forgetProof(entry.key);
    return true;
  }

  async function abortMatching(entry) {
    if (closed) return;
    const current = await manager.getJob(entry.streamId);
    if (closed || !matches(entry, current)) return;
    await manager.abortJob(entry.streamId, {
      expectedCreatedAt: entry.createdAt,
      awaitProviderDrain: true,
    });
  }

  function failed(entry, reason) {
    if (!retire(entry) || closed || cancellation(reason)) return;
    for (const proof of proofBindings.get(entry.bindingId)?.values() ?? []) forgetProof(proof.key);
    // Deliberately hide native/provider errors and never turn them into response contents.
    void abortMatching(entry).catch(() => {});
  }

  async function poll(entry) {
    if (!entry.active || closed) return;
    try {
      const current = await manager.getJob(entry.streamId);
      if (!entry.active || closed) return;
      if (!matches(entry, current)) { retire(entry, { keepProof: sameJob(entry, current) }); return; }
      entry.timer = setTimeout(() => { void poll(entry); }, pollIntervalMs);
      entry.timer.unref?.();
    } catch (error) {
      // An unreadable registry cannot justify keeping the last successful authority lease.
      failed(entry, error);
    }
  }

  async function start(entry, idToken, expectedUser) {
    try {
      const current = await manager.getJob(entry.streamId);
      if (!entry.active || closed) return;
      if (!matches(entry, current)) { retire(entry, { keepProof: sameJob(entry, current) }); return; }
      const lease = await guard.watch({ idToken, expectedUser, signal: entry.controller.signal });
      if (!entry.active || closed) { lease.stop(); return; }
      entry.lease = lease;
      if (!lease?.signal || typeof lease.signal.addEventListener !== 'function' || typeof lease.stop !== 'function' ||
          lease.context?.bindingId !== entry.bindingId || lease.context?.subject !== expectedUser.openidId ||
          lease.context?.issuer !== expectedUser.openidIssuer) {
        throw new Error('Invalid generation liveness lease');
      }
      entry.onAbort = () => failed(entry, lease.signal.reason);
      lease.signal.addEventListener('abort', entry.onAbort, { once: true });
      if (lease.signal.aborted) { entry.onAbort(); return; }
      entry.timer = setTimeout(() => { void poll(entry); }, pollIntervalMs);
      entry.timer.unref?.();
    } catch (error) {
      failed(entry, error);
    }
  }

  function capture(req, res, { idToken, expectedUser, context } = {}) {
    const id = userId(expectedUser);
    const tenantId = expectedUser?.tenantId ?? undefined;
    if (closed || !isChatStart(req) || typeof res?.json !== 'function' || wrappedResponses.has(res)) return false;
    if (!id || !identifier(context?.bindingId) || typeof idToken !== 'string' || idToken.length === 0 || idToken.length > 65536 ||
        (tenantId !== undefined && !identifier(tenantId))) throw new TypeError('Missing verified generation identity');
    const original = res.json;
    wrappedResponses.add(res);
    res.json = function captureGenerationResponse(...args) {
      const result = Reflect.apply(original, this, args);
      const body = args[0];
      const status = this.statusCode ?? 200;
      if (!closed && status >= 200 && status < 300 && body && typeof body === 'object' && !Array.isArray(body) &&
          identifier(body.streamId) && epoch(body.generationCreatedAt)) {
        const key = JSON.stringify([body.streamId, body.generationCreatedAt]);
        if (!proofs.has(key) && !byEpoch.has(key)) {
          const entry = { key, streamId: body.streamId, createdAt: body.generationCreatedAt,
            bindingId: context.bindingId, userId: id, tenantId, active: true, controller: new AbortController() };
          byEpoch.set(key, entry);
          rememberProof(entry);
          let binding = byBinding.get(entry.bindingId);
          if (!binding) { binding = new Map(); byBinding.set(entry.bindingId, binding); }
          binding.set(key, entry);
          // This owns its signal. Request/res finish, close or abort cannot end a paid job's lease.
          void start(entry, idToken, expectedUser);
        }
      }
      return result;
    };
    return true;
  }

  /** Reconnects may use only this process's original binding/owner/epoch proof.
   * Returns false only for unrelated routes; status's no-job branch is response-fenced too.
   * No body IDs, user-wide lookup, decoded path alias or missing-registry fallback is used.
   */
  async function authorizeAttachment(req, { context, expectedUser, res = req?.res } = {}) {
    if (req?.method !== 'GET') return false;
    const raw = req.originalUrl ?? req.url;
    if (typeof raw !== 'string') return false;
    const question = raw.indexOf('?');
    const path = question < 0 ? raw : raw.slice(0, question);
    const prefix = /^\/api\/agents\/chat\/(?:stream|status)(?:\/|$)/i;
    const denied = () => {
      const error = new Error('Generation attachment denied');
      error.code = 'GENERATION_ATTACHMENT_DENIED';
      error.status = error.statusCode = 403;
      return error;
    };
    // Express routing is case-insensitive by default. Never normalize an encoded locator
    // into a registry key, including an encoded static route component.
    if (path.includes('%')) {
      let decoded;
      try { decoded = decodeURIComponent(path); } catch { decoded = ''; }
      if (prefix.test(path) || prefix.test(decoded)) throw denied();
    }
    const route = /^\/api\/agents\/chat\/(stream|status)\/([^/%\\]+)\/?$/i.exec(path);
    if (!route) {
      if (prefix.test(path)) throw denied();
      return false;
    }
    const kind = route[1].toLowerCase();
    const streamId = route[2];
    const id = userId(expectedUser);
    const tenantId = expectedUser?.tenantId ?? undefined;
    if (closed || !identifier(streamId) || !id || !identifier(context?.bindingId) ||
        expectedUser?.provider !== 'openid' || context.subject !== expectedUser.openidId ||
        context.issuer !== expectedUser.openidIssuer) throw denied();
    const versions = new URLSearchParams(question < 0 ? '' : raw.slice(question + 1)).getAll('generationCreatedAt');
    let requestedEpoch;
    if (versions.length > 1 || (versions.length === 1 && (!/^[1-9]\d*$/.test(versions[0]) || !epoch(Number(versions[0]))))) {
      throw denied();
    }
    if (versions.length === 1) requestedEpoch = Number(versions[0]);

    const proof = () => [...(proofBindings.get(context.bindingId)?.values() ?? [])].filter(entry =>
      entry.streamId === streamId && entry.userId === id && entry.tenantId === tenantId &&
      (requestedEpoch === undefined || entry.createdAt === requestedEpoch));
    const protectStatus = proven => {
      if (kind !== 'status') return;
      if (!res || typeof res.json !== 'function') throw denied();
      if (wrappedStatusResponses.has(res)) return;
      wrappedStatusResponses.add(res);
      const original = res.json;
      res.json = function fencedStatusJson(...args) {
        const body = args[0];
        const hasJobContent = body && typeof body === 'object' &&
          (body.active === true || body.streamId != null || body.createdAt != null ||
           body.generationCreatedAt != null || body.aggregatedContent != null || body.resumeState != null ||
           (Array.isArray(body.unrecoveredSteers) && body.unrecoveredSteers.length > 0));
        if (hasJobContent && (!proven || closed || proofs.get(proven.key) !== proven ||
            body.streamId !== proven.streamId || body.createdAt !== proven.createdAt)) {
          this.statusCode = 403;
          return Reflect.apply(original, this, [{ message: 'Generation attachment denied', code: 'GENERATION_ATTACHMENT_DENIED' }]);
        }
        return Reflect.apply(original, this, args);
      };
    };
    // A stream without local proof must not even look up an arbitrary native job.
    if (kind === 'stream' && proof().length === 0) throw denied();
    let current;
    try { current = await manager.getJob(streamId); } catch { throw denied(); }
    if (closed) throw denied();
    for (const existing of proofs.values()) {
      if (existing.streamId === streamId && !sameJob(existing, current)) forgetProof(existing.key);
    }
    if (!current) {
      if (kind === 'status') { protectStatus(undefined); return true; }
      throw denied();
    }
    const entry = proof().find(candidate => sameJob(candidate, current) && proofs.get(candidate.key) === candidate);
    if (!entry) throw denied();
    if (kind === 'stream' && requestedEpoch === undefined) {
      const fencedUrl = value => {
        const delimiter = value.indexOf('?');
        const params = new URLSearchParams(delimiter < 0 ? '' : value.slice(delimiter + 1));
        params.set('generationCreatedAt', String(entry.createdAt));
        return `${delimiter < 0 ? value : value.slice(0, delimiter)}?${params}`;
      };
      req.url = fencedUrl(typeof req.url === 'string' ? req.url : raw);
      req.originalUrl = fencedUrl(raw);
    }
    protectStatus(entry);
    return true;
  }

  function close() {
    if (closed) return;
    closed = true;
    for (const entry of byEpoch.values()) retire(entry);
    byEpoch.clear();
    byBinding.clear();
    proofs.clear();
    proofBindings.clear();
  }

  return Object.freeze({ capture, authorizeAttachment, close });
}
