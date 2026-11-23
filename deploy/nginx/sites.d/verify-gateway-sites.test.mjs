import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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

test('deployment preflight rejects an empty mount, while the template check still accepts it', () => {
	const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-gw-active-'));
	const site = path.join(directory, 'entertainment.conf');
	const args = [path.join(SITES_DIR, 'verify-gateway-sites.mjs'), directory,
		path.join(SITES_DIR, '00-include-sites.conf')];
	const run = (...flags) => spawnSync(process.execPath, [...args, ...flags], { encoding: 'utf8', timeout: 5000 });
	try {
		const template = run();
		assert.equal(template.status, 0, template.stderr);
		assert.equal(JSON.parse(template.stdout).domain_count, 0);
		const empty = run('--require-active-routes');
		assert.equal(empty.status, 1, empty.stderr);
		assert.match(empty.stderr, /gateway_sites_no_active_routes/);
		assert.equal(empty.stdout, '');

		fs.writeFileSync(site, 'server { server_name tavern.pingxingxian.space matrix.pingxingxian.space; }\n');
		const ready = run('--require-active-routes');
		assert.equal(ready.status, 0, ready.stderr);
		assert.equal(JSON.parse(ready.stdout).domain_count, 2);
	} finally {
		if (fs.existsSync(site)) fs.unlinkSync(site);
		fs.rmdirSync(directory);
	}
});

test('required route contract verifies exact domain ownership for target site file', () => {
	const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-gw-req-'));
	const args = [path.join(SITES_DIR, 'verify-gateway-sites.mjs'), directory,
		path.join(SITES_DIR, '00-include-sites.conf'), '--require-active-routes',
		'--require-route', 'parallellines-entertainment.conf=tavern.pingxingxian.space,matrix.pingxingxian.space'];
	const run = () => spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 5000 });
	try {
		// Directory is non-empty due to another site, but Tavern/Matrix file is missing -> must fail
		fs.writeFileSync(path.join(directory, 'other.conf'), 'server { server_name other.pingxingxian.space; }\n');
		const missingTarget = run();
		assert.equal(missingTarget.status, 1);
		assert.match(missingTarget.stderr, /required_route_file_missing:parallellines-entertainment\.conf/);

		// Target file exists, but only owns one of the two required domains -> must fail
		fs.writeFileSync(
			path.join(directory, 'parallellines-entertainment.conf'),
			'server { server_name tavern.pingxingxian.space; }\n'
		);
		const partialDomain = run();
		assert.equal(partialDomain.status, 1);
		assert.match(partialDomain.stderr, /required_route_domain_not_owned:parallellines-entertainment\.conf:matrix\.pingxingxian\.space/);

		// Target file owns both required domains plus an extra unexpected domain -> must fail
		fs.writeFileSync(
			path.join(directory, 'parallellines-entertainment.conf'),
			'server { server_name tavern.pingxingxian.space matrix.pingxingxian.space extra.pingxingxian.space; }\n'
		);
		const extraDomain = run();
		assert.equal(extraDomain.status, 1);
		assert.match(extraDomain.stderr, /required_route_unexpected_domain:parallellines-entertainment\.conf:extra\.pingxingxian\.space/);

		// Target file owns exact two domains -> passes even when other valid site exists
		fs.writeFileSync(
			path.join(directory, 'parallellines-entertainment.conf'),
			'server { server_name tavern.pingxingxian.space matrix.pingxingxian.space; }\n'
		);
		const exact = run();
		assert.equal(exact.status, 0, exact.stderr);
		assert.equal(JSON.parse(exact.stdout).domain_count, 3);
	} finally {
		fs.rmSync(directory, { recursive: true, force: true });
	}
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
