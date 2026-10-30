'use strict';
// Run after applying native-session.patch and npm ci in the pinned LibreChat checkout.
// LIBRECHAT_SOURCE_ROOT overrides the source root; otherwise use the current directory.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const native = path.resolve(process.env.LIBRECHAT_SOURCE_ROOT || process.cwd());
const requireNative = Module.createRequire(path.join(native, 'package.json'));
const ts = requireNative('typescript');
const { createStaticHandler } = requireNative('react-router-dom');
const sourcePath = path.join(native, 'client/src/routes/ssoLoginLoader.ts');
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, strict: true },
  reportDiagnostics: true,
});
assert.equal(compiled.diagnostics.length, 0, 'actual patched loader must transpile');
const filename = path.join(native, 'client/src/routes/__sso-basename-test.cjs');
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = Module._nodeModulePaths(path.dirname(filename));
loaded._compile(compiled.outputText, filename);

const previousDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
Object.defineProperty(globalThis, 'document', {
  configurable: true,
  value: Object.freeze({ querySelector(selector) {
    assert.equal(selector, 'meta[name="pl-sso-only"]');
    return Object.freeze({ content: 'true' });
  } }),
});
test.after(() => {
  if (previousDocument) Object.defineProperty(globalThis, 'document', previousDocument);
  else delete globalThis.document;
});

const cases = [
  ['', '/chat/oauth/openid?returnTo=%2Fchat%2F'],
  ['?redirect_to=%2Fc%2Foriginal', '/chat/oauth/openid?returnTo=%2Fchat%2Fc%2Foriginal'],
  ['?error=AUTH_FAILED', '/chat/login?redirect=false&error=AUTH_FAILED'],
  ['?redirect=false', '/chat/login?redirect=false&error=AUTH_FAILED'],
];
for (const basename of ['/chat', '/chat/']) {
  for (const [query, expected] of cases) {
    test(`production basename=${basename} query=${query || '(empty)'} has one chat prefix`, async () => {
      const handler = createStaticHandler([{ path: '/login', loader: loaded.exports.ssoLoginLoader }], { basename });
      const response = await handler.query(new Request('https://fixture.invalid/chat/login' + query));
      assert.ok(response instanceof Response, 'redirect must terminate real router resolution');
      assert.equal(response.status, 302);
      assert.equal(response.headers.get('X-Remix-Reload-Document'), 'true');
      assert.equal(response.headers.get('Location'), expected);
      assert.doesNotMatch(response.headers.get('Location'), /^\/chat\/chat\//);
    });
  }
}
