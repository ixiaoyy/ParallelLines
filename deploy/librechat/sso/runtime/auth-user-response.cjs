'use strict';

function identityError() {
  const error = new Error('Auth response identity is inconsistent');
  error.code = 'AUTH_RESPONSE_IDENTITY_MISMATCH';
  return error;
}

function canonicalDatabaseId(value) {
  let id;
  try {
    if (typeof value === 'string') id = value;
    else if (value && typeof value === 'object' && typeof value.toHexString === 'function') id = value.toHexString();
    else if (value && typeof value === 'object' && typeof value.toString === 'function') id = value.toString();
  } catch { throw identityError(); }
  if (typeof id !== 'string' || !id || id.length > 256 || /\s/.test(id) || id === '[object Object]') {
    throw identityError();
  }
  return id;
}

/** Preserve native sanitization; derive the required client ID only from its trusted DB _id. */
function createAuthUserResponseSanitizer(nativeSanitize) {
  if (typeof nativeSanitize !== 'function') throw new TypeError('Native auth sanitizer is required');
  return function sanitizeUserForAuthResponse(user) {
    const safeUser = nativeSanitize(user);
    if (!safeUser || typeof safeUser !== 'object' || Array.isArray(safeUser) ||
        !Object.prototype.hasOwnProperty.call(safeUser, '_id')) throw identityError();
    const id = canonicalDatabaseId(safeUser._id);
    if (Object.prototype.hasOwnProperty.call(safeUser, 'id') && safeUser.id !== id) throw identityError();
    return { ...safeUser, id };
  };
}

module.exports = { createAuthUserResponseSanitizer };
