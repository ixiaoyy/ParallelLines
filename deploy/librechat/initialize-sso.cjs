'use strict';
// Approved server-local bootstrap only. Never prints, replaces, or exports a secret value.
const fs = require('node:fs');
const path = require('node:path');
const { randomBytes, generateKeyPairSync, createPrivateKey, createHash } = require('node:crypto');
const MATERIALS = ['CHAT_SSO_BRIDGE_SECRET', 'CHAT_OIDC_CLIENT_SECRET', 'CHAT_OIDC_COOKIE_KEYS', 'OPENID_SESSION_SECRET'];
const FILE_KEY = 'CHAT_OIDC_SIGNING_JWKS_FILE';
const FILE_REFERENCE = '/secrets/signing.jwks.json';
const FINISH_URL = 'https://pingxingxian.space/auth/oidc/interaction/finish';
function fail(code) { const error = new Error(code); error.code = code; throw error; }
function statFile(filename, required = false) {
  if (!fs.existsSync(filename)) { if (required) fail('required_env_missing'); return { filename, text: null, stat: null }; }
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink()) fail('unsafe_existing_file');
  return { filename, text: fs.readFileSync(filename, 'utf8'), stat };
}
function values(snapshot) {
  const result = new Map();
  for (const line of (snapshot.text || '').split(/\r?\n/)) {
    const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (!match || ![...MATERIALS, FILE_KEY, 'CHAT_SSO_ENABLED', 'CHAT_SSO_LOGIN_POLICY', 'CHAT_SSO_FINISH_URL', 'CHAT_SSO_CLIENT_ID'].includes(match[1])) continue;
    if (result.has(match[1])) fail('duplicate_target_env_key');
    let value = match[2].trim();
    try {
      if (value.startsWith("'")) { const quoted = /^'([^']*)'\s*(?:#.*)?$/.exec(value); if (!quoted) fail('invalid_target_env_syntax'); value = quoted[1]; }
      else if (value.startsWith('"')) { const quoted = /^"((?:\\.|[^"\\])*)"\s*(?:#.*)?$/.exec(value); if (!quoted) fail('invalid_target_env_syntax'); value = JSON.parse('"' + quoted[1] + '"'); }
      else value = value.replace(/\s+#.*$/, '').trim();
    } catch { fail('invalid_target_env_syntax'); }
    result.set(match[1], value);
  }
  return result;
}
function canonical(name, value) {
  if (!value) return '';
  if (name === 'CHAT_OIDC_COOKIE_KEYS') {
    let parsed; try { parsed = JSON.parse(value); } catch { fail('invalid_existing_cookie_keys'); }
    if (!Array.isArray(parsed) || !parsed.length || parsed.some(key => typeof key !== 'string' || key.length < 32 || /[\r\n\0]/.test(key))) fail('invalid_existing_cookie_keys');
    return JSON.stringify(parsed);
  }
  if (value.length < 32 || value.length > 8192 || /[\r\n\0]|\$\{/.test(value)) fail('invalid_existing_service_secret');
  return value;
}
function setValue(text, name, value) {
  const current = values({ text }).get(name);
  if (current === value) return text;
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const encoded = /^[A-Za-z0-9_:/.,=-]+$/.test(value) ? value : "'" + value.replace(/'/g, "'\\''") + "'";
  // Generated values never contain quotes. Existing opaque values containing a quote are not reserialized.
  if (value.includes("'")) fail('unsupported_existing_secret_encoding');
  const pattern = new RegExp('^(\\s*(?:export\\s+)?' + name + '\\s*=)[^\\r\\n]*', 'm');
  if (pattern.test(text)) return text.replace(pattern, name + '=' + encoded);
  return text + (text && !text.endsWith('\n') ? eol : '') + name + '=' + encoded + eol;
}
function assertUnchanged(snapshot) {
  const exists = fs.existsSync(snapshot.filename);
  if (snapshot.text === null ? exists : !exists || fs.readFileSync(snapshot.filename, 'utf8') !== snapshot.text) fail('env_changed_during_initialization');
}
function secureDirectory(directory, uid, gid) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const stat = fs.lstatSync(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) fail('unsafe_runtime_directory');
  fs.chmodSync(directory, 0o700);
  if (process.platform !== 'win32' && uid !== undefined) fs.chownSync(directory, uid, gid);
}
function atomicSave(snapshot, text) {
  assertUnchanged(snapshot);
  if (text === snapshot.text) { fs.chmodSync(snapshot.filename, 0o600); return; }
  const temporary = snapshot.filename + '.sso-' + randomBytes(8).toString('hex') + '.tmp';
  const fd = fs.openSync(temporary, 'wx', 0o600);
  try { fs.writeFileSync(fd, text); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  try {
    if (process.platform !== 'win32' && snapshot.stat) fs.chownSync(temporary, snapshot.stat.uid, snapshot.stat.gid);
    assertUnchanged(snapshot); fs.renameSync(temporary, snapshot.filename); fs.chmodSync(snapshot.filename, 0o600);
  } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
}

/** The only mutable targets are deploy/chat-sso and four named Main .env fields. */
function initialize({ repoRoot = path.resolve(__dirname, '../..'), uid = 1000, gid = 1000 } = {}) {
  const root = fs.realpathSync(path.resolve(repoRoot));
  const runtime = path.join(root, 'deploy', 'chat-sso');
  const base = statFile(path.join(root, 'deploy', 'librechat', '.env'), true);
  const main = statFile(path.join(root, 'apps', 'api', '.env'), true);
  const sso = statFile(path.join(runtime, '.env'));
  const dictionaries = [values(sso), values(base), values(main)];
  if (dictionaries[2].get('CHAT_SSO_CLIENT_ID') && dictionaries[2].get('CHAT_SSO_CLIENT_ID') !== 'parallellines-chat') fail('conflicting_main_client_id');
  if (dictionaries[0].get(FILE_KEY) && dictionaries[0].get(FILE_KEY) !== FILE_REFERENCE) fail('conflicting_signing_file_reference');
  const selected = new Map(); const generatedGroups = []; const reusedGroups = [];
  for (const name of MATERIALS) {
    const configured = dictionaries.map(dictionary => dictionary.get(name) || '').filter(Boolean);
    const canonicalValues = configured.map(value => canonical(name, value));
    if (new Set(canonicalValues).size > 1) fail('conflicting_existing_' + name);
    if (configured.length) { selected.set(name, configured[0]); reusedGroups.push(name); }
    else {
      selected.set(name, name === 'CHAT_OIDC_COOKIE_KEYS' ? JSON.stringify([randomBytes(32).toString('hex')]) : randomBytes(32).toString('hex'));
      generatedGroups.push(name);
    }
  }
  const signingPath = path.join(runtime, 'secrets', 'signing.jwks.json');
  const existingSigning = statFile(signingPath);
  let signingText = existingSigning.text;
  if (signingText !== null) {
    try {
      const jwks = JSON.parse(signingText);
      if (!Array.isArray(jwks.keys) || !jwks.keys.length || jwks.keys.some(key => key.kty !== 'RSA' || key.alg !== 'RS256' || !key.d || !key.kid || createPrivateKey({ key, format: 'jwk' }).asymmetricKeyDetails.modulusLength < 2048)) fail('invalid_existing_signing_key');
    } catch { fail('invalid_existing_signing_key'); }
    reusedGroups.push('RS256_SIGNING_JWKS');
  } else {
    const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 3072 });
    const publicJwk = publicKey.export({ format: 'jwk' });
    const kid = 'pl-chat-' + createHash('sha256').update(publicJwk.n).digest('base64url').slice(0, 24);
    signingText = JSON.stringify({ keys: [{ ...privateKey.export({ format: 'jwk' }), alg: 'RS256', use: 'sig', kid }] }, null, 2) + '\n';
    generatedGroups.push('RS256_SIGNING_JWKS');
  }
  let ssoText = sso.text || '# Server-local OIDC trust materials. Do not commit or print.\n';
  for (const [name, value] of selected) ssoText = setValue(ssoText, name, value);
  ssoText = setValue(ssoText, FILE_KEY, FILE_REFERENCE);
  let mainText = main.text;
  for (const [name, value] of Object.entries({ CHAT_SSO_ENABLED: 'true', CHAT_SSO_LOGIN_POLICY: 'active_main', CHAT_SSO_FINISH_URL: FINISH_URL, CHAT_SSO_BRIDGE_SECRET: selected.get('CHAT_SSO_BRIDGE_SECRET') })) mainText = setValue(mainText, name, value);
  // Validate every existing value before creating any material or editing an environment.
  for (const snapshot of [base, main, sso, existingSigning]) assertUnchanged(snapshot);
  secureDirectory(runtime);
  const lock = path.join(runtime, '.initialize.lock');
  let lockFd;
  try { lockFd = fs.openSync(lock, 'wx', 0o600); } catch { fail('initialization_lock_exists'); }
  try {
    for (const snapshot of [base, main, sso, existingSigning]) assertUnchanged(snapshot);
    secureDirectory(path.join(runtime, 'data'), uid, gid);
    secureDirectory(path.join(runtime, 'secrets'), uid, gid);
    if (existingSigning.text === null) fs.writeFileSync(signingPath, signingText, { flag: 'wx', mode: 0o600 });
    fs.chmodSync(signingPath, 0o600);
    if (process.platform !== 'win32') fs.chownSync(signingPath, uid, gid);
    atomicSave(sso, ssoText);
    atomicSave(main, mainText);
    assertUnchanged(base); // Base LibreChat/OpenAI environment is preserved byte for byte.
    return { initialized: true, generatedGroups, reusedGroups, materialGroups: 5,
      mainPolicy: 'active_main', finishUrl: FINISH_URL, baseLibreChatEnvChanged: false, modelKeyChanged: false };
  } finally { fs.closeSync(lockFd); fs.unlinkSync(lock); }
}
module.exports = { initialize };
if (require.main === module) {
  try {
    if (process.argv.length > 3) fail('usage_initialize_sso_optional_repository_root');
    console.log(JSON.stringify(initialize({ repoRoot: process.argv[2] || path.resolve(__dirname, '../..') })));
  } catch (error) {
    console.error('SSO initialization refused: ' + (error.code || 'initialization_failed'));
    process.exitCode = 1;
  }
}
