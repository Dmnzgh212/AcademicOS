"""Experimental PersonIR; deliberately separate from the LifeHub kernel."""

from .model import Node, Program
from .runtime import Intent, Interpreter, Result, Value
from .verifier import VerificationError, verify

__all__ = [
    "Intent",
    "Interpreter",
    "Node",
    "Program",
    "Result",
    "Value",
    "VerificationError",
    "verify",
]
