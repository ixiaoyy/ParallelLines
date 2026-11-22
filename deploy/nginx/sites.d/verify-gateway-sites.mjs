// ParallelLines 共享 Nginx 网关发布前静态校验脚本。
// 校验 sites.d 目录内站点的命名安全、无重复 server_name、不劫持主站核心域名。
// 注意：分文件只解决配置归属，不缩小共享网关故障范围；线上切换前仍须执行 nginx -t。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const SAFE_SITE_FILENAME_RE = /^[a-z0-9][a-z0-9._-]*\.conf$/;
export const CORE_PROTECTED_DOMAINS = new Set([
	'pingxingxian.space',
	'www.pingxingxian.space',
	'_'
]);

export function extractServerNames(confText) {
	const names = [];
	const cleaned = confText.replace(/#[^\n]*/g, '');
	const regex = /\bserver_name\s+([^;]+);/g;
	let match;
	while ((match = regex.exec(cleaned)) !== null) {
		for (const token of match[1].trim().split(/\s+/)) {
			if (token) names.push(token.toLowerCase());
		}
	}
	return names;
}

export function verifyGatewaySitesDirectory(sitesDir, { includeFile = null } = {}) {
	const resolvedDir = path.resolve(sitesDir);
	if (!fs.existsSync(resolvedDir) || !fs.statSync(resolvedDir).isDirectory()) {
		throw new Error(`gateway_sites_dir_missing:${resolvedDir}`);
	}

	if (includeFile) {
		const includeText = fs.readFileSync(path.resolve(includeFile), 'utf8');
		const nonCommentLines = includeText
			.split(/\r?\n/)
			.map((line) => line.trim())
			.filter((line) => line && !line.startsWith('#'));
		if (nonCommentLines.length !== 1 || nonCommentLines[0] !== 'include /etc/nginx/sites.d/*.conf;') {
			throw new Error('gateway_include_file_unexpected_content');
		}
	}

	const entries = fs.readdirSync(resolvedDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));
	const checkedFiles = [];
	const domainOwners = new Map();

	for (const entry of entries) {
		if (!entry.name.endsWith('.conf')) continue;
		if (entry.name === '00-include-sites.conf') continue;
		if (!SAFE_SITE_FILENAME_RE.test(entry.name)) {
			throw new Error(`unsafe_site_filename:${entry.name}`);
		}
		const fullPath = path.join(resolvedDir, entry.name);
		const stat = fs.lstatSync(fullPath);
		if (stat.isSymbolicLink() || !stat.isFile()) {
			throw new Error(`site_file_must_be_regular:${entry.name}`);
		}
		const text = fs.readFileSync(fullPath, 'utf8');
		const serverNames = extractServerNames(text);
		if (serverNames.length === 0) {
			throw new Error(`site_file_missing_server_name:${entry.name}`);
		}
		for (const domain of serverNames) {
			if (CORE_PROTECTED_DOMAINS.has(domain)) {
				throw new Error(`site_file_hijacks_core_domain:${entry.name}:${domain}`);
			}
			const existingOwner = domainOwners.get(domain);
			if (existingOwner && existingOwner !== entry.name) {
				throw new Error(`duplicate_server_name:${domain}:${existingOwner},${entry.name}`);
			}
			domainOwners.set(domain, entry.name);
		}
		checkedFiles.push({ file: entry.name, server_names: [...new Set(serverNames)] });
	}

	return {
		ok: true,
		site_files: checkedFiles,
		domain_count: domainOwners.size,
		shared_gateway_blast_radius_unchanged: true
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const sitesDir = process.argv[2] || path.dirname(fileURLToPath(import.meta.url));
	const includeFile = process.argv[3] || path.join(path.dirname(fileURLToPath(import.meta.url)), '00-include-sites.conf');
	const summary = verifyGatewaySitesDirectory(sitesDir, { includeFile });
	console.log(JSON.stringify(summary));
}
