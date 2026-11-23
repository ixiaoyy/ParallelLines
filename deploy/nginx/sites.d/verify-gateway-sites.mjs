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

export function parseRequiredRouteSpecs(specs = []) {
	const requirements = [];
	const seenDomains = new Set();
	for (const raw of specs) {
		const spec = String(raw || '').trim();
		const eqIndex = spec.indexOf('=');
		if (eqIndex <= 0 || eqIndex === spec.length - 1) {
			throw new Error(`invalid_required_route_spec:${spec}`);
		}
		const file = spec.slice(0, eqIndex).trim();
		if (!SAFE_SITE_FILENAME_RE.test(file) || file === '00-include-sites.conf') {
			throw new Error(`invalid_required_route_file:${file}`);
		}
		const domains = spec
			.slice(eqIndex + 1)
			.split(',')
			.map((d) => d.trim().toLowerCase())
			.filter(Boolean);
		if (domains.length === 0) {
			throw new Error(`invalid_required_route_domains:${spec}`);
		}
		for (const domain of domains) {
			if (CORE_PROTECTED_DOMAINS.has(domain) || seenDomains.has(domain)) {
				throw new Error(`invalid_required_route_domain:${domain}`);
			}
			seenDomains.add(domain);
		}
		requirements.push({ file, domains });
	}
	return requirements;
}

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

export function verifyGatewaySitesDirectory(
	sitesDir,
	{ includeFile = null, requireActiveRoutes = false, requiredRoutes = [] } = {}
) {
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

	const parsedRequired = Array.isArray(requiredRoutes)
		? requiredRoutes.every((item) => typeof item === 'string')
			? parseRequiredRouteSpecs(requiredRoutes)
			: requiredRoutes
		: [];

	const entries = fs.readdirSync(resolvedDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));
	const checkedFiles = [];
	const domainOwners = new Map();
	const fileDomainSets = new Map();

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
		const uniqueNames = [...new Set(serverNames)];
		fileDomainSets.set(entry.name, new Set(uniqueNames));
		checkedFiles.push({ file: entry.name, server_names: uniqueNames });
	}

	if (requireActiveRoutes && domainOwners.size === 0) {
		throw new Error('gateway_sites_no_active_routes');
	}

	for (const req of parsedRequired) {
		const actualSet = fileDomainSets.get(req.file);
		if (!actualSet) {
			throw new Error(`required_route_file_missing:${req.file}`);
		}
		const expectedSet = new Set(req.domains.map((d) => d.toLowerCase()));
		for (const domain of expectedSet) {
			if (domainOwners.get(domain) !== req.file) {
				throw new Error(`required_route_domain_not_owned:${req.file}:${domain}`);
			}
		}
		for (const actualDomain of actualSet) {
			if (!expectedSet.has(actualDomain)) {
				throw new Error(`required_route_unexpected_domain:${req.file}:${actualDomain}`);
			}
		}
	}

	return {
		ok: true,
		site_files: checkedFiles,
		domain_count: domainOwners.size,
		shared_gateway_blast_radius_unchanged: true
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const rawArgs = process.argv.slice(2);
	const positionals = [];
	let requireActiveRoutes = false;
	const requiredRouteSpecs = [];
	for (let i = 0; i < rawArgs.length; i += 1) {
		const arg = rawArgs[i];
		if (arg === '--require-active-routes') {
			requireActiveRoutes = true;
		} else if (arg === '--require-route') {
			i += 1;
			if (i >= rawArgs.length) {
				throw new Error('missing_require_route_value');
			}
			requiredRouteSpecs.push(rawArgs[i]);
		} else if (arg.startsWith('--require-route=')) {
			requiredRouteSpecs.push(arg.slice('--require-route='.length));
		} else if (arg.startsWith('--')) {
			throw new Error(`unknown_verify_gateway_sites_flag:${arg}`);
		} else {
			positionals.push(arg);
		}
	}
	const defaultDir = path.dirname(fileURLToPath(import.meta.url));
	const sitesDir = positionals[0] || defaultDir;
	const includeFile = positionals[1] || path.join(defaultDir, '00-include-sites.conf');
	const summary = verifyGatewaySitesDirectory(sitesDir, {
		includeFile,
		requireActiveRoutes,
		requiredRoutes: requiredRouteSpecs
	});
	console.log(JSON.stringify(summary));
}
