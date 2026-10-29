import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';

// Reuse installed dependencies; all accounts/API calls/DOM are synthetic.
const require = createRequire(new URL('../../package.json', import.meta.url));
const vue = require('vue');
const ts = require('typescript');
const { parse, compileScript, compileTemplate } = require('vue/compiler-sfc');
const web = new URL('../../src/', import.meta.url);
const origin = 'https://pingxingxian.space';
const bridge = '/auth/chat?interaction_id=abcdefgh12345678';
const passthrough = { setup: (_, { slots }) => () => vue.h('span', slots.default?.()) };
const empty = { render: () => null };

function evaluate(code, imports) {
  const output = ts.transpileModule(code.replaceAll('import.meta.env.DEV', 'false'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  });
  assert.equal(output.diagnostics?.length ?? 0, 0);
  const module = { exports: {} };
  new Function('require', 'module', 'exports', output.outputText)(name => {
    if (name === 'vue') return vue;
    if (name in imports) return imports[name];
    throw new Error(`Unexpected module: ${name}`);
  }, module, module.exports);
  return module.exports;
}

const helper = evaluate(readFileSync(new URL('shared/router/authReturn.ts', web), 'utf8'), {});
function component(path, imports) {
  const source = readFileSync(new URL(path, web), 'utf8');
  const { descriptor, errors } = parse(source, { filename: path });
  assert.deepEqual(errors, []);
  const script = descriptor.scriptSetup ? compileScript(descriptor, { id: path }) : null;
  const result = script ? evaluate(script.content, imports).default : {};
  const template = compileTemplate({ source: descriptor.template.content, filename: path, id: path,
    compilerOptions: { bindingMetadata: script?.bindings } });
  assert.deepEqual(template.errors, []);
  result.render = evaluate(template.code, imports).render;
  return result;
}
const loading = component('pages/auth/ChatEntryLoading.vue', {});
const renderer = vue.createRenderer({
  createElement: tag => ({ tag, tagName: tag.toUpperCase(), children: [], props: {}, style: {},
    addEventListener() {}, removeEventListener() {} }),
  createText: text => ({ text }), createComment: text => ({ comment: text }),
  setText: (node, text) => { node.text = text; },
  setElementText: (node, text) => { node.text = text; node.children = []; },
  parentNode: node => node.parent, nextSibling: () => null,
  patchProp: (node, key, _previous, value) => { node.props[key] = value; },
  insert(node, parent, anchor = null) {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1);
    node.parent = parent;
    const index = parent.children.indexOf(anchor);
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node);
  },
  remove(node) { const list = node.parent?.children; if (list) list.splice(list.indexOf(node), 1); },
});
function texts(node) { return [node.text ?? '', ...(node.children ?? []).map(texts)].join(''); }
function count(node, tag) { return Number(node.tag === tag) + (node.children ?? []).reduce((sum, child) => sum + count(child, tag), 0); }
const settle = async () => { await Promise.resolve(); await vue.nextTick(); await Promise.resolve(); await vue.nextTick(); };

function harness({ token = true, user = null, fetching = false, redirect = bridge, reauth, apiFailure } = {}) {
  const route = vue.reactive({ name: 'auth', path: '/auth', query: { redirect, ...(reauth ? { reauth } : {}) } });
  const current = { data: vue.ref(user), isFetching: vue.ref(fetching), error: vue.ref(null) };
  const navigation = [], apiCalls = [], assigned = [];
  const router = { replace: async target => { navigation.push(['replace', target]); },
    push: async target => { navigation.push(['push', target]); } };
  const mutation = { isPending: vue.ref(false), mutateAsync: async () => ({}) };
  const queries = new Proxy({ useCurrentUser: () => current, useOAuthProviders: () => ({ data: vue.ref({ providers: [] }) }) },
    { get: (target, key) => target[key] ?? (() => mutation) });
  const imports = {
    'vue-router': { useRoute: () => route, useRouter: () => router },
    '@ant-design/icons-vue': new Proxy({}, { get: () => empty }),
    '@/features/auth/queries': queries,
    '@/shared/api/client': { ApiError: class extends Error {}, hasAccessToken: () => token,
      isAuthenticationError: failure => failure?.status === 401,
      apiPost: async (path, body) => { apiCalls.push({ path, body }); throw apiFailure ?? new Error('test should stub approval'); } },
    '@/shared/router/authReturn': helper,
    '@/shared/assets/staticAssets': { staticAssetUrl: value => value, cssUrl: value => `url(${value})` },
    '@/shared/ui/Button.vue': { default: passthrough },
    './ChatEntryLoading.vue': { default: loading },
  };
  globalThis.window = { location: { origin, assign: target => assigned.push(target) }, setTimeout, clearTimeout };
  const mount = path => {
    const root = { children: [] };
    const app = renderer.createApp(component(path, imports));
    app.component('RouterLink', passthrough);
    const vm = app.mount(root);
    return { root, state: vm.$.setupState, unmount: () => app.unmount() };
  };
  return { route, current, mutation, navigation, apiCalls, assigned, mount,
    setToken: value => { token = value; } };
}

