"""Isolated, exploratory PersonIR slice. Not part of the LifeHub kernel."""

from .model import Graph, Node, Observation
from .runtime import Interpreter
from .verifier import VerificationError, verify
from .authority import AuthorityStore, AuthorityError
from .state import StateStore, StaleProposal, InvalidProposal
from .effects import EffectService, FakeExecutor, InvalidEffect

__all__ = ["Graph", "Node", "Observation", "Interpreter", "VerificationError", "verify",
           "AuthorityStore", "AuthorityError", "StateStore", "StaleProposal", "InvalidProposal",
           "EffectService", "FakeExecutor", "InvalidEffect"]
