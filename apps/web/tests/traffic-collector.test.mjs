import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/traffic-collector.v1.js', import.meta.url), 'utf8');
const endpoint = 'https://pingxingxian.space/api/v1/site/traffic';
const visitorId = '00000000-0000-4000-8000-000000000001';

// 浏览器状态、空闲任务、时钟及网络均为内存替身；不访问真实站点或数据库。
function browser(options = {}) {
  let now = Date.UTC(2026, 10, 17);
  let sequence = 1;
  let handle = 0;
  const timers = new Map();
  const idles = [];
  const requests = [];
  const beacons = [];
  const cookieWrites = [];
  const storageWrites = [];
  const originalCalls = [];
  const historyErrors = {};
  const cookies = new Map(Object.entries(options.cookies || {}));
  const storage = new Map(Object.entries(options.storage || {}));
  const location = new URL(options.url || 'https://pingxingxian.space/');

  function events(target) {
    const listeners = new Map();
    target.addEventListener = (name, callback, settings) => {
      const list = listeners.get(name) || [];
      list.push({ callback, once: settings?.once });
      listeners.set(name, list);
    };
    target.emit = (name, event = {}) => {
      for (const item of [...(listeners.get(name) || [])]) {
        if (item.once) listeners.set(name, listeners.get(name).filter(value => value !== item));
        item.callback(event);
      }
    };
    return target;
  }

  class Element {
    constructor(action, { disabled = false, button } = {}) {
      this.action = action;
      this.disabled = disabled;
      this.button = button;
    }
    closest(selector) {
      assert.equal(selector, '[data-traffic-action]');
      return this.button || (this.action ? this : null);
    }
    getAttribute(name) {
      assert.equal(name, 'data-traffic-action');
      return this.action;
    }
  }

  const document = events({
    currentScript: options.noScript ? null : { dataset: options.dataset || { site: 'games' } },
    readyState: options.loading ? 'loading' : 'complete',
    visibilityState: 'visible',
    referrer: options.referrer || '',
  });
  Object.defineProperty(document, 'cookie', {
    get() {
      if (options.cookieReadThrows) throw new Error('Cookie access denied');
      return [...cookies].map(([key, value]) => `${key}=${value}`).join('; ');
    },
    set(value) {
      cookieWrites.push(value);
      if (options.cookieWriteThrows) throw new Error('Cookie write denied');
      if (options.cookiesBlocked) return;
      const [pair] = value.split(';');
      const split = pair.indexOf('=');
      cookies.set(pair.slice(0, split), pair.slice(split + 1));
    },
  });

  const window = events({
    setTimeout(callback, delay) {
      const id = ++handle;
      timers.set(id, { callback, at: now + delay, delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    setInterval() { throw new Error('Polling is not allowed'); },
    ...(options.noIdle ? {} : {
      requestIdleCallback(callback, settings) { idles.push({ callback, settings }); },
    }),
  });
  const crypto = options.noCrypto ? undefined : {
    randomUUID() {
      return `00000000-0000-4000-8000-${String(sequence++).padStart(12, '0')}`;
    },
    getRandomValues(bytes) { bytes.fill(sequence++); return bytes; },
  };
  window.crypto = crypto;
  const navigator = { ...(options.navigator || {}) };
  if (options.beacon !== false) {
    navigator.sendBeacon = (url, body) => {
      beacons.push({ url, body });
      if (options.beaconThrows) throw new Error('Beacon denied');
      return options.beaconResult ?? true;
    };
  }
  const history = {};
  for (const name of ['pushState', 'replaceState']) {
    history[name] = function (...args) {
      originalCalls.push({ name, thisValue: this, args });
      if (historyErrors[name]) throw historyErrors[name];
      if (args[2] !== undefined) location.href = new URL(args[2], location.href).href;
      return `native:${name}`;
    };
  }
  const context = vm.createContext({
    window, document, navigator, location, history, Element, crypto,
    URL, URLSearchParams, Blob, AbortController, Uint8Array,
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : [now])); }
      static now() { return now; }
    },
    localStorage: {
      getItem(key) {
        if (options.storageBlocked) throw new Error('Storage denied');
        return storage.get(key) ?? null;
      },
      setItem(key, value) {
        if (options.storageBlocked) throw new Error('Storage denied');
        storageWrites.push({ key, value });
        storage.set(key, value);
      },
    },
    setTimeout: window.setTimeout,
    clearTimeout: window.clearTimeout,
    fetch(url, init) {
      requests.push({ url, init, body: JSON.parse(init.body) });
      return options.fetch ? options.fetch(url, init) : Promise.resolve({ ok: true, status: 204 });
    },
  });

  const settle = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); };
  const run = () => vm.runInContext(source, context, { filename: 'traffic-collector.v1.js' });
  const idle = async () => {
    for (const job of idles.splice(0)) job.callback();
    await settle();
  };
  const advance = async milliseconds => {
    const until = now + milliseconds;
    let count = 0;
    while (true) {
      const next = [...timers].filter(([, timer]) => timer.at <= until).sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      assert.ok(count++ < 1000, 'timer callbacks must be bounded');
      const [id, timer] = next;
      now = timer.at;
      timers.delete(id);
      timer.callback();
      await settle();
    }
    now = until;
    await settle();
  };
  const start = async () => { run(); await idle(); if (options.noIdle) await advance(1000); };
  const action = (event_name, path) => window.emit('pl:traffic', { detail: { event_name, path } });
  const navigate = async (path, name = 'pushState') => {
    const result = history[name]({}, 'private browser title', path);
    await idle();
    return result;
  };
  const sentEvents = () => requests.flatMap(request => request.body.events);
  return {
    run, idle, advance, start, action, navigate, settle, sentEvents,
    window, document, navigator, location, history, historyErrors, Element,
    requests, beacons, timers, idles, cookies, cookieWrites, storage, storageWrites, originalCalls,
  };
}