test('only canonical validated interaction paths count as a chat continuation', () => {
  assert.equal(helper.isChatSsoContinuation(bridge, origin), true);
  for (const path of ['/forum', '//evil.test/auth/chat?interaction_id=abcdefgh', '/auth/chat',
    '/auth/chat?interaction_id=short', bridge + '&interaction_id=abcdefgh', '/auth/chat/../forum']) {
    assert.equal(helper.isChatSsoContinuation(path, origin), false);
  }
});

test('existing main session and pending current-user fetch show only chat loading', async () => {
  const h = harness({ fetching: true });
  const view = h.mount('pages/auth/AuthPage.vue');
  assert.equal(count(view.root, 'form'), 0);
  assert.match(texts(view.root), /正在进入聊天/);
  h.current.data.value = { id: 'synthetic-101' };
  await settle();
  assert.deepEqual(h.navigation, [['replace', bridge]]);
  assert.deepEqual(h.assigned, []);
  assert.equal(count(view.root, 'form'), 0);
  view.unmount();
});

test('stale cached user without a main token stays on the main login form', async () => {
  const h = harness({ token: false, user: { id: 'synthetic-101' } });
  const view = h.mount('pages/auth/AuthPage.vue');
  await settle();
  assert.ok(count(view.root, 'form') > 0);
  assert.deepEqual(h.navigation, []);
  view.unmount();
});

test('current-user fetch failure restores auth form and never navigates to forum', async () => {
  const h = harness({ fetching: true });
  const view = h.mount('pages/auth/AuthPage.vue');
  h.current.error.value = new Error('synthetic offline');
  h.current.isFetching.value = false;
  await settle();
  assert.ok(count(view.root, 'form') > 0);
  assert.deepEqual(h.navigation, []);
  view.unmount();
});

test('login success and current-user watcher coalesce into one bridge replacement', async () => {
  const h = harness({ token: false });
  const view = h.mount('pages/auth/AuthPage.vue');
  view.state.account = 'synthetic'; view.state.loginPassword = 'synthetic-test-only';
  h.mutation.mutateAsync = async () => { h.setToken(true); h.current.data.value = { id: 'synthetic-101' }; await vue.nextTick(); return {}; };
  await view.state.submitLogin(); await settle();
  assert.deepEqual(h.navigation, [['replace', bridge]]);
  assert.deepEqual(h.assigned, []);
  view.unmount();
});

test('ordinary forum login still navigates to its main-site destination', async () => {
  const h = harness({ token: false, redirect: '/forum?sort=new' });
  const view = h.mount('pages/auth/AuthPage.vue');
  assert.ok(count(view.root, 'form') > 0);
  await view.state.finishAuthReturn();
  assert.deepEqual(h.navigation, [['push', '/forum?sort=new']]);
  view.unmount();
});

test('bridge without a main token replaces directly to one main auth entry', async () => {
  const h = harness({ token: false });
  h.route.query = { interaction_id: 'abcdefgh12345678' };
  const view = h.mount('pages/auth/ChatSsoPage.vue');
  await settle();
  assert.deepEqual(h.navigation, [['replace', { name: 'auth', query: { redirect: bridge } }]]);
  assert.deepEqual(h.apiCalls, []);
  assert.match(texts(view.root), /正在进入聊天/);
  view.unmount();
});

test('bridge 401 uses explicit reauthentication and stale cached user cannot auto-resume', async () => {
  const h = harness({ apiFailure: { status: 401 } });
  h.route.query = { interaction_id: 'abcdefgh12345678' };
  const view = h.mount('pages/auth/ChatSsoPage.vue');
  await settle();
  assert.deepEqual(h.apiCalls, [{ path: '/auth/chat-sso/approve', body: { interaction_id: 'abcdefgh12345678' } }]);
  assert.deepEqual(h.navigation, [['replace', { name: 'auth', query: { redirect: bridge, reauth: 'chat' } }]]);
  view.unmount();
  const resumed = harness({ user: { id: 'synthetic-101' }, fetching: true, reauth: 'chat' });
  const auth = resumed.mount('pages/auth/AuthPage.vue');
  await settle();
  assert.ok(count(auth.root, 'form') > 0);
  assert.deepEqual(resumed.navigation, []);
  auth.unmount();
});

test('main shell is excluded only for validated chat login; bridge metadata excludes shell', () => {
  const app = readFileSync(new URL('app/App.vue', web), 'utf8');
  assert.ok(app.includes('!isAdminLogin && !isChatLogin'));
  assert.ok(app.includes('isChatSsoContinuation(redirect, window.location.origin)'));
  const router = readFileSync(new URL('app/router.ts', web), 'utf8');
  const route = router.slice(router.indexOf('name: "chat-sso"'), router.indexOf('name: "auth"'));
  assert.ok(route.includes('forumShell: false'));
});
