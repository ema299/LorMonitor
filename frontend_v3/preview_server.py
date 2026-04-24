#!/usr/bin/env python3
"""
Lorcana Monitor V3 — local preview server.

Serves files from this ``frontend_v3/`` directory and reverse-proxies
``/api/*`` to the live FastAPI backend (default ``http://127.0.0.1:8100``).
The live dashboard on port 8100 and the files under ``frontend/`` are never
touched.

Usage::

    python3 frontend_v3/preview_server.py
    python3 frontend_v3/preview_server.py --port 8103
    python3 frontend_v3/preview_server.py --host 0.0.0.0 --port 8103
"""

from __future__ import annotations

import argparse
import http.client
import http.server
import logging
import mimetypes
import posixpath
import socketserver
import sys
import urllib.parse
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_INDEX = "dashboard.html"
DEFAULT_UPSTREAM = "http://127.0.0.1:8100"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8103
UPSTREAM_TIMEOUT = 20

FORWARD_REQ_HEADERS = frozenset({
    "accept",
    "accept-encoding",
    "accept-language",
    "authorization",
    "content-type",
    "cookie",
    "referer",
    "user-agent",
})

DROP_RESP_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
})


def build_handler(root: Path, upstream_host: str, upstream_port: int, upstream_scheme: str):
    class PreviewHandler(http.server.BaseHTTPRequestHandler):
        server_version = "LorcanaV3Preview/1.0"

        def log_message(self, fmt, *args):
            logging.info("%s - %s", self.address_string(), fmt % args)

        def _is_api(self) -> bool:
            p = self.path or ""
            return p == "/api" or p.startswith("/api/") or p.startswith("/api?")

        def do_GET(self):
            return self._dispatch("GET")

        def do_HEAD(self):
            return self._dispatch("HEAD")

        def do_POST(self):
            return self._dispatch("POST", has_body=True)

        def do_PUT(self):
            return self._dispatch("PUT", has_body=True)

        def do_DELETE(self):
            return self._dispatch("DELETE")

        def do_PATCH(self):
            return self._dispatch("PATCH", has_body=True)

        def do_OPTIONS(self):
            return self._dispatch("OPTIONS")

        def _dispatch(self, method: str, has_body: bool = False):
            if self._is_api():
                return self._proxy(method, has_body=has_body)
            if method in ("GET", "HEAD"):
                return self._serve_static(method)
            self.send_error(405, "static root is read-only")

        def _resolve_under_root(self, raw_path: str) -> Path | None:
            try:
                parsed = urllib.parse.urlsplit(raw_path)
                decoded = urllib.parse.unquote(parsed.path or "/")
            except Exception:
                return None

            normalised = posixpath.normpath(decoded)
            if normalised.startswith("../") or normalised == "..":
                return None

            rel = normalised.lstrip("/") or DEFAULT_INDEX
            candidate_raw = root / rel
            try:
                candidate = candidate_raw.resolve(strict=False)
            except (OSError, RuntimeError):
                return None
            try:
                candidate.relative_to(root)
            except ValueError:
                return None
            return candidate

        def _serve_static(self, method: str):
            fs_path = self._resolve_under_root(self.path)
            if fs_path is None:
                return self.send_error(403, "Forbidden path")
            if fs_path.is_dir():
                fs_path = fs_path / DEFAULT_INDEX
                try:
                    fs_path.resolve(strict=False).relative_to(root)
                except (OSError, ValueError):
                    return self.send_error(403, "Forbidden path")
            if not fs_path.is_file():
                return self.send_error(404, "Not found")

            ctype = mimetypes.guess_type(fs_path.name)[0] or "application/octet-stream"
            try:
                data = fs_path.read_bytes()
            except OSError as exc:
                logging.warning("static read error: %s", exc)
                return self.send_error(500, "Read error")

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("X-V3-Preview", "1")
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(data)

        def _proxy(self, method: str, has_body: bool = False):
            outgoing = {}
            for key, value in self.headers.items():
                if key.lower() in FORWARD_REQ_HEADERS:
                    outgoing[key] = value
            outgoing["Host"] = f"{upstream_host}:{upstream_port}"

            body: bytes | None = None
            if has_body:
                try:
                    length = int(self.headers.get("Content-Length", "0") or "0")
                except ValueError:
                    length = 0
                if length > 0:
                    body = self.rfile.read(length)

            try:
                if upstream_scheme == "https":
                    conn = http.client.HTTPSConnection(upstream_host, upstream_port, timeout=UPSTREAM_TIMEOUT)
                else:
                    conn = http.client.HTTPConnection(upstream_host, upstream_port, timeout=UPSTREAM_TIMEOUT)
                conn.request(method, self.path, body=body, headers=outgoing)
                resp = conn.getresponse()
                resp_headers = resp.getheaders()
                resp_body = resp.read()
            except (OSError, http.client.HTTPException) as exc:
                logging.warning("proxy error for %s %s: %s", method, self.path, exc)
                return self.send_error(502, f"Upstream error: {exc}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self.send_response(resp.status, resp.reason)
            saw_content_length = False
            for key, value in resp_headers:
                if key.lower() in DROP_RESP_HEADERS:
                    continue
                if key.lower() == "content-length":
                    saw_content_length = True
                self.send_header(key, value)
            if not saw_content_length and method != "HEAD":
                self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(resp_body)

    return PreviewHandler


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def parse_upstream(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme or "http"
    if scheme not in ("http", "https"):
        raise SystemExit(f"unsupported upstream scheme: {scheme}")
    host = parsed.hostname
    if not host:
        raise SystemExit(f"invalid upstream host in URL: {url!r}")
    default_port = 443 if scheme == "https" else 80
    port = parsed.port or default_port
    return scheme, host, port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Static + /api proxy preview for Lorcana Monitor V3.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"bind host (default {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"bind port (default {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--upstream",
        default=DEFAULT_UPSTREAM,
        help=f"upstream base URL for /api proxy (default {DEFAULT_UPSTREAM})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable DEBUG level logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    root = HERE
    if root.name != "frontend_v3":
        logging.error("refusing to start: root (%s) does not end with 'frontend_v3'", root)
        return 2
    entry = root / DEFAULT_INDEX
    if not entry.is_file():
        logging.error("refusing to start: %s not found under %s", DEFAULT_INDEX, root)
        return 2

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logging.warning("binding on %s is non-loopback; only do this if you know why", args.host)

    scheme, up_host, up_port = parse_upstream(args.upstream)
    handler_cls = build_handler(root, up_host, up_port, scheme)
    server = ThreadingServer((args.host, args.port), handler_cls)

    logging.info("preview server ready")
    logging.info("  static root  : %s", root)
    logging.info("  default page : /%s", DEFAULT_INDEX)
    logging.info("  listening on : http://%s:%d", args.host, args.port)
    logging.info("  /api proxy   : %s://%s:%d", scheme, up_host, up_port)
    logging.info("press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("stopping on SIGINT")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
