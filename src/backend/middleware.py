"""Security response-header middleware.

Stamps defense-in-depth headers on every response. Specifics:

- Content-Security-Policy: locks script/style to same-origin; permits the Lakeview
  dashboard and Genie Space as frame sources once they're embedded; permits calls
  out to the Stratego KA serving endpoint. Hosts are configurable via env so we
  can tune per workspace without code changes.
- X-Content-Type-Options: nosniff — stops browsers from guessing MIME types.
- X-Frame-Options: DENY — the cockpit is never legitimately framed
  (matches ``frame-ancestors 'none'`` in the CSP). SDR-4682 N-8.
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
            # SDR-4682 N-9: split style-src into block-level (strict) and
            # attribute-level (lenient). Tailwind compiles to a static stylesheet
            # at build time, so no <style> blocks are emitted at runtime; only
            # React's `style={...}` attribute on individual elements (e.g. the
            # dynamic engagement-quarter chart-bar widths) needs unsafe-inline,
            # and only at the attribute level. style-src-attr is a CSP3
            # directive — older browsers fall back to style-src and block both,
            # which is acceptable for an internal app on managed endpoints.
            "style-src 'self'",
            "style-src-attr 'unsafe-inline'",
            "img-src 'self' data:",
            f"connect-src {connect_src}",
            f"frame-src {frame_src}",
            "font-src 'self' data:",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            # SDR-4682 N-8: cockpit is never legitimately framed by anyone —
            # not even from the same origin. 'none' / DENY is the correct
            # posture; allowlist-by-env is intentionally absent so a future
            # operator can't loosen this without a code change.
            "frame-ancestors 'none'",
        ]
    )


SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    # SDR-4682 N-8: see frame-ancestors comment above. DENY is stricter than
    # SAMEORIGIN and matches the CSP intent.
    "X-Frame-Options": "DENY",
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
