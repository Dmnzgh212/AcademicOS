"""Experimental PersonIR; deliberately separate from the LifeHub kernel."""

from .model import Node, Program
from .authority import AuthorityRegistry, Capability, CapabilityInfo
from .runtime import Intent, Interpreter, Result, Value
from .state import StateSnapshot, VersionedState
from .verifier import VerificationError, verify

__all__ = [
    "Intent",
    "Interpreter",
    "AuthorityRegistry",
    "Capability",
    "CapabilityInfo",
    "Node",
    "Program",
    "Result",
    "StateSnapshot",
    "Value",
    "VersionedState",
    "VerificationError",
    "verify",
]
