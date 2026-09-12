from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Response, request


ROOT = Path(__file__).resolve().parents[1]
SECURITY_DB = ROOT / "server" / "data" / "security_events.db"


def _safe_json_error(message: str, status: int, extra: dict | None = None):
    payload = {
        "error": message,
        "status": status,
    }

    if extra:
        payload.update(extra)

    return Response(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        mimetype="application/json",
    )


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"

    return request.remote_addr or "unknown"


def _rate_key(group: str) -> str:
    return f"{group}:{_client_ip()}"


def _security_db_conn():
    SECURITY_DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(SECURITY_DB, timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=2000")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS security_rate_limit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_key TEXT NOT NULL,
            group_name TEXT NOT NULL,
            occurred_at REAL NOT NULL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_rate_limit_bucket_time
        ON security_rate_limit_events(bucket_key, occurred_at)
    """)

    conn.commit()
    return conn


def _rate_limit_for_request():
    path = request.path or "/"
    method = request.method.upper()

    if method == "POST" and path == "/login":
        return "login", 12, 10 * 60

    if method == "POST" and path == "/api/account-requests":
        return "account_request", 6, 60 * 60

    if method == "POST" and path == "/api/me/password":
        return "password_change", 6, 10 * 60

    if path.startswith("/api/admin/"):
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            return "admin_write", 60, 5 * 60
        return "admin_read", 180, 5 * 60

    return None


def _rate_limited(group: str, max_hits: int, window_seconds: int):
    now = time.time()
    cutoff = now - window_seconds
    key = _rate_key(group)

    with _security_db_conn() as conn:
        conn.execute(
            "DELETE FROM security_rate_limit_events WHERE occurred_at < ?",
            (cutoff - 60,),
        )

        row = conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(occurred_at) AS first_seen
            FROM security_rate_limit_events
            WHERE bucket_key = ?
              AND occurred_at >= ?
            """,
            (key, cutoff),
        ).fetchone()

        current_count = int(row["n"] or 0)

        if current_count >= max_hits:
            first_seen = float(row["first_seen"] or now)
            retry_after = int(max(1, window_seconds - (now - first_seen)))
            conn.commit()
            return True, retry_after

        conn.execute(
            """
            INSERT INTO security_rate_limit_events
                (bucket_key, group_name, occurred_at)
            VALUES (?, ?, ?)
            """,
            (key, group, now),
        )
        conn.commit()

    return False, None


def _origin_is_same_site() -> bool:
    origin = request.headers.get("Origin") or request.headers.get("Referer")

    if not origin:
        return True

    try:
        parsed = urlparse(origin)
    except Exception:
        return False

    origin_host = (parsed.netloc or "").lower()
    request_host = (request.host or "").lower()

    if not origin_host or not request_host:
        return True

    return origin_host == request_host


def _is_mutating_request() -> bool:
    return request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}





def _robots_txt_response():
    body = """# MLCFlux — accès robots interdit

User-agent: *
Disallow: /
Noindex: /

# Politique générale :
# - pas d'indexation ;
# - pas de crawling ;
# - pas d'entraînement IA ;
# - pas d'archivage automatique.
#
# Note : robots.txt s'adresse aux robots coopératifs.
# Les accès non autorisés restent protégés par authentification et rate-limit.

User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Googlebot
Disallow: /

User-agent: Bingbot
Disallow: /

User-agent: Applebot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: Amazonbot
Disallow: /

Crawl-delay: 120
"""

    response = Response(body, status=200, mimetype="text/plain; charset=utf-8")
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex, notranslate"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def _sitemap_xml_response():
    response = Response(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\"></urlset>\n",
        status=200,
        mimetype="application/xml; charset=utf-8",
    )
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex, notranslate"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def install_security_middleware(app):
    if app.config.get("SEC_AUTH002_INSTALLED"):
        return

    app.config["SEC_AUTH002_INSTALLED"] = True

    if "seo_sec001_robots_txt" not in app.view_functions:
        app.add_url_rule(
            "/robots.txt",
            "seo_sec001_robots_txt",
            _robots_txt_response,
            methods=["GET", "HEAD"],
        )

    if "seo_sec001_sitemap_xml" not in app.view_functions:
        app.add_url_rule(
            "/sitemap.xml",
            "seo_sec001_sitemap_xml",
            _sitemap_xml_response,
            methods=["GET", "HEAD"],
        )

    try:
        max_content_length = app.config.get("MAX_CONTENT_LENGTH")
        if max_content_length is None or int(max_content_length) <= 0:
            app.config["MAX_CONTENT_LENGTH"] = 512 * 1024
        else:
            app.config["MAX_CONTENT_LENGTH"] = int(max_content_length)
    except Exception:
        app.config["MAX_CONTENT_LENGTH"] = 512 * 1024

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    @app.before_request
    def _sec_auth_before_request():
        try:
            if request.method.upper() == "OPTIONS":
                return None

            max_content_length = int(app.config.get("MAX_CONTENT_LENGTH") or 512 * 1024)

            if request.content_length is not None and int(request.content_length) > max_content_length:
                return _safe_json_error("Requête trop volumineuse.", 413)

            if _is_mutating_request() and not _origin_is_same_site():
                return _safe_json_error("Origine de requête refusée.", 403)

            rate = _rate_limit_for_request()
            if rate:
                group, max_hits, window_seconds = rate
                limited, retry_after = _rate_limited(group, max_hits, window_seconds)

                if limited:
                    response = _safe_json_error("Trop de tentatives. Réessayez plus tard.", 429)
                    response.headers["Retry-After"] = str(retry_after)
                    return response

            return None

        except Exception as exc:
            app.logger.exception("security middleware before_request failed")
            return _safe_json_error(
                "Erreur de garde-fou sécurité.",
                500,
                {"detail": f"{type(exc).__name__}: {exc}"},
            )

    @app.after_request
    def _sec_auth_after_request(response):
        response.headers.setdefault(
            "X-Robots-Tag",
            "noindex, nofollow, noarchive, nosnippet, noimageindex, notranslate",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )

        path = request.path or ""
        if path.startswith("/api/admin/") or path.startswith("/api/me"):
            response.headers.setdefault("Cache-Control", "no-store")

        return response
