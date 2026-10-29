#!/usr/bin/env python3
"""Validate a runner-produced plain tar and install only public client artifacts."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile

SOURCE_COMMIT = '8d3da9bbb220a0a96be9330a2e1cbd385fb786d5'
MAX_FILES = 10000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
HEX = re.compile(r'^[0-9a-f]{64}$')
SEGMENT = re.compile(r'^[A-Za-z0-9._~-]+$')


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def relative_name(value: str) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 2048, 'invalid_asset_path')
    require(all(part not in ('', '.', '..') and SEGMENT.fullmatch(part)
                for part in value.split('/')), 'invalid_asset_path')
    return value


def regular_file(path: Path) -> os.stat_result:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'not_single_regular_file')
    return info


def directory(path: Path) -> None:
    require(stat.S_ISDIR(path.lstat().st_mode), 'not_real_directory')


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def verified_tar(archive: Path, expected_sha: str):
    # Hash and parse the same opened file, never a path reopened after verification.
    descriptor = os.open(archive, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'not_single_regular_file')
        require(info.st_size <= MAX_TOTAL_BYTES + 16 * 1024 * 1024, 'archive_too_large')
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        require(digest.hexdigest() == expected_sha, 'bundle_sha_mismatch')
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode='r:') as tar:
            yield tar


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate_manifest_key')
        value[key] = item
    return value


def parse_manifest(raw: bytes, patch_sha: str) -> dict:
    require(len(raw) <= MAX_MANIFEST_BYTES, 'manifest_too_large')
    value = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(value, dict) and set(value) ==
            {'schemaVersion', 'sourceCommit', 'patchSha256', 'files'}, 'invalid_manifest_schema')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1, 'invalid_manifest_schema')
    require(value['sourceCommit'] == SOURCE_COMMIT, 'source_commit_mismatch')
    require(value['patchSha256'] == patch_sha, 'patch_sha_mismatch')
    files = value['files']
    require(isinstance(files, dict) and 0 < len(files) <= MAX_FILES and 'index.html' in files,
            'invalid_manifest_files')
    for name, digest in files.items():
        relative_name(name)
        require(isinstance(digest, str) and HEX.fullmatch(digest), 'invalid_asset_hash')
    return value


def safe_remove(path: Path, root: Path, prefix: str) -> None:
    require(path.parent == root and path.name.startswith(prefix), 'unsafe_cleanup_target')
    directory(path)
    shutil.rmtree(path)


def verify_inventory(root: Path, expected: dict) -> None:
    actual = set()
    total = 0
    for current, directories, files in os.walk(root, followlinks=False):
        current = Path(current)
        for name in directories:
            directory(current / name)
        for name in files:
            path = current / name
            info = regular_file(path)
            total += info.st_size
            require(info.st_size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, 'existing_revision_too_large')
            relative = path.relative_to(root).as_posix()
            relative_name(relative)
            actual.add(relative)
            require(relative in expected and file_sha(path) == expected[relative], 'existing_revision_mismatch')
    require(actual == set(expected), 'existing_revision_mismatch')


def install_bundle(archive: Path, expected_sha: str, integration: Path) -> dict:
    integration = integration.absolute()
    directory(integration)
    require(HEX.fullmatch(expected_sha) is not None, 'invalid_bundle_sha')
    runtime = integration / '.runtime'
    directory(runtime)
    incoming = runtime / 'incoming'
    directory(incoming)
    archive = archive.absolute()
    archive_match = re.fullmatch(r'native-session-([0-9a-f]{40})\.tar', archive.name)
    require(archive.parent == incoming and archive_match,
            'invalid_bundle_location')
    revision = archive_match.group(1)
    require(regular_file(archive).st_size <= MAX_TOTAL_BYTES + 16 * 1024 * 1024, 'archive_too_large')
    patch = integration / 'patches/native-session.patch'
    directory(patch.parent)
    regular_file(patch)
    patch_sha = file_sha(patch)
    client_root = runtime / 'native-client'
    if not client_root.exists():
        client_root.mkdir(mode=0o755)
    directory(client_root)
    destination = client_root / revision
    manifest_destination = runtime / 'native-client-manifest.json'
    pointer_destination = runtime / 'session-release.env'
    if destination.exists() or destination.is_symlink():
        directory(destination)
    if manifest_destination.exists() or manifest_destination.is_symlink():
        regular_file(manifest_destination)
    if pointer_destination.exists() or pointer_destination.is_symlink():
        regular_file(pointer_destination)

    # Stage public assets before changing the mounted tree. Never use extractall.
    stage = Path(tempfile.mkdtemp(prefix='.native-stage-', dir=runtime))
    os.chmod(stage, 0o700)
    client_stage = stage / 'native-client'
    client_stage.mkdir(mode=0o755)
    try:
        with verified_tar(archive, expected_sha) as tar:
            members = []
            for member in tar:
                require(len(members) < MAX_FILES + 1, 'invalid_archive_file_count')
                members.append(member)
            require(0 < len(members) <= MAX_FILES + 1, 'invalid_archive_file_count')
            seen = set()
            assets = {}
            manifest_member = None
            total = 0
            for member in members:
                require(member.isreg() and not member.pax_headers and member.sparse is None,
                        'non_regular_archive_member')
                require(member.name not in seen, 'duplicate_archive_member')
                seen.add(member.name)
                require(0 <= member.size <= MAX_FILE_BYTES, 'asset_too_large')
                total += member.size
                require(total <= MAX_TOTAL_BYTES, 'archive_expansion_too_large')
                if member.name == 'native-client-manifest.json':
                    require(member.size <= MAX_MANIFEST_BYTES, 'manifest_too_large')
                    manifest_member = member
                else:
                    require(member.name.startswith('native-client/'), 'unexpected_archive_member')
                    name = relative_name(member.name[len('native-client/'):])
                    assets[name] = member
            require(manifest_member is not None, 'missing_manifest')
            with tar.extractfile(manifest_member) as stream:
                manifest_raw = stream.read(MAX_MANIFEST_BYTES + 1)
            manifest = parse_manifest(manifest_raw, patch_sha)
            require(set(assets) == set(manifest['files']), 'asset_inventory_mismatch')
            for name, member in assets.items():
                output = client_stage.joinpath(*name.split('/'))
                output.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                length = 0
                with tar.extractfile(member) as source, output.open('xb') as target:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        length += len(block)
                        require(length <= member.size, 'asset_size_mismatch')
                        digest.update(block)
                        target.write(block)
                os.chmod(output, 0o644)
                require(length == member.size and digest.hexdigest() == manifest['files'][name],
                        'asset_sha_mismatch')
            staged_manifest = stage / 'native-client-manifest.json'
            staged_manifest.write_bytes(manifest_raw)
            os.chmod(staged_manifest, 0o644)
        # Immutable revision trees keep the currently mounted directory untouched.
        # An identical retry is accepted, but a revision can never be overwritten.
        if destination.exists():
            verify_inventory(destination, manifest['files'])
        else:
            os.replace(client_stage, destination)
        staged_pointer = stage / 'session-release.env'
        staged_pointer.write_text('CHAT_SESSION_RELEASE=' + revision + '\n', encoding='ascii')
        os.chmod(staged_pointer, 0o644)
        os.replace(staged_manifest, manifest_destination)
        os.replace(staged_pointer, pointer_destination)
        return {'verified': True, 'sourceCommit': SOURCE_COMMIT, 'revision': revision,
                'assetCount': len(manifest['files'])}
    finally:
        if stage.exists():
            safe_remove(stage, runtime, '.native-stage-')


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 3, 'usage_expected_archive_and_sha')
        print(json.dumps(install_bundle(Path(sys.argv[1]), sys.argv[2], Path(__file__).resolve().parent)))
    except Exception as error:
        # No archive paths, member input, environment or credentials are logged.
        print('native_client_install_rejected:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
