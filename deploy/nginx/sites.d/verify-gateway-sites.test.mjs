import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractServerNames, verifyGatewaySitesDirectory } from './verify-gateway-sites.mjs';

const SITES_DIR = path.dirname(fileURLToPath(import.meta.url));

test('validates real repo sites.d directory and 00-include-sites.conf', () => {
	const summary = verifyGatewaySitesDirectory(SITES_DIR, {
		includeFile: path.join(SITES_DIR, '00-include-sites.conf')
	});
	assert.equal(summary.ok, true);
	assert.equal(summary.shared_gateway_blast_radius_unchanged, true);
});

test('accepts valid Tavern and Matrix site conf files and detects duplicates', () => {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-gw-sites-'));
	try {
		fs.writeFileSync(
			path.join(tmp, 'tavern.conf'),
			'server {\n  listen 443 ssl;\n  server_name tavern.pingxingxian.space matrix.pingxingxian.space;\n}\n'
		);
		const ok = verifyGatewaySitesDirectory(tmp);
		assert.equal(ok.ok, true);
		assert.equal(ok.domain_count, 2);

		fs.writeFileSync(
			path.join(tmp, 'duplicate.conf'),
			'server {\n  listen 443 ssl;\n  server_name tavern.pingxingxian.space;\n}\n'
		);
		assert.throws(() => verifyGatewaySitesDirectory(tmp), /duplicate_server_name:tavern\.pingxingxian\.space/);
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true });
	}
});

test('blocks site file from hijacking core pingxingxian.space domain', () => {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-gw-core-'));
	try {
		fs.writeFileSync(
			path.join(tmp, 'bad.conf'),
			'server {\n  listen 443 ssl;\n  server_name pingxingxian.space;\n}\n'
		);
		assert.throws(() => verifyGatewaySitesDirectory(tmp), /site_file_hijacks_core_domain/);
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true });
	}
});

test('extractServerNames ignores comments', () => {
	const names = extractServerNames('# server_name fake.test;\nserver_name tavern.pingxingxian.space;\n');
	assert.deepEqual(names, ['tavern.pingxingxian.space']);
});
