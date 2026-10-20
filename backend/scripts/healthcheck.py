"""Container health probe that follows the scheme the app is actually serving."""

from __future__ import annotations

import os
import ssl
import sys
import urllib.request

TIMEOUT_SECONDS = 5


def main() -> int:
    port = os.environ.get("UVICORN_PORT", "8000")
    scheme = "https" if os.environ.get("HTTPS_CERTFILE") else "http"
    url = f"{scheme}://localhost:{port}/api/health"

    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS, context=context) as response:
            return 0 if response.status == 200 else 1
    except Exception as exc:  # noqa: BLE001
        print(f"healthcheck: {url} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
