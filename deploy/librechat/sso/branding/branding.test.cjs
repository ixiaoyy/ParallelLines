'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { applyShellBranding, installBrandLogoRoute, BRAND_TITLE, LOGO_URL } = require('./shell-branding.cjs');
const theme = require('./forum-theme.json');

test('replaces only shell branding, preserves resource links and chat payload', () => {
  const html = '<html><head><base href="/chat/"><title>LibreChat</title>' +
    '<link rel="icon" type="image/png" href="assets/favicon-32x32.png">' +
    '<link href="assets/favicon-16x16.png" rel="shortcut icon">' +
    "<link rel='apple-touch-icon' href='old.png'>" +
    '<link rel="stylesheet" href="assets/index.css"><script src="assets/index.js"></script></head>' +
    '<body><div data-conversation-title="Personal title"></div></body></html>';
  const result = applyShellBranding(html);
  assert.match(result, new RegExp(`<title>${BRAND_TITLE}</title>`));
  assert.match(result, /rel="icon" type="image\/svg\+xml" href="\/favicon\.svg"/);
  assert.match(result, /rel="apple-touch-icon" href="\/logo-lines-mark\.png"/);
  assert.doesNotMatch(result, /favicon-32|favicon-16|old\.png|<title>LibreChat/);
  assert.match(result, /<base href="\/chat\/">/);
  assert.match(result, /<link rel="stylesheet" href="assets\/index.css">/);
  assert.match(result, /<script src="assets\/index.js"><\/script>/);
  assert.match(result, /Personal title/);
  assert.equal(applyShellBranding(result), result);
});

test('brand route has one fixed public path and redirect target', () => {
  let registered;
  installBrandLogoRoute({ get: (route, handler) => { registered = { route, handler }; } });
  assert.equal(registered.route, '/assets/logo.svg');
  const values = {};
  registered.handler({ query: { target: 'https://example.invalid/' } }, {
    set: (key, value) => { values[key] = value; },
    redirect: (code, target) => { values.code = code; values.target = target; },
  });
  assert.equal(values.code, 302);
  assert.equal(values.target, LOGO_URL);
  assert.equal(values['Cache-Control'], 'public, max-age=300');
});

test('theme reuses exact forum palette with valid opaque RGB triples', () => {
  assert.equal(theme.version, 1);
  const light = theme.modes.light.colors;
  assert.equal(light['rgb-button-primary'], '64 158 255');
  assert.equal(light['rgb-button-primary-hover'], '102 177 255');
  assert.equal(light['rgb-text-inverted'], '255 255 255');
  assert.equal(light['rgb-surface-canvas'], '248 250 252');
  assert.equal(light['rgb-text-primary'], '51 65 85');
  assert.equal(light['rgb-text-secondary'], '71 85 105');
  for (const mode of Object.values(theme.modes)) {
    for (const value of Object.values(mode.colors)) {
      assert.match(value, /^\d{1,3} \d{1,3} \d{1,3}$/);
      assert.ok(value.split(' ').every(channel => Number(channel) <= 255));
    }
  }
});

test('protected assets are referenced without creating replacement copies', () => {
  const files = fs.readdirSync(__dirname);
  assert.ok(!files.some(file => /\.(svg|png|jpg|webp)$/i.test(file)));
  const assets = path.resolve(__dirname, '../../../../apps/web/public');
  assert.ok(fs.existsSync(path.join(assets, 'logo-lines-mark.png')));
  assert.ok(fs.existsSync(path.join(assets, 'favicon.svg')));
});
