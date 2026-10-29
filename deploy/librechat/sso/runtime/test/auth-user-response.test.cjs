'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { createRequire } = require('node:module');
const nativeRequire = process.env.LIBRECHAT_SOURCE_ROOT
  ? createRequire(path.join(process.env.LIBRECHAT_SOURCE_ROOT, 'api/package.json'))
  : require;
const api = nativeRequire('@librechat/api');
const mongoose = nativeRequire('mongoose');
const schemas = nativeRequire('@librechat/data-schemas');
const { createAuthUserResponseSanitizer } = require('../auth-user-response.cjs');
const sanitize = createAuthUserResponseSanitizer(api.sanitizeUserForAuthResponse);
const id = '000000000000000000000001';
const make = () => ({ _id: new mongoose.Types.ObjectId(id), provider: 'openid', openidId: 'fixture-sub',
  openidIssuer: 'https://fixture.invalid/oidc', name: 'Synthetic fixture', email: 'fixture@chat.invalid',
  password: 'synthetic-hidden', totpSecret: 'synthetic-hidden', backupCodes: ['synthetic-hidden'],
  federatedTokens: { access_token: 'synthetic-hidden' } });
const inconsistent = error => error?.code === 'AUTH_RESPONSE_IDENTITY_MISMATCH';

test('real native sanitizer leaves lean _id, helper supplies the exact client id', () => {
  const user = make();
  assert.equal(api.sanitizeUserForAuthResponse(user).id, undefined);
  const result = sanitize(user);
  assert.equal(result.id, id);
  assert.equal(result._id, user._id);
  assert.equal(user.id, undefined, 'raw database/cache object is unchanged');
  assert.equal(JSON.parse(JSON.stringify(result))._id, id);
});

test('real native Mongoose document survives native toObject semantics', () => {
  const models = schemas.createModels(mongoose);
  const user = new models.User(make());
  assert.equal(user.id, id, 'virtual getter exists only on the hydrated document');
  assert.equal(api.sanitizeUserForAuthResponse(user).id, undefined);
  assert.equal(sanitize(user).id, id);
  assert.equal(mongoose.connection.readyState, 0, 'no database connection for this pure test');
});

test('preserves all original safe fields including exact OpenID subject and issuer', () => {
  const user = make();
  const expected = api.sanitizeUserForAuthResponse(user);
  const actual = sanitize(user);
  const { id: actualId, ...rest } = actual;
  assert.equal(actualId, id);
  assert.deepEqual(rest, expected);
  assert.equal(actual.openidId, user.openidId);
  assert.equal(actual.openidIssuer, user.openidIssuer);
});

test('native credential stripping runs before ID completion', () => {
  const result = sanitize(make());
  for (const field of ['password', 'totpSecret', 'backupCodes', 'federatedTokens'])
    assert.equal(Object.hasOwn(result, field), false);
});

test('an existing matching client id remains accepted', () => {
  assert.equal(sanitize({ ...make(), id }).id, id);
});

test('mismatching or malformed existing id is rejected rather than overwritten', () => {
  for (const existing of ['different-user', '', null, undefined, 123, { toString: () => id }])
    assert.throws(() => sanitize({ ...make(), id: existing }), inconsistent);
});

test('absent or unrepresentable database id fails without disclosing conversion input', () => {
  for (const value of [undefined, null, {}, '', 'has space', { toString() { throw new Error('sensitive synthetic detail'); } }])
    assert.throws(() => sanitize({ ...make(), _id: value }), inconsistent);
  assert.throws(() => createAuthUserResponseSanitizer(() => ({ id }))({}), inconsistent);
});

test('native sanitizer is called once and remains the only field sanitizer', () => {
  const raw = make(); let calls = 0;
  const wrapped = createAuthUserResponseSanitizer(user => {
    assert.equal(user, raw); calls++; return api.sanitizeUserForAuthResponse(user);
  });
  assert.equal(wrapped(raw).id, id);
  assert.equal(calls, 1);
});
