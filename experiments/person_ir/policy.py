"""Host-approved, domain-neutral preconditions for new fake effects."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .model import EffectRequest
from .runtime import _json_value


class PolicyRejected(PermissionError):
    pass


@dataclass(frozen=True)
class Evidence:
    value: Any
    observed_at: datetime


@dataclass(frozen=True)
class NumberBetween:
    path: tuple[str | int, ...]
    minimum: int | float
    maximum: int | float


@dataclass(frozen=True)
class ComparePaths:
    left: tuple[str | int, ...]
    right: tuple[str | int, ...]
    relation: str  # eq | gt


@dataclass(frozen=True)
class DestinationEquals:
    path: tuple[str | int, ...]


@dataclass(frozen=True)
class FreshEvidence:
    source_ref: str
    path: tuple[str | int, ...]
    max_age: timedelta


def _at(value: Any, path: tuple[str | int, ...]) -> Any:
    if type(path) is not tuple:
        raise PolicyRejected("invalid policy path")
    try:
        for key in path:
            if type(value) is list and type(key) is int and 0 <= key < len(value):
                value = value[key]
            elif type(value) is dict and type(key) is str:
                value = value[key]
            else:
                raise KeyError(key)
        return value
    except (KeyError, IndexError) as exc:
        raise PolicyRejected("policy path not present") from exc


class EffectPolicy:
    """Trusted host configuration; extension-authored rules are not authority."""

    def __init__(self, rules: tuple):
        if type(rules) is not tuple or any(type(rule) not in {
                NumberBetween, ComparePaths, DestinationEquals, FreshEvidence}
                for rule in rules):
            raise ValueError("unsupported policy rule")
        self.rules = rules

    def evaluate(self, request: EffectRequest, current: dict[str, Evidence] | None,
                 *, now: datetime) -> None:
        if not isinstance(request, EffectRequest) or not isinstance(now, datetime) or now.tzinfo is None:
            raise PolicyRejected("effect and aware evaluation time required")
        payload = _json_value(request.payload)
        current = {} if current is None else current
        if type(current) is not dict:
            raise PolicyRejected("host evidence map required")
        for rule in self.rules:
            if type(rule) is NumberBetween:
                value = _at(payload, rule.path)
                if (type(value) not in (int, float) or
                        type(rule.minimum) not in (int, float) or
                        type(rule.maximum) not in (int, float) or
                        not rule.minimum <= value <= rule.maximum):
                    raise PolicyRejected("number outside approved bounds")
            elif type(rule) is ComparePaths:
                left, right = _at(payload, rule.left), _at(payload, rule.right)
                if rule.relation == "eq":
                    accepted = type(left) is type(right) and left == right
                elif rule.relation == "gt":
                    accepted = type(left) in (int, float) and type(right) in (int, float) and left > right
                else:
                    raise PolicyRejected("unsupported comparison")
                if not accepted:
                    raise PolicyRejected("payload relation failed")
            elif type(rule) is DestinationEquals:
                if _at(payload, rule.path) != request.destination:
                    raise PolicyRejected("payload destination mismatch")
            else:
                evidence = current.get(rule.source_ref)
                if (rule.source_ref not in request.sources or
                        not isinstance(evidence, Evidence) or
                        not isinstance(evidence.observed_at, datetime) or
                        evidence.observed_at.tzinfo is None or
                        not isinstance(rule.max_age, timedelta) or
                        rule.max_age <= timedelta(0)):
                    raise PolicyRejected("fresh host evidence required")
                age = now.astimezone(timezone.utc) - evidence.observed_at.astimezone(timezone.utc)
                if (age < timedelta(0) or age > rule.max_age or
                        _at(payload, rule.path) != _json_value(evidence.value)):
                    raise PolicyRejected("evidence stale or no longer matches")
