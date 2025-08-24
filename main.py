import logging
import random
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import Endpoint, FailureRule, ProxyConfig, load_config


class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, proxy_server, config_path: str):
        self.proxy_server = proxy_server
        self.config_path = Path(config_path).resolve()

    def on_modified(self, event):
        if event.is_directory:
            return

        if Path(event.src_path).resolve() == self.config_path:
            self.proxy_server.reload_config()


class FailureInjector:
    def __init__(self):
        self.request_counts: Dict[str, int] = defaultdict(int)

    def should_inject_failure(self, rule: FailureRule, method: str, path: str) -> bool:
        condition = rule.condition

        # Check if the condition is enabled
        if not condition.enabled:
            return False

        if condition.method and condition.method.upper() != method.upper():
            return False

        key = f"{method}:{path}"
        self.request_counts[key] += 1

        if condition.count:
            if self.request_counts[key] != condition.count:
                return False

        if condition.every:
            if self.request_counts[key] % condition.every != 0:
                return False

        if condition.probability:
            if random.random() > condition.probability:
                return False

        if condition.delay:
            time.sleep(condition.delay / 1000.0)

        return True


class ProxyServer:
    def __init__(self, config: ProxyConfig, config_path: str = "config.yaml"):
        self.config = config
        self.config_path = config_path
        self.config_lock = threading.RLock()
        self.app = FastAPI(title="Debug Proxy Server", debug=config.server.debug)
        self.client = httpx.AsyncClient()
        self.failure_injector = FailureInjector()
        self.logger = self._setup_logging()
        self.observer = None
        self._setup_routes()
        self._setup_config_watcher()

    def _setup_logging(self) -> logging.Logger:
        logging.basicConfig(
            level=getattr(logging, self.config.logging.level),
            format=self.config.logging.format,
        )
        return logging.getLogger("proxy-server")

    def _setup_config_watcher(self):
        config_file = Path(self.config_path)
        if config_file.exists():
            event_handler = ConfigReloadHandler(self, self.config_path)
            self.observer = Observer()
            self.observer.schedule(
                event_handler, str(config_file.parent), recursive=False
            )
            self.observer.start()
            self.logger.info(f"Config file watcher started for {self.config_path}")

    def reload_config(self):
        try:
            with self.config_lock:
                new_config = load_config(self.config_path)
                self.config = new_config
                self.logger.info("Configuration reloaded successfully")

                # Update logging level if changed
                self.logger.setLevel(getattr(logging, new_config.logging.level))

        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")

    def _setup_routes(self):
        @self.app.api_route(
            "/{full_path:path}",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        )
        async def proxy_handler(request: Request, full_path: str):
            return await self._handle_request(request, full_path)

    def _find_matching_endpoint(self, path: str, method: str) -> Optional[Endpoint]:
        with self.config_lock:
            for endpoint in self.config.target.endpoints:
                if self._path_matches(endpoint.path, path) and self._method_matches(
                    endpoint.methods, method
                ):
                    return endpoint
            return None

    def _path_matches(self, pattern: str, path: str) -> bool:
        if pattern == "/*":
            return True

        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(f"^{regex_pattern}$", path))

        return pattern == path

    def _method_matches(self, allowed_methods: list, method: str) -> bool:
        return "*" in allowed_methods or method.upper() in [
            m.upper() for m in allowed_methods
        ]

    async def _handle_request(self, request: Request, full_path: str):
        path = f"/{full_path}"
        method = request.method

        endpoint = self._find_matching_endpoint(path, method)
        target = self.config.target

        if not endpoint:
            raise HTTPException(status_code=404, detail="No matching endpoint found")

        # Read request body early for logging and later use
        body = await request.body()

        # Log request details immediately, before any failure injection
        if endpoint and endpoint.debug:
            self.logger.info(f"[proxy] {method} {path} -> {target.url}")

            # Log request headers
            headers_str = "\n".join(
                [f"    {k}: {v}" for k, v in request.headers.items()]
            )
            self.logger.info(f"[proxy] Request headers:\n{headers_str}")

            # Log request body if present
            if body:
                try:
                    # Try to decode as UTF-8 text
                    body_str = body.decode("utf-8")
                    # Truncate very long bodies
                    if len(body_str) > 1000:
                        body_str = body_str[:1000] + "... (truncated)"
                    self.logger.info(f"[proxy] Request body:\n{body_str}")
                except UnicodeDecodeError:
                    self.logger.info(
                        f"[proxy] Request body: <binary data, {len(body)} bytes>"
                    )
            else:
                self.logger.info("[proxy] Request body: <empty>")

        # Check for failure injection after logging
        if endpoint:
            for rule in endpoint.failure_rules:
                if self.failure_injector.should_inject_failure(rule, method, path):
                    self.logger.warning(
                        f"[proxy] Injecting failure for {method} {path}: {rule.response.status_code}"
                    )
                    return JSONResponse(
                        status_code=rule.response.status_code,
                        content=rule.response.body or {},
                        headers=rule.response.headers or {},
                    )

        headers = dict(request.headers)

        if target.headers:
            headers.update(target.headers)

        # Remove host header to avoid conflicts
        headers.pop("host", None)

        target_url = f"{target.url.rstrip('/')}{path}"

        # Log actual request being sent to backend (after header modifications)
        if endpoint and endpoint.debug:
            self.logger.info(f"[proxy] Sending to backend: {method} {target_url}")

            # Log final headers that will be sent
            final_headers_str = "\n".join([f"    {k}: {v}" for k, v in headers.items()])
            self.logger.info(f"[proxy] Final request headers:\n{final_headers_str}")

            # Log query parameters if any
            if request.query_params:
                params_str = "\n".join(
                    [f"    {k}: {v}" for k, v in request.query_params.items()]
                )
                self.logger.info(f"[proxy] Query parameters:\n{params_str}")

        try:
            response = await self.client.request(
                method=method,
                url=target_url,
                headers=headers,
                content=body,
                params=dict(request.query_params),
            )

            if endpoint and endpoint.debug:
                self.logger.info(f"[proxy] Response: {response.status_code}")

                # Log response headers
                resp_headers_str = "\n".join(
                    [f"    {k}: {v}" for k, v in response.headers.items()]
                )
                self.logger.info(f"[proxy] Response headers:\n{resp_headers_str}")

                # Log response body if present
                if response.content:
                    try:
                        # Try to decode as UTF-8 text
                        resp_body_str = response.content.decode("utf-8")
                        # Truncate very long bodies
                        if len(resp_body_str) > 1000:
                            resp_body_str = resp_body_str[:1000] + "... (truncated)"
                        self.logger.info(f"[proxy] Response body:\n{resp_body_str}")
                    except UnicodeDecodeError:
                        self.logger.info(
                            f"[proxy] Response body: <binary data, {len(response.content)} bytes>"
                        )

            response_headers = dict(response.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("transfer-encoding", None)
            response_headers.pop("content-length", None)

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type"),
            )

        except httpx.RequestError as e:
            self.logger.error(f"[proxy] Request failed: {e}")
            raise HTTPException(status_code=502, detail=f"Bad Gateway: {str(e)}")

    def run(self):
        try:
            uvicorn.run(
                self.app,
                host=self.config.server.host,
                port=self.config.server.port,
                log_level=self.config.logging.level.lower(),
            )
        finally:
            if self.observer:
                self.observer.stop()
                self.observer.join()


def main():
    config_path = "config.yaml"
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        config_path = "config.example.yaml"
        config = load_config(config_path)

    server = ProxyServer(config, config_path)
    server.run()


if __name__ == "__main__":
    main()
