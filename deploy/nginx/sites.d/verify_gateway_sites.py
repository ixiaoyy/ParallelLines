#!/usr/bin/env python3
"""ParallelLines 共享 Nginx 网关发布前静态校验脚本（Python 3 标准库版，供无 Node 的生产宿主使用）。"""

import json
from pathlib import Path
import re
import sys


SAFE_SITE_FILENAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*\.conf$')
CORE_PROTECTED_DOMAINS = {'pingxingxian.space', 'www.pingxingxian.space', '_'}
SERVER_NAME_RE = re.compile(r'\bserver_name\s+([^;]+);')


def parse_required_route_specs(specs):
    requirements = []
    seen_domains = set()
    for raw in specs:
        spec = str(raw or '').strip()
        eq = spec.find('=')
        if eq <= 0 or eq == len(spec) - 1:
            raise ValueError(f'invalid_required_route_spec:{spec}')
        filename = spec[:eq].strip()
        if not SAFE_SITE_FILENAME_RE.fullmatch(filename) or filename == '00-include-sites.conf':
            raise ValueError(f'invalid_required_route_file:{filename}')
        domains = [d.strip().lower() for d in spec[eq + 1:].split(',') if d.strip()]
        if not domains:
            raise ValueError(f'invalid_required_route_domains:{spec}')
        for domain in domains:
            if domain in CORE_PROTECTED_DOMAINS or domain in seen_domains:
                raise ValueError(f'invalid_required_route_domain:{domain}')
            seen_domains.add(domain)
        requirements.append((filename, domains))
    return requirements


def extract_server_names(conf_text):
    cleaned = re.sub(r'#[^\n]*', '', conf_text)
    names = []
    for match in SERVER_NAME_RE.finditer(cleaned):
        for token in match.group(1).strip().split():
            if token:
                names.append(token.lower())
    return names


def verify_gateway_sites_directory(sites_dir, *, include_file=None, require_active_routes=False, required_routes=()):
    resolved_dir = Path(sites_dir).resolve()
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise ValueError(f'gateway_sites_dir_missing:{resolved_dir}')

    if include_file:
        include_text = Path(include_file).resolve().read_text(encoding='utf-8')
        non_comment = [line.strip() for line in include_text.splitlines()
                       if line.strip() and not line.strip().startswith('#')]
        if non_comment != ['include /etc/nginx/sites.d/*.conf;']:
            raise ValueError('gateway_include_file_unexpected_content')

    parsed_required = parse_required_route_specs(required_routes)
    checked_files = []
    domain_owners = {}
    file_domain_sets = {}

    for entry in sorted(resolved_dir.iterdir(), key=lambda p: p.name):
        name = entry.name
        if not name.endswith('.conf') or name == '00-include-sites.conf':
            continue
        if not SAFE_SITE_FILENAME_RE.fullmatch(name):
            raise ValueError(f'unsafe_site_filename:{name}')
        if entry.is_symlink() or not entry.is_file():
            raise ValueError(f'site_file_must_be_regular:{name}')
        server_names = extract_server_names(entry.read_text(encoding='utf-8'))
        if not server_names:
            raise ValueError(f'site_file_missing_server_name:{name}')
        for domain in server_names:
            if domain in CORE_PROTECTED_DOMAINS:
                raise ValueError(f'site_file_hijacks_core_domain:{name}:{domain}')
            existing = domain_owners.get(domain)
            if existing and existing != name:
                raise ValueError(f'duplicate_server_name:{domain}:{existing},{name}')
            domain_owners[domain] = name
        unique = list(dict.fromkeys(server_names))
        file_domain_sets[name] = set(unique)
        checked_files.append({'file': name, 'server_names': unique})

    if require_active_routes and not domain_owners:
        raise ValueError('gateway_sites_no_active_routes')

    for filename, domains in parsed_required:
        actual_set = file_domain_sets.get(filename)
        if actual_set is None:
            raise ValueError(f'required_route_file_missing:{filename}')
        expected_set = set(domains)
        for domain in expected_set:
            if domain_owners.get(domain) != filename:
                raise ValueError(f'required_route_domain_not_owned:{filename}:{domain}')
        for actual_domain in actual_set:
            if actual_domain not in expected_set:
                raise ValueError(f'required_route_unexpected_domain:{filename}:{actual_domain}')

    return {
        'ok': True,
        'site_files': checked_files,
        'domain_count': len(domain_owners),
        'shared_gateway_blast_radius_unchanged': True,
    }


def main(argv):
    positionals = []
    require_active_routes = False
    required_routes = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == '--require-active-routes':
            require_active_routes = True
        elif arg == '--require-route':
            i += 1
            if i >= len(argv):
                raise ValueError('missing_require_route_value')
            required_routes.append(argv[i])
        elif arg.startswith('--require-route='):
            required_routes.append(arg[len('--require-route='):])
        elif arg.startswith('--'):
            raise ValueError(f'unknown_verify_gateway_sites_flag:{arg}')
        else:
            positionals.append(arg)
        i += 1
    default_dir = Path(__file__).resolve().parent
    sites_dir = positionals[0] if len(positionals) >= 1 else default_dir
    include_file = positionals[1] if len(positionals) >= 2 else default_dir / '00-include-sites.conf'
    summary = verify_gateway_sites_directory(
        sites_dir,
        include_file=include_file,
        require_active_routes=require_active_routes,
        required_routes=required_routes,
    )
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