test('missing/invalid opt-in, unsupported hosts and unsafe endpoints stay inactive', async () => {
  for (const options of [
    { noScript: true }, { dataset: {} }, { dataset: { site: 'unknown' } },
    { dataset: { site: '__proto__' } }, { dataset: { site: 'toString' } },
    { url: 'https://evil.test/' },
    { url: 'https://chat.pingxingxian.space/', dataset: { site: 'games' } },
    { dataset: { site: 'games', endpoint: 'https://evil.test/traffic' } },
    { dataset: { websiteId: 'third-party' }, url: 'https://api.pingxingxian.space/' },
    { dataset: { site: 'games', allowLocal: 'true' }, url: 'http://localhost/' },
  ]) {
    const page = browser(options);
    await page.start();
    await page.advance(120000);
    assert.equal(page.requests.length, 0);
    assert.equal(page.beacons.length, 0);
    assert.equal(page.cookieWrites.length, 0);
  }
});

test('supported sites and native New API data-website-id use the fixed endpoint', async () => {
  for (const [site, host] of Object.entries({
    games: 'pingxingxian.space', forum: 'forum.pingxingxian.space', tools: 'tools.pingxingxian.space',
    chat: 'chat.pingxingxian.space', api: 'api.pingxingxian.space',
  })) {
    const page = browser({ url: `https://${host}/`, dataset: { site } });
    await page.start(); await page.advance(30000);
    assert.equal(page.requests[0].url, endpoint);
    assert.equal(page.sentEvents()[0].site_key, site);
  }
  const native = browser({ url: 'https://api.pingxingxian.space/', dataset: { websiteId: 'api' } });
  await native.start(); await native.advance(30000);
  assert.equal(native.sentEvents()[0].site_key, 'api');
  const local = browser({ url: 'http://localhost/', dataset: { site: 'games', allowLocal: 'true', endpoint: '/api/v1/site/traffic' } });
  await local.start(); await local.advance(30000);
  assert.equal(local.requests[0].url, 'http://localhost/api/v1/site/traffic');
  assert.equal(local.requests[0].body.identity_scope, 'site');
});

test('DNT, GPC, automation and explicit exclusion prevent identity and network writes', async () => {
  for (const options of [
    { navigator: { doNotTrack: '1' } }, { navigator: { msDoNotTrack: '1' } },
    { navigator: { globalPrivacyControl: true } }, { navigator: { webdriver: true } },
    { cookies: { px_traffic_exclude: '1' } },
  ]) {
    const page = browser(options);
    await page.start(); page.action('game_open', '/games/public-game'); await page.advance(30000);
    page.window.emit('pagehide');
    assert.equal(page.requests.length + page.beacons.length, 0);
    assert.equal(page.cookieWrites.length + page.storageWrites.length, 0);
  }
});

