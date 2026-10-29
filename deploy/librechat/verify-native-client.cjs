'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');

const SOURCE_COMMIT = '8d3da9bbb220a0a96be9330a2e1cbd385fb786d5';
const SHA256 = /^[a-f0-9]{64}$/;
const LIMITS = Object.freeze({ files: 10000, fileBytes: 128 * 1024 * 1024, totalBytes: 512 * 1024 * 1024 });
const fail = code => { throw new Error(code); };
const safeAssetPath = name => typeof name === 'string' && name.length > 0 && name.length <= 2048 &&
  name.split('/').every(segment => /^[A-Za-z0-9._~-]+$/.test(segment) && segment !== '.' && segment !== '..');
const hashFile = filename => createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
function regularFile(filename, limit) {
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 || stat.size > limit) fail('native_client_invalid_file');
  return stat;
}

/** Validate the exact readonly client tree before any LibreChat process is started. */
function verifyNativeClient({ clientRoot, manifestPath, patchPath }) {
  regularFile(manifestPath, 8 * 1024 * 1024);
  regularFile(patchPath, 16 * 1024 * 1024);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest) ||
      Object.keys(manifest).sort().join(',') !== 'files,patchSha256,schemaVersion,sourceCommit' ||
      manifest.schemaVersion !== 1 || manifest.sourceCommit !== SOURCE_COMMIT ||
      !SHA256.test(manifest.patchSha256 || '') || manifest.patchSha256 !== hashFile(patchPath) ||
      !manifest.files || typeof manifest.files !== 'object' || Array.isArray(manifest.files)) fail('native_client_invalid_manifest');
  const names = Object.keys(manifest.files).sort();
  if (!names.length || names.length > LIMITS.files || !Object.hasOwn(manifest.files, 'index.html') ||
      names.some(name => !safeAssetPath(name) || !SHA256.test(manifest.files[name]))) fail('native_client_invalid_asset_list');
  const seen = [];
  let totalBytes = 0;
  function walk(relative = '') {
    const target = path.join(clientRoot, ...relative.split('/').filter(Boolean));
    const stat = fs.lstatSync(target);
    if (stat.isSymbolicLink()) fail('native_client_link_rejected');
    if (stat.isDirectory()) {
      for (const name of fs.readdirSync(target)) {
        const next = relative ? relative + '/' + name : name;
        if (!safeAssetPath(next)) fail('native_client_invalid_asset_path');
        walk(next);
      }
      return;
    }
    if (!relative || !stat.isFile() || stat.nlink !== 1 || stat.size > LIMITS.fileBytes) fail('native_client_invalid_file');
    totalBytes += stat.size;
    seen.push(relative);
    if (totalBytes > LIMITS.totalBytes || seen.length > LIMITS.files || !Object.hasOwn(manifest.files, relative) ||
        hashFile(target) !== manifest.files[relative]) fail('native_client_asset_mismatch');
  }
  if (!fs.lstatSync(clientRoot).isDirectory()) fail('native_client_invalid_root');
  walk();
  if (JSON.stringify(seen.sort()) !== JSON.stringify(names)) fail('native_client_asset_set_mismatch');
  return Object.freeze({ sourceCommit: SOURCE_COMMIT, patchSha256: manifest.patchSha256, files: names.length, totalBytes });
}
module.exports = { verifyNativeClient, safeAssetPath, SOURCE_COMMIT, LIMITS };
