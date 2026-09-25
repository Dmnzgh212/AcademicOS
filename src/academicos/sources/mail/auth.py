from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

GRAPH_SCOPES = ["User.Read", "Mail.Read"]
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/organizations"


class MailAuthError(RuntimeError):
    pass


def acquire_graph_token(
    *,
    client_id: str,
    cache_path: Path,
    authority: str = DEFAULT_AUTHORITY,
    allow_interactive: bool = True,
    prompt: Callable[[str], None] | None = None,
) -> str:
    """Return a delegated Graph token, using local MSAL cache when possible.

    Only ``User.Read`` and ``Mail.Read`` are requested. If interactive device-code
    authentication is required, ``prompt`` is called before MSAL starts waiting.
    """
    try:
        import msal
    except ImportError as exc:
        raise MailAuthError('MSAL is required; install with pip install -e ".[mail]"') from exc

    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))

    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache,
    )

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])

    if not result and allow_interactive:
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
        if "user_code" not in flow:
            raise MailAuthError(f"unable to start Microsoft device flow: {flow}")
        message = str(flow.get("message") or "Open the Microsoft device-login page and enter the code shown.")
        if prompt:
            prompt(message)
        result = app.acquire_token_by_device_flow(flow)

    if cache.has_state_changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize(), encoding="utf-8")

    if not result or "access_token" not in result:
        detail = (result or {}).get("error_description") or "no cached token available"
        raise MailAuthError(detail)
    return result["access_token"]
