"""Compatibility shim for the legacy LifeHub reference Web shell.

The actual implementation lives in :mod:`academicos.lifehub.shells.reference_web`.
Engine/runtime code must never import this module.
"""

from academicos.lifehub.shells.reference_web import (
    CSS,
    JS,
    make_handler,
    render_review_inbox,
    render_workspace,
    serve,
)

__all__ = [
    "CSS",
    "JS",
    "make_handler",
    "render_review_inbox",
    "render_workspace",
    "serve",
]
