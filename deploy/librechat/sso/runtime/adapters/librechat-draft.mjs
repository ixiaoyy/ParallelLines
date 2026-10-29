/**
 * LOCAL DRAFT ONLY. This module is not mounted in LibreChat or in production.
 * Keep native authentication, bans, tenant checks, and image ownership/ACL checks.
 * No environment reads, token decoding, credentials, or logging live here.
 */

function requireFunction(value, name) {
  if (typeof value !== 'function') throw new TypeError(`${name} is required`);
}

function requireGuard(guard) {
  requireFunction(guard?.authorize, 'guard.authorize');
  requireFunction(guard?.watch, 'guard.watch');
}

function stopLease(lease, reason) {
  try { if (typeof lease?.stop === 'function') lease.stop(reason); }
  catch { /* Cleanup must not expose errors or prevent a fail-closed response. */ }
}

function nonemptyString(value) {
  return typeof value === 'string' && value.length > 0 && value.trim() === value;
}

function userIdOf(user) {
  const value = user?._id ?? user?.id;
  if (value == null) throw new Error('unauthorized');
  const id = typeof value === 'string' ? value : value.toString?.();
  if (!nonemptyString(id) || id === '[object Object]') throw new Error('unauthorized');
  return id;
}

function expectedUserOf(user) {
  if (user?.provider !== 'openid' || !nonemptyString(user.openidId) ||
      !nonemptyString(user.openidIssuer)) throw new Error('unauthorized');
  return Object.freeze({
    _id: userIdOf(user),
    provider: 'openid',
    openidId: user.openidId,
    openidIssuer: user.openidIssuer,
  });
}

function deny(res) {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) {
    // Closing an SSE/socket response does not itself cancel a provider generation.
    res.destroy?.();
    return;
  }
  res.status(401).json({ error: 'unauthorized' });
}

function requestLifetime(req, res) {
  const controller = new AbortController();
  let cleanupLease = () => {};
  let disposed = false;
  const dispose = (reason = 'request_complete') => {
    if (disposed) return;
    disposed = true;
    req.removeListener?.('aborted', onAborted);
    res.removeListener?.('finish', onFinished);
    res.removeListener?.('close', onClosed);
    cleanupLease();
    controller.abort(reason);
  };
  const onAborted = () => controller.abort('request_aborted');
  const onFinished = () => dispose();
  const onClosed = () => {
    if (!res.writableEnded) controller.abort('request_closed');
    dispose('request_closed');
  };
  req.once?.('aborted', onAborted);
  res.once?.('finish', onFinished);
  res.once?.('close', onClosed);
  if (req.aborted || res.destroyed || res.writableEnded) controller.abort('request_closed');
  return {
    signal: controller.signal,
    dispose,
    bindCleanup(fn) {
      if (disposed) fn();
      else cleanupLease = fn;
    },
  };
}

/** The injected guard must validate the token and required expectedUser itself. */
async function attachLiveSession({ guard, req, res, idToken, expectedUser, lifetime, watch, onCancel }) {
  const input = { idToken, expectedUser, signal: lifetime.signal };
  let lease;
  let context;
  try {
    if (watch) {
      lease = await guard.watch(input);
      if (!lease || !lease.signal || typeof lease.signal.addEventListener !== 'function' ||
          typeof lease.stop !== 'function' || !lease.closed ||
          typeof lease.closed.then !== 'function') throw new Error('unauthorized');
      context = lease.context;
    } else {
      context = await guard.authorize(input);
    }
    if (context?.subject !== expectedUser.openidId || context?.issuer !== expectedUser.openidIssuer ||
        lifetime.signal.aborted || lease?.signal.aborted) throw new Error('unauthorized');

    const signal = lease?.signal ?? lifetime.signal;
    const onRevoked = () => {
      // This callback is only a hook. An integration must cancel the real job here.
      if (onCancel) {
        try {
          Promise.resolve(onCancel({ req, context, signal, code: 'sso_session_closed' })).catch(() => {});
        } catch { /* Return no sensitive error details. */ }
      }
      deny(res);
    };
    if (lease) {
      signal.addEventListener('abort', onRevoked, { once: true });
      lifetime.bindCleanup(() => {
        signal.removeEventListener('abort', onRevoked);
        stopLease(lease, 'request_complete');
      });
    }
    req.ssoLiveSession = Object.freeze({ context, signal });
  } catch {
    stopLease(lease, 'authorization_failed');
    throw new Error('unauthorized');
  }
}

