'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { replaceModelLine } = require('./configure-models.cjs');

test('only the model line changes; credentials, comments and CRLF bytes are preserved', () => {
  const source = Buffer.from('# keep\r\nOPENAI_API_KEY=synthetic-fixture\r\nOPENAI_CHAT_MODELS=\r\nJWT_SECRET=synthetic-login\r\nCREDS_KEY=synthetic-encryption\r\n');
  const updated = replaceModelLine(source);
  const expected = Buffer.from('# keep\r\nOPENAI_API_KEY=synthetic-fixture\r\nOPENAI_CHAT_MODELS=gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol\r\nJWT_SECRET=synthetic-login\r\nCREDS_KEY=synthetic-encryption\r\n');
  assert.deepEqual(updated, expected);
  assert.deepEqual(replaceModelLine(updated), updated);
});

test('missing or duplicate settings stop instead of changing ambiguous environments', () => {
  for (const source of ['JWT_SECRET=synthetic\n', 'OPENAI_CHAT_MODELS=a\nOPENAI_CHAT_MODELS=b\n']) {
    assert.throws(() => replaceModelLine(Buffer.from(source)), /model_line_count/);
  }
});

test('the model setting without a final newline is handled without rewriting other bytes', () => {
  const before = Buffer.concat([Buffer.from([0x23, 0xff, 0x0a]), Buffer.from('OPENAI_CHAT_MODELS=old')]);
  assert.deepEqual(replaceModelLine(before), Buffer.concat([Buffer.from([0x23, 0xff, 0x0a]), Buffer.from('OPENAI_CHAT_MODELS=gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol')]));
});
