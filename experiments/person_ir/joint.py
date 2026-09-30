"""Host-approved multi-principal commit gate for a shared domain."""

from dataclasses import dataclass
from datetime import datetime

from .authority import AuthorityError, AuthorityStore
from .model import CommitRequest
from .state import CommitOutcome, StateStore


@dataclass(frozen=True)
class JointCommitOutcome:
    commit: CommitOutcome
    required_principals: tuple[str, ...]
    authority_ids: tuple[str, ...]


class JointCommitService:
    """Requires independently issued grants from every listed principal."""

    def __init__(self, required_principals: tuple[str, ...]):
        if (type(required_principals) is not tuple or len(required_principals) < 2 or
                len(set(required_principals)) != len(required_principals) or
                any(type(item) is not str or not item.strip()
                    for item in required_principals)):
            raise ValueError("at least two distinct principals required")
        self.required_principals = required_principals

    def commit(self, request: CommitRequest, state: StateStore,
               authority: AuthorityStore, handles: dict[str, object], *,
               agent: str, context: str | None = None,
               now: datetime | None = None) -> JointCommitOutcome:
        if (not isinstance(request, CommitRequest) or not isinstance(state, StateStore) or
                not isinstance(authority, AuthorityStore) or type(handles) is not dict):
            raise TypeError("host state, authority, handles and commit request required")
        if set(handles) != set(self.required_principals):
            raise AuthorityError("exact required principal grants missing")
        outcome = state.commit(
            request, authority, handles[self.required_principals[0]],
            principal=self.required_principals[0], agent=agent,
            context=context, now=now,
            additional_grants=tuple((principal, handles[principal])
                                    for principal in self.required_principals[1:]))
        return JointCommitOutcome(outcome, self.required_principals,
                                  outcome.receipt.authority_ids)