test('installation waits for load then idle, keeps a one-shot fallback, and does not duplicate', async () => {
  const page = browser({ loading: true });
  page.run(); page.run();
  assert.equal(page.idles.length, 0);
  assert.equal(page.cookieWrites.length, 0);
  page.window.emit('load'); page.window.emit('load');
  assert.equal(page.idles.length, 1);
  assert.equal(page.idles[0].settings.timeout, 2000);
  await page.idle();
  assert.equal(page.requests.length, 0);
  await page.advance(29999); assert.equal(page.requests.length, 0);
  await page.advance(1); assert.equal(page.requests.length, 1);
  const fallback = browser({ noIdle: true });
  fallback.run();
  await fallback.advance(999); assert.equal(fallback.cookieWrites.length, 0);
  await fallback.advance(1); assert.equal(fallback.cookieWrites.length, 1);
});

test('shared identity is random, non-authorizing, reusable and explicitly scoped', async () => {
  const existing = browser({ cookies: { px_traffic_id: visitorId, auth_token: 'never-send-this' } });
  await existing.start(); await existing.advance(30000);
  assert.equal(existing.requests[0].body.visitor_id, visitorId);
  assert.equal(existing.requests[0].body.identity_scope, 'shared');
  assert.equal(existing.cookieWrites.length, 0);
  assert.doesNotMatch(existing.requests[0].init.body, /never-send-this|auth_token/);
  const fresh = browser();
  await fresh.start(); await fresh.advance(30000);
  assert.match(fresh.cookieWrites[0], /Domain=pingxingxian\.space; Secure/);
  assert.match(fresh.cookieWrites[0], /Max-Age=31536000; SameSite=Lax/);
  assert.equal(fresh.requests[0].body.identity_scope, 'shared');
});

test('blocked cookie writes fall back to site storage, then ephemeral identity', async () => {
  for (const cookieOptions of [{ cookiesBlocked: true }, { cookieWriteThrows: true }]) {
    const site = browser({ ...cookieOptions, storage: { 'parallellines.traffic_id.v1': visitorId } });
    await site.start(); await site.advance(30000);
    assert.equal(site.requests[0].body.visitor_id, visitorId);
    assert.equal(site.requests[0].body.identity_scope, 'site');
    const fresh = browser(cookieOptions);
    await fresh.start(); await fresh.advance(30000);
    assert.equal(fresh.storageWrites.length, 1);
    assert.equal(fresh.requests[0].body.identity_scope, 'site');
    const ephemeral = browser({ ...cookieOptions, storageBlocked: true });
    await ephemeral.start(); await ephemeral.advance(30000);
    assert.equal(ephemeral.requests[0].body.identity_scope, 'ephemeral');
  }
});

test('unreadable exclusion cookies conservatively skip collection without throwing', async () => {
  const page = browser({ cookieReadThrows: true, storageBlocked: true });
  await page.start(); await page.advance(30000);
  assert.equal(page.requests.length + page.beacons.length, 0);
  assert.equal(page.cookieWrites.length + page.storageWrites.length, 0);
});

test('query/hash/chat IDs and full referrer URLs never enter page-view payloads', async () => {
  const page = browser({
    url: 'https://chat.pingxingxian.space/c/private-chat-123?email=alice%40example.test#private-hash',
    dataset: { site: 'chat' },
    referrer: 'https://user:password@outside.test/private/path?secret=referrer#fragment',
  });
  await page.start(); await page.advance(30000);
  const event = page.sentEvents()[0];
  assert.equal(event.path, '/c/:chat');
  assert.equal(event.referrer, 'https://outside.test');
  assert.doesNotMatch(page.requests[0].init.body, /private-chat|alice|private-hash|password|private\/path|secret|fragment/);
});

test('SPA duplicate paths ignore query/hash while distinct chat IDs retain canonical PVs', async () => {
  const page = browser({ url: 'https://chat.pingxingxian.space/c/first', dataset: { site: 'chat' } });
  await page.start();
  await page.navigate('/c/first?q=private#hash');
  await page.navigate('/c/first', 'replaceState');
  await page.navigate('/c/second');
  page.window.emit('popstate'); await page.idle();
  await page.advance(30000);
  assert.deepEqual(page.sentEvents().map(event => event.path), ['/c/:chat', '/c/:chat']);
  assert.equal(new Set(page.sentEvents().map(event => event.event_id)).size, 2);
});

test('private routes and invalid public paths do not create identities or events', async () => {
  for (const path of ['/admin/analytics', '/auth/callback', '/account/profile', '/messages/private', '/workspace/private', '/oauth/callback', '/reset-password/token', '/new-topic', '/me', '/bad%20path']) {
    const page = browser({ url: `https://pingxingxian.space${path}` });
    await page.start(); page.action('game_open', '/games/public-game'); await page.advance(30000);
    assert.equal(page.requests.length + page.beacons.length, 0, path);
    assert.equal(page.cookieWrites.length, 0, path);
  }
});

