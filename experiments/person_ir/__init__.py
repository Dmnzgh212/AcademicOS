"""Isolated, exploratory PersonIR slice. Not part of the LifeHub kernel."""

from .model import Graph, Node, Observation
from .runtime import Interpreter
from .verifier import VerificationError, verify
from .authority import AuthorityStore, AuthorityError

__all__ = ["Graph", "Node", "Observation", "Interpreter", "VerificationError", "verify",
           "AuthorityStore", "AuthorityError"]
