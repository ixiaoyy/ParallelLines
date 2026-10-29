'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { clientConfig, hideBalancePresentation } = require('../client-config.cjs');

test('hide native balance UI without mutating server balance configuration or model permissions', () => {
  const server = { appTitle: 'fixture', balance: { enabled: true, startBalance: 10000 },
    modelSpecs: { list: [{ name: 'fixture' }] }, interface: { modelSelect: false } };
  const client = clientConfig(server);
  assert.equal(client.balance.enabled, false);
  assert.equal(server.balance.enabled, true);
  assert.equal(client.modelSpecs, server.modelSpecs);
  assert.equal(client.interface, server.interface);
  // The combined directory is an overlay, so its read-only baseline may be supplied
  // explicitly instead of copying unrelated deploy configuration into the candidate.
  const base = JSON.parse(fs.readFileSync(process.env.SSO_TEST_BASE_CONFIG || path.join(__dirname, '../../../base-config.json'), 'utf8'));
  assert.equal(base.balance.enabled, true);
});

test('only startup JSON presentation is filtered, not balance APIs or error/string responses', () => {
  const sent = [];
  const res = { send(value) { sent.push(value); } };
  let calls = 0;
  hideBalancePresentation({ method: 'GET', originalUrl: '/api/config' }, res, () => calls++);
  res.send({ appTitle: 'fixture', balance: { enabled: true } });
  res.send('fixture-error');
  assert.equal(calls, 1);
  assert.equal(sent[0].balance.enabled, false);
  assert.equal(sent[1], 'fixture-error');
  for (const [method, url] of [['POST','/api/config'], ['GET','/api/balance'], ['GET','/api/config/other']]) {
    const other = { send() {} }; const original = other.send;
    hideBalancePresentation({ method, originalUrl: url }, other, () => {});
    assert.equal(other.send, original);
  }
});