test('forum and API dynamic details are reduced to canonical public dimensions', async () => {
  for (const [site, host, path, expected] of [
    ['forum', 'forum.pingxingxian.space', '/topics/private-topic', '/topics/:topic'],
    ['forum', 'forum.pingxingxian.space', '/members/private-member', '/members/:member'],
    ['api', 'api.pingxingxian.space', '/console/private-user', '/console'],
  ]) {
    const page = browser({ url: `https://${host}${path}?private=data#hash`, dataset: { site } });
    await page.start(); await page.advance(30000);
    assert.equal(page.sentEvents()[0].path, expected);
    assert.doesNotMatch(page.requests[0].init.body, /private-topic|private-member|private-user|private=data/);
  }
});

test('queue accepts at most 40 events, each request at most 20, and no empty polling follows', async () => {
  const page = browser(); await page.start();
  for (let i = 0; i < 100; i++) page.action('game_open', `/games/public-${i}`);
  assert.equal(page.requests.length, 0);
  await page.idle(); await page.advance(30000);
  assert.equal(page.requests.length, 2);
  assert.equal(page.sentEvents().length, 40);
  assert.ok(page.requests.every(request => request.body.events.length <= 20));
  await page.advance(600000);
  assert.equal(page.requests.length, 2);
  assert.equal(page.timers.size, 0);
});

test('small batches submit after 30 seconds without credentials or awaited business work', async () => {
  const page = browser(); await page.start();
  page.action('game_open', '/games/public');
  await page.advance(29999); assert.equal(page.requests.length, 0);
  await page.advance(1);
  const { init, body } = page.requests[0];
  assert.equal(body.events.length, 2);
  assert.equal(init.method, 'POST');
  assert.equal(init.mode, 'cors');
  assert.equal(init.credentials, 'omit');
  assert.equal(init.keepalive, true);
  assert.equal(init.headers['Content-Type'], 'text/plain;charset=UTF-8');
  assert.deepEqual(Object.keys(init.headers), ['Content-Type']);
});

test('network rejection, 429 and 503 stop this page, clear pending events, and never retry', async () => {
  for (const fetch of [
    () => Promise.reject(new Error('offline')),
    () => Promise.resolve({ ok: false, status: 429 }),
    () => Promise.resolve({ ok: false, status: 503 }),
  ]) {
    const page = browser({ fetch }); await page.start(); await page.advance(30000);
    page.action('game_open', '/games/after-error'); await page.navigate('/games/new-route');
    await page.advance(300000); page.window.emit('pagehide');
    assert.equal(page.requests.length, 1);
    assert.equal(page.beacons.length, 0);
  }
});

test('in-flight requests abort after three seconds and do not create retry loops', async () => {
  let aborted = 0;
  const page = browser({ fetch: (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => { aborted++; reject(new Error('AbortError')); }, { once: true });
  }) });
  await page.start(); await page.advance(30000);
  await page.advance(2999); assert.equal(aborted, 0);
  await page.advance(1); assert.equal(aborted, 1);
  page.action('game_open', '/games/after-abort'); await page.advance(300000);
  assert.equal(page.requests.length, 1);
});

test('only one request can be in flight even when the bounded queue receives more actions', async () => {
  const page = browser({ fetch: (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('AbortError')), { once: true });
  }) });
  await page.start();
  for (let i = 0; i < 40; i++) page.action('game_open', `/games/first-${i}`);
  await page.idle();
  assert.equal(page.requests.length, 1);
  for (let i = 0; i < 100; i++) page.action('game_open', `/games/next-${i}`);
  await page.idle();
  assert.equal(page.requests.length, 1);
  await page.advance(3000);
  page.window.emit('pagehide');
  assert.equal(page.requests.length, 1);
  assert.equal(page.beacons.length, 0);
});

test('visibility + pagehide omit authentication, never duplicate events and never retry failures', async () => {
  for (const settings of [
    {},
    { fetch: () => Promise.reject(new Error('offline on leave')) },
    { fetch: () => Promise.resolve({ ok: false, status: 503 }) },
  ]) {
    const page = browser(settings); await page.start();
    page.action('game_open', '/games/public');
    page.document.visibilityState = 'hidden';
    assert.doesNotThrow(() => { page.document.emit('visibilitychange'); page.window.emit('pagehide'); });
    await page.advance(300000);
    // sendBeacon 无法设置 credentials=omit；离页同样须使用不带认证的 keepalive 请求。
    assert.equal(page.beacons.length, 0);
    assert.equal(page.requests.length, 1);
    const { body: value, init, url } = page.requests[0];
    assert.equal(url, endpoint);
    assert.equal(init.credentials, 'omit');
    assert.equal(init.keepalive, true);
    assert.equal(new Set(value.events.map(event => event.event_id)).size, value.events.length);
    assert.equal(value.events.length, 2);
  }
});

