// 一键执行 ParallelLines 全套架构边界静态守卫（账号写权 + 运维域边界 + 共享网关站点校验）。
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyAccountWriteBoundaries } from './verify_account_write_boundaries.mjs';
import { verifyOpsBoundaries } from './verify_ops_boundaries.mjs';
import { verifySharedFacilitiesBoundaries } from './verify_shared_facilities_boundaries.mjs';
import { verifyGatewaySitesDirectory } from '../../deploy/nginx/sites.d/verify-gateway-sites.mjs';

const SCRIPTS_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPTS_DIR, '..', '..');

export function runAllArchitectureGuards(repoRoot = REPO_ROOT) {
	const root = path.resolve(repoRoot);
	const account = verifyAccountWriteBoundaries(path.join(root, 'apps', 'api', 'app'));
	const ops = verifyOpsBoundaries(path.join(root, '.github'));
	const facilities = verifySharedFacilitiesBoundaries(root);
	const sitesDir = path.join(root, 'deploy', 'nginx', 'sites.d');
	const gateway = verifyGatewaySitesDirectory(sitesDir, {
		includeFile: path.join(sitesDir, '00-include-sites.conf')
	});

	return {
		ok: true,
		guards: {
			account_write_boundaries: account,
			ops_boundaries: ops,
			shared_facilities_boundaries: facilities,
			gateway_sites: gateway
		}
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	console.log(JSON.stringify(runAllArchitectureGuards(), null, 2));
}
