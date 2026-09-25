from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

TOKEN_ISSUER = "https://api.brightspace.com/auth"
TOKEN_AUDIENCE = "https://api.brightspace.com/auth/token"
LOCAL_STORAGE_KEY = "D2L.Fetch.Tokens"
XSRF_STORAGE_KEY = "XSRF.Token"
AUTH_SCOPE = "*:*:*"


class BrightspaceAuthError(RuntimeError):
    pass


def decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise BrightspaceAuthError("token is not a JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception as exc:
        raise BrightspaceAuthError("unable to decode token claims") from exc


def valid_token_claims(token: str, *, require_unexpired: bool = True) -> dict[str, Any] | None:
    try:
        claims = decode_jwt_claims(token)
    except BrightspaceAuthError:
        return None
    if claims.get("iss") != TOKEN_ISSUER or claims.get("aud") != TOKEN_AUDIENCE:
        return None
    exp = claims.get("exp")
    if not isinstance(exp, int):
        return None
    if require_unexpired and exp <= time.time():
        return None
    return claims


def _paths(auth_dir: Path) -> tuple[Path, Path]:
    return auth_dir / "token.json", auth_dir / "browser-profile"


def save_token(auth_dir: Path, token: str) -> Path:
    claims = valid_token_claims(token)
    if claims is None:
        raise BrightspaceAuthError("refusing to save an invalid or expired Brightspace token")
    token_file, _ = _paths(auth_dir)
    auth_dir.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        json.dumps(
            {
                "token": token,
                "exp": claims.get("exp"),
                "sub": claims.get("sub"),
                "tenant": claims.get("tenantid"),
                "captured_at": int(time.time()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return token_file


def load_saved_token(auth_dir: Path) -> str | None:
    token_file, _ = _paths(auth_dir)
    if not token_file.exists():
        return None
    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
        token = data.get("token")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return token if isinstance(token, str) and valid_token_claims(token) else None


def token_info(auth_dir: Path) -> dict[str, Any]:
    token_file, profile = _paths(auth_dir)
    if not token_file.exists():
        return {"status": "missing", "browser_profile": profile.exists()}
    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
        token = data.get("token", "")
        claims = valid_token_claims(token, require_unexpired=False)
    except Exception:
        claims = None
        data = {}
    if not claims:
        return {"status": "invalid", "browser_profile": profile.exists()}
    exp = int(claims["exp"])
    return {
        "status": "valid" if exp > time.time() else "expired",
        "expires_at": exp,
        "remaining_seconds": max(0, int(exp - time.time())),
        "user_id": data.get("sub") or claims.get("sub"),
        "tenant": data.get("tenant") or claims.get("tenantid"),
        "browser_profile": profile.exists(),
    }


def _token_from_local_storage(page):
    try:
        raw = page.evaluate(
            """key => { try { return window.localStorage.getItem(key); } catch { return null; } }""",
            LOCAL_STORAGE_KEY,
        )
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    best: tuple[int, str] | None = None
    for item in data.values() if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        token = item.get("access_token")
        claims = valid_token_claims(token) if isinstance(token, str) else None
        if not claims:
            continue
        candidate = (int(claims["exp"]), token)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def _request_token_in_page(page):
    """Ask Brightspace's own authenticated page for a bearer token.

    This POST is authentication/session refresh only; AcademicOS academic-data methods
    remain GET-only.
    """
    try:
        result = page.evaluate(
            """({xsrfKey, scope}) => (async () => {
                let xsrf = null;
                try { xsrf = window.localStorage.getItem(xsrfKey); } catch {}
                if (!xsrf) {
                    const r = await fetch('/d2l/lp/auth/xsrf-tokens', {credentials: 'include'});
                    if (!r.ok) return null;
                    const d = await r.json();
                    xsrf = d.referrerToken;
                }
                const r = await fetch('/d2l/lp/auth/oauth2/token', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Csrf-Token': xsrf,
                    },
                    body: `scope=${scope}`,
                });
                if (!r.ok) return null;
                return await r.json();
            })()""",
            {"xsrfKey": XSRF_STORAGE_KEY, "scope": AUTH_SCOPE},
        )
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    token = result.get("access_token")
    return token if isinstance(token, str) and valid_token_claims(token) else None


def _launch_persistent_context(playwright, profile: Path, *, headless: bool, channel: str):
    if channel == "auto":
        attempts = (None, "chrome", "msedge")
    elif channel == "chromium":
        attempts = (None,)
    else:
        attempts = (channel,)

    errors: list[str] = []
    for candidate in attempts:
        kwargs: dict[str, Any] = {
            "headless": headless,
            "viewport": {"width": 1280, "height": 900},
        }
        if candidate:
            kwargs["channel"] = candidate
        try:
            return playwright.chromium.launch_persistent_context(str(profile), **kwargs)
        except Exception as exc:
            errors.append(f"{candidate or 'chromium'}: {str(exc).splitlines()[0]}")
    raise BrightspaceAuthError("could not launch Chromium/Chrome/Edge: " + "; ".join(errors))


def capture_browser_token(
    *,
    host: str,
    auth_dir: Path,
    headless: bool = False,
    channel: str = "auto",
    wait_seconds: int | None = None,
) -> str:
    """Capture and locally save a Brightspace bearer token from a persistent browser session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrightspaceAuthError(
            'Playwright is required for browser login; install with pip install -e ".[brightspace]"'
        ) from exc

    _, profile = _paths(auth_dir)
    profile.mkdir(parents=True, exist_ok=True)
    captured: str | None = None
    timeout = wait_seconds if wait_seconds is not None else (30 if headless else 300)

    with sync_playwright() as playwright:
        context = _launch_persistent_context(
            playwright,
            profile,
            headless=headless,
            channel=channel,
        )

        def on_request(request) -> None:
            nonlocal captured
            auth = request.headers.get("authorization", "")
            if captured or not auth.startswith("Bearer eyJ"):
                return
            token = auth.removeprefix("Bearer ")
            if valid_token_claims(token):
                captured = token

        context.on("request", on_request)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(f"{host.rstrip('/')}/d2l/home", wait_until="domcontentloaded")
        deadline = time.time() + timeout
        try:
            while captured is None and time.time() < deadline:
                for candidate in reversed(context.pages or [page]):
                    captured = _token_from_local_storage(candidate) or _request_token_in_page(candidate)
                    if captured:
                        break
                if captured is None:
                    page.wait_for_timeout(500)
        finally:
            context.close()

    if captured is None:
        raise BrightspaceAuthError("no valid Brightspace token was captured")
    save_token(auth_dir, captured)
    return captured


def get_or_refresh_token(*, host: str, auth_dir: Path) -> str:
    token = load_saved_token(auth_dir)
    if token:
        return token
    return capture_browser_token(host=host, auth_dir=auth_dir, headless=True, channel="auto")