test('history retains native this, arguments, return values and exact exceptions', async () => {
  const page = browser(); await page.start();
  const receiver = { nativeReceiver: true };
  const state = { privateState: 'not-serialized' };
  const value = page.history.pushState.call(receiver, state, 'private title', '/games/next');
  assert.equal(value, 'native:pushState');
  assert.equal(page.originalCalls[0].thisValue, receiver);
  assert.equal(page.originalCalls[0].args[0], state);
  assert.equal(page.originalCalls[0].args[1], 'private title');
  assert.equal(page.originalCalls[0].args[2], '/games/next');
  await page.idle();
  const failure = new Error('native navigation failure');
  page.historyErrors.replaceState = failure;
  assert.throws(() => page.history.replaceState({}, '', '/games/fail'), error => error === failure);
  assert.equal(page.idles.length, 0);
  await page.advance(30000);
  assert.doesNotMatch(page.requests[0].init.body, /privateState|not-serialized|private title|games\/fail/);
});

test('trusted tool result-button clicks are whitelisted and disabled/synthetic clicks ignored', async () => {
  const page = browser({ url: 'https://tools.pingxingxian.space/pdf/merge', dataset: { site: 'tools' } });
  await page.start();
  const click = (target, isTrusted = true) => page.document.emit('click', { target, isTrusted });
  click(new page.Element('tool_download'));
  click(new page.Element(undefined, { button: new page.Element('tool_copy') }));
  click(new page.Element('tool_upload'));
  click(new page.Element('tool_copy', { disabled: true }));
  click(new page.Element('tool_copy'), false);
  click({});
  await page.advance(30000);
  assert.deepEqual(page.sentEvents().map(event => event.event_name), ['page_view', 'tool_download', 'tool_copy']);
  assert.ok(page.sentEvents().every(event => event.path === '/pdf/merge'));
});

test('explicit actions accept only supported names and public game slug overrides', async () => {
  const page = browser(); await page.start();
  page.action('game_open', '/games/public-slug');
  for (const name of ['tool_run', 'tool_complete', 'login', '__proto__', undefined]) page.action(name, '/games/should-not-send');
  await page.advance(30000);
  assert.deepEqual(page.sentEvents().map(event => event.event_name), ['page_view', 'game_open']);
  assert.equal(page.sentEvents()[1].path, '/games/public-slug');
  const unsafe = browser(); await unsafe.start();
  unsafe.action('game_open', '/account/private-account');
  unsafe.action('game_open', '/games/private?email=alice');
  await unsafe.advance(30000);
  assert.doesNotMatch(unsafe.requests[0].init.body, /private-account|email=alice/);
  const privateOverride = browser({ url: 'https://chat.pingxingxian.space/c/private-chat', dataset: { site: 'chat' } });
  await privateOverride.start();
  privateOverride.action('game_open', '/c/private-chat');
  await privateOverride.advance(30000);
  assert.doesNotMatch(privateOverride.requests[0].init.body, /private-chat/);
});

test('changing privacy preference drops queued events without a final send', async () => {
  const page = browser(); await page.start();
  page.cookies.set('px_traffic_exclude', '1');
  page.window.emit('pl:traffic-preference', { detail: { excluded: true } });
  await page.advance(30000); page.window.emit('pagehide');
  assert.equal(page.requests.length + page.beacons.length, 0);
});

test('explicitly clearing initial exclusion resumes public PVs but never private routes', async () => {
  for (const path of ['/', '/admin/analytics']) {
    const page = browser({ url: `https://pingxingxian.space${path}`, cookies: { px_traffic_exclude: '1' } });
    await page.start();
    assert.equal(page.cookieWrites.length, 0);
    page.cookies.delete('px_traffic_exclude');
    page.window.emit('pl:traffic-preference', { detail: { excluded: false } });
    await page.advance(30000);
    assert.equal(page.sentEvents().length, path === '/' ? 1 : 0);
  }
});

test('missing cryptographic randomness skips collection rather than inventing an identity', async () => {
  const page = browser({ noCrypto: true }); await page.start(); await page.advance(30000);
  assert.equal(page.requests.length, 0);
  assert.equal(page.cookieWrites.length + page.storageWrites.length, 0);
});