/** Mount AFTER native requireJwtAuth; native local-JWT fallback is rejected. */
export function createLibreChatBearerSessionMiddleware({ guard, watch = true, onCancel } = {}) {
  requireGuard(guard);
  if (onCancel != null) requireFunction(onCancel, 'onCancel');
  return async function libreChatBearerSessionDraft(req, res, next) {
    const lifetime = requestLifetime(req, res);
    try {
      if (req.authStrategy !== 'openidJwt') throw new Error('unauthorized');
      const expectedUser = expectedUserOf(req.user);
      const authorization = req.headers?.authorization;
      const match = typeof authorization === 'string' && /^Bearer ([^\s]+)$/i.exec(authorization);
      if (!match) throw new Error('unauthorized');
      // Never substitute req.user.federatedTokens or a server-stored bearer token.
      await attachLiveSession({ guard, req, res, idToken: match[1], expectedUser, lifetime, watch, onCancel });
    } catch {
      lifetime.dispose('authorization_failed');
      deny(res);
      return;
    }
    next();
  };
}

/**
 * Additive private-image guard. It does NOT perform or replace native owner/ACL checks.
 * Use createLibreChatPrivateImageChain to make the required ordering explicit.
 */
export function createLibreChatPrivateImageSessionMiddleware({
  guard,
  parseCookies,
  getValidOpenIDReuseCredential,
  jwtRefreshSecret,
  findSession,
  getUserById,
  watch = true,
  onCancel,
} = {}) {
  requireGuard(guard);
  requireFunction(parseCookies, 'parseCookies');
  requireFunction(getValidOpenIDReuseCredential, 'getValidOpenIDReuseCredential');
  requireFunction(findSession, 'findSession');
  requireFunction(getUserById, 'getUserById');
  if (!nonemptyString(jwtRefreshSecret)) throw new TypeError('jwtRefreshSecret is required');
  if (onCancel != null) requireFunction(onCancel, 'onCancel');
  return async function libreChatPrivateImageSessionDraft(req, res, next) {
    const lifetime = requestLifetime(req, res);
    try {
      // The pinned image adapter parses the raw header itself. Do not trust an
      // unrelated/global req.cookies object as proof of this request's cookies.
      const cookieHeader = req.headers?.cookie;
      if (!nonemptyString(cookieHeader)) throw new Error('unauthorized');
      const cookies = parseCookies(cookieHeader);
      const refreshToken = cookies?.refreshToken;
      if (cookies?.token_provider !== 'openid' || !nonemptyString(refreshToken) ||
          !nonemptyString(cookies?.openid_user_id)) {
        throw new Error('unauthorized');
      }
      const credential = await getValidOpenIDReuseCredential(cookies, jwtRefreshSecret, refreshToken);
      if (!nonemptyString(credential?.userId)) throw new Error('unauthorized');
      const [durableSession, user] = await Promise.all([
        findSession({ userId: credential.userId, refreshToken }),
        getUserById(credential.userId),
      ]);
      if (!durableSession || userIdOf({ _id: durableSession.user }) !== credential.userId) {
        throw new Error('unauthorized');
      }
      const expiresAt = new Date(durableSession.expiration).getTime();
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error('unauthorized');
      const expectedUser = expectedUserOf(user);
      if (expectedUser._id !== credential.userId ||
          (req.user && userIdOf(req.user) !== expectedUser._id)) throw new Error('unauthorized');
      // Mongo's native Session is NOT the Express session and has no openidTokens.
      // Missing/stale Express token state must fail closed, never fall back to DB tokens.
      const tokens = req.session?.openidTokens;
      if (!tokens || tokens.appUserId !== expectedUser._id ||
          tokens.openidSubject !== expectedUser.openidId ||
          tokens.openidIssuer !== expectedUser.openidIssuer ||
          tokens.refreshToken !== refreshToken || !nonemptyString(tokens.idToken)) {
        throw new Error('unauthorized');
      }
      await attachLiveSession({ guard, req, res, idToken: tokens.idToken, expectedUser, lifetime, watch, onCancel });
    } catch {
      lifetime.dispose('authorization_failed');
      deny(res);
      return;
    }
    next();
  };
}

/** Spread this chain before the existing static sender; owner/ACL runs first. */
export function createLibreChatPrivateImageChain({ nativeImageOwnerAcl, ...dependencies } = {}) {
  requireFunction(nativeImageOwnerAcl, 'nativeImageOwnerAcl');
  return Object.freeze([
    nativeImageOwnerAcl,
    createLibreChatPrivateImageSessionMiddleware(dependencies),
  ]);
}
