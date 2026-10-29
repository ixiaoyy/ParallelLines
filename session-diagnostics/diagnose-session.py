"""Fixed-window read-only diagnosis. Never emit raw log text or exception details."""
import datetime as dt
import json
import queue
import re
import subprocess
import sys
import threading
import time
from collections import Counter

SINCE = '2026-10-29T15:02:00Z'
UNTIL = '2026-10-29T15:10:00Z'
CONTAINERS = (
    'parallellines-nginx-1', 'parallellines-api-1',
    'parallellines-chat-librechat-1', 'parallellines-chat-chat-oidc-1',
)
PATHS = frozenset((
    '/chat/api/auth/refresh', '/chat/api/user', '/chat/api/config',
    '/chat/api/models', '/chat/api/endpoints', '/chat/api/files/config',
    '/api/auth/refresh', '/api/user', '/api/config', '/api/models',
    '/api/endpoints', '/api/files/config',
    '/api/v1/auth/chat-sso/session-state', '/auth/oidc/token',
    '/auth/oidc/auth', '/auth/oidc/interaction/finish', '/auth/chat',
    '/chat/oauth/openid', '/chat/oauth/openid/callback', '/auth',
    '/chat/', '/chat/c/new',
))
LABELS = (
    ('invalid_grant', 'invalid_grant'),
    ('[openidsessionrefresh]', 'native_openid_session_refresh'),
    ('[openidrefreshflight]', 'native_openid_refresh_flight'),
    ('[openidrefreshrecovery]', 'native_openid_refresh_recovery'),
    ('[refreshtokenbridge]', 'native_refresh_token_bridge'),
    ('authority_unavailable', 'authority_unavailable'),
    ('sso_session_required', 'sso_session_required'),
    ('jwt expired', 'jwt_expired'),
    ('upstream timed out', 'upstream_timeout'),
)
TIMESTAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z\s')
HTTP = re.compile(r'"(GET|POST|HEAD|OPTIONS) (/[^\s"]{1,4096}) HTTP/[0-9.]{1,8}" ([1-5]\d{2})(?=\s|$)')
REQUEST = re.compile(r'"(GET|POST|HEAD|OPTIONS) (/[^\s"]{1,4096}) HTTP/[0-9.]{1,8}"')
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
MAX_BYTES = 2 * 1024 * 1024
MAX_LINE = 16 * 1024
MAX_EVENTS = 200
TIMEOUT = 8.0
UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 29, 15, 2, tzinfo=UTC)
END = dt.datetime(2026, 10, 29, 15, 10, tzinfo=UTC)


def sanitize_line(raw):
    """Return only normalized timestamp, fixed enums/paths and validated HTTP status."""
    if len(raw) > MAX_LINE:
        return []
    line = ANSI.sub('', raw.decode('utf-8', errors='replace'))
    match = TIMESTAMP.match(line)
    if not match:
        return []
    try:
        stamp = dt.datetime.strptime(match[1], '%Y-%m-%dT%H:%M:%S').replace(
            microsecond=int((match[2] or '')[:6].ljust(6, '0')), tzinfo=UTC)
    except ValueError:
        return []
    if not START <= stamp < END:
        return []
    normalized = stamp.isoformat(timespec='microseconds').replace('+00:00', 'Z')
    events = []
    http = HTTP.search(line)
    if http:
        path = http[2].split('?', 1)[0].split('#', 1)[0]
        if path in PATHS:
            events.append({'at': normalized, 'kind': 'http', 'method': http[1],
                           'path': path, 'status': int(http[3])})
    lower = line.lower()
    for needle, label in LABELS:
        if needle in lower:
            event = {'at': normalized, 'kind': 'classification', 'label': label}
            request = REQUEST.search(line)
            if request:
                path = request[2].split('?', 1)[0].split('#', 1)[0]
                if path in PATHS:
                    event['path'] = path
            events.append(event)
    return events


def collect(command, timeout=TIMEOUT, max_bytes=MAX_BYTES):
    """Drain output with bounded memory/time; return sanitized data only."""
    result = {'completion': 'complete', 'bytes': 0, 'lines': 0,
              'oversized_lines': 0, 'events': [], 'counts': {}}
    counts = Counter()
    chunks = queue.Queue(maxsize=8)
    stop = threading.Event()
    read_failed = threading.Event()
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    except (OSError, ValueError):
        result['completion'] = 'process_unavailable'
        return result

    def reader():
        try:
            while not stop.is_set():
                block = process.stdout.read(65536)
                if not block:
                    break
                while not stop.is_set():
                    try:
                        chunks.put(block, timeout=0.1)
                        break
                    except queue.Full:
                        pass
        except (OSError, ValueError):
            read_failed.set()
        finally:
            while not stop.is_set():
                try:
                    chunks.put(None, timeout=0.1)
                    break
                except queue.Full:
                    pass

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    pending = b''
    discard_line = False
    deadline = time.monotonic() + timeout

    def accept(line):
        result['lines'] += 1
        for event in sanitize_line(line):
            key = ('http:' + event['path'] + ':' + str(event['status'])
                   if event['kind'] == 'http' else event['label'])
            counts[key] += 1
            if len(result['events']) < MAX_EVENTS:
                result['events'].append(event)

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result['completion'] = 'timeout'
                break
            try:
                block = chunks.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            if block is None:
                if pending and not discard_line:
                    accept(pending)
                break
            available = max_bytes - result['bytes']
            if len(block) > available:
                block = block[:available]
                result['completion'] = 'size_limit'
            result['bytes'] += len(block)
            parts = block.split(b'\n')
            for index, part in enumerate(parts):
                ended = index < len(parts) - 1
                if not discard_line:
                    if len(pending) + len(part) > MAX_LINE:
                        discard_line = True
                        pending = b''
                        result['oversized_lines'] += 1
                    else:
                        pending += part
                if ended:
                    if not discard_line:
                        accept(pending)
                    pending = b''
                    discard_line = False
            if result['completion'] == 'size_limit' or result['bytes'] >= max_bytes:
                result['completion'] = 'size_limit'
                break
        result['events_truncated'] = sum(counts.values()) > MAX_EVENTS
    finally:
        stop.set()
        if process.poll() is None:
            try:
                process.kill()  # Kill only the read-only docker-logs client, never a container.
            except OSError:
                result['completion'] = 'process_stop_error'
        try:
            code = process.wait(timeout=1)
            if code != 0 and result['completion'] == 'complete':
                result['completion'] = 'docker_error'
        except subprocess.TimeoutExpired:
            result['completion'] = 'process_stop_timeout'
        thread.join(timeout=1)
        if not thread.is_alive():
            process.stdout.close()
    if read_failed.is_set() and result['completion'] == 'complete':
        result['completion'] = 'read_error'
    result['counts'] = dict(sorted(counts.items()))
    return result


def main():
    if len(sys.argv) != 1:
        print(json.dumps({'diagnostic': 'fixed_window', 'error': 'invalid_arguments'}))
        return 2
    print(json.dumps({'diagnostic': 'chat_session', 'since': SINCE, 'until': UNTIL,
        'raw_logs_emitted': False, 'classification_is_cause_proof': False,
        'max_events_per_container': MAX_EVENTS, 'max_bytes_per_container': MAX_BYTES}))
    for container in CONTAINERS:
        result = collect(['docker', 'logs', '--timestamps', '--since', SINCE,
                          '--until', UNTIL, container])
        print(json.dumps({'container': container, **result}, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
