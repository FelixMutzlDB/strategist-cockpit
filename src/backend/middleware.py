"""Security response-header middleware.

Stamps defense-in-depth headers on every response. Specifics:

- Content-Security-Policy: locks script/style to same-origin; permits the Lakeview
  dashboard and Genie Space as frame sources once they're embedded; permits calls
  out to the Stratego KA serving endpoint. Hosts are configurable via env so we
  can tune per workspace without code changes.
- X-Content-Type-Options: nosniff — stops browsers from guessing MIME types.
- X-Frame-Options: SAMEORIGIN — we're not iframe'd externally.
- Referrer-Policy: strict-origin-when-cross-origin — leaks no path info off-origin.
- Permissions-Policy: blocks camera/microphone/geolocation the app never uses.

CSP allow-lists come from CSP_FRAME_SRC / CSP_CONNECT_SRC env vars (space-separated
hosts). Leave them empty for the locked-down default.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def _build_csp() -> str:
    extra_frame = os.environ.get("CSP_FRAME_SRC", "").split()
    extra_connect = os.environ.get("CSP_CONNECT_SRC", "").split()
    frame_src = " ".join(["'self'", *extra_frame]) if extra_frame else "'none'"
    connect_src = " ".join(["'self'", *extra_connect])
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            # Tailwind emits inline style attributes at runtime; allow 'unsafe-inline'
            # for styles only. Scripts remain locked down.
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            f"connect-src {connect_src}",
            f"frame-src {frame_src}",
            "font-src 'self' data:",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'self'",
        ]
    )


SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        response.headers.setdefault("Content-Security-Policy", _build_csp())
        return response
