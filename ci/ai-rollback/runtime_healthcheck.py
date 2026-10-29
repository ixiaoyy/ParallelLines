"""Run only inside the disposable, network-none compatibility API container.

All Settings sources except explicit synthetic initial values are disabled.
The original application factory is served on container loopback/port zero;
only the dependency-free /healthz route is requested. No migrations are run.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "/app")


def main() -> None:
    if not Path("/.dockerenv").is_file():
        raise RuntimeError("health check must run in the disposable Docker container")

    from app.core import config

    class IsolatedSettings(config.Settings):
        @classmethod
        def settings_customise_sources(
            cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
        ):
            # Never read inherited environment, .env, or file-secret sources.
            return (init_settings,)

    settings = IsolatedSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+asyncmy://synthetic:synthetic@127.0.0.1:1/no_database",
        redis_url="redis://127.0.0.1:1/15",
        jwt_secret_key="synthetic-isolated-container-validation-only-0001",
        public_site_url=None,
        web_app_shell_url=None,
    )
    config.get_settings = lambda: settings

    import uvicorn

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        "app.main:create_app", factory=True, host="127.0.0.1", port=0,
        loop="asyncio", lifespan="on", access_log=False, log_level="warning",
    ))
    failures = []

    def serve():
        try:
            server.run(sockets=[listener])
        except BaseException as exc:
            failures.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=serve, name="isolated-api-health", daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        health = None
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while time.monotonic() < deadline:
            if failures:
                raise RuntimeError(f"API startup failed: {failures[0]}")
            if not thread.is_alive():
                raise RuntimeError("API stopped before returning health")
            try:
                with http.open(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                    assert response.status == 200
                    health = json.load(response)
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.1)
        assert health == {"status": "ok", "service": "parallellines-api"}, (
            "dependency-free /healthz did not return the expected response before timeout"
        )
        result = {
            "status": "passed",
            "application_factory": "app.main:create_app",
            "health_path": "/healthz",
            "health_response": health,
            "bound_address": "127.0.0.1",
            "ephemeral_container_port": port,
            "settings_sources": ["explicit_synthetic_initial_values"],
            "dotenv_and_file_secrets_disabled": True,
            "database_endpoint": "synthetic container loopback port 1; no database supplied",
            "redis_endpoint": "synthetic container loopback port 1; no Redis supplied",
            "migration_upgrade_or_downgrade_called": False,
        }
        print("ROLLBACK_HEALTH_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("isolated API did not stop within five seconds")


if __name__ == "__main__":
    main()
