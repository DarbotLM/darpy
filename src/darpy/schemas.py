"""Versioned, dependency-free JSON contracts for local DARPy execution."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar, Literal, Self
from uuid import uuid4

SCHEMA_VERSION = "1.0"
ProtocolName = Literal["local", "mcp", "acp", "activity"]
PROTOCOLS = ("local", "mcp", "acp", "activity")


def _string(value: object, name: str, *, nonempty: bool = True) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value.strip():
        raise ValueError(f"{name} must be nonempty")


def _positive_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _finite(value: object, name: str, *, positive: bool = False) -> None:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a number")
    try:
        valid = math.isfinite(value)  # type: ignore[arg-type]
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0):  # type: ignore[operator]
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON number: {value}")


def _number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON number is outside finite floating-point range")
    return number


def strict_json_loads(value: str) -> Any:
    """Decode JSON, rejecting duplicate keys and nonfinite numeric values."""
    _string(value, "JSON text", nonempty=False)
    return json.loads(value, object_pairs_hook=_object_pairs, parse_constant=_constant, parse_float=_number)


class JsonContract:
    """Serialization mixin; constructors remain the authoritative validators."""

    schema_version: ClassVar[str] = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, **asdict(self)}  # type: ignore[arg-type]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), allow_nan=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        if not isinstance(value, dict):
            raise TypeError("Contract must be a JSON object")
        data = dict(value)
        if data.pop("schema_version", None) != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        allowed = {item.name for item in fields(cls)}  # type: ignore[arg-type]
        unknown = data.keys() - allowed
        if unknown:
            raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
        return cls(**data)

    @classmethod
    def from_json(cls, value: str) -> Self:
        return cls.from_dict(strict_json_loads(value))


@dataclass(frozen=True, slots=True)
class Task(JsonContract):
    """One immutable text request with an optional valid JSON payload.

    ``protocol`` records provenance; it does not invoke a protocol adapter.
    ``cwd`` is descriptive and never changes the process working directory.
    """

    prompt: str
    session_id: str
    protocol: ProtocolName = "local"
    cwd: str | None = None
    payload_json: str | None = None
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        _string(self.prompt, "prompt", nonempty=False)
        _string(self.session_id, "session_id")
        _string(self.request_id, "request_id")
        _string(self.protocol, "protocol")
        if self.protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {PROTOCOLS}")
        if self.cwd is not None:
            _string(self.cwd, "cwd")
        if self.payload_json is not None:
            strict_json_loads(self.payload_json)


@dataclass(frozen=True, slots=True)
class RunBudget(JsonContract):
    """Cooperative wall-clock deadline and Unicode character limits.

    The deadline includes the concurrency queue. Character limits count all
    task string fields and the handler output, respectively. They are not byte,
    token, memory, or model-spend limits.
    """

    timeout_seconds: float = 60.0
    max_input_chars: int = 1_000_000
    max_output_chars: int = 1_000_000

    def __post_init__(self) -> None:
        _finite(self.timeout_seconds, "timeout_seconds", positive=True)
        _positive_int(self.max_input_chars, "max_input_chars")
        _positive_int(self.max_output_chars, "max_output_chars")


@dataclass(frozen=True, slots=True)
class RunResult(JsonContract):
    """Successful execution receipt, not a judgment of output correctness."""

    request_id: str
    session_id: str
    protocol: ProtocolName
    text: str
    elapsed_seconds: float

    def __post_init__(self) -> None:
        _string(self.request_id, "request_id")
        _string(self.session_id, "session_id")
        _string(self.protocol, "protocol")
        if self.protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {PROTOCOLS}")
        _string(self.text, "text", nonempty=False)
        _finite(self.elapsed_seconds, "elapsed_seconds")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be nonnegative")


def schema(name: str) -> dict[str, Any]:
    """Return a fresh JSON Schema 2020-12 for a public execution contract.

    The embedded ``payload_json`` string additionally uses strict JSON parsing
    in Python; ``contentMediaType`` is an annotation in JSON Schema.
    """
    nonempty = {"type": "string", "minLength": 1, "pattern": r"\S"}
    protocol = {"type": "string", "enum": list(PROTOCOLS)}
    properties: dict[str, Any] = {"schema_version": {"const": SCHEMA_VERSION}}
    if name == "Task":
        required = ["prompt", "session_id"]
        properties.update(
            prompt={"type": "string"},
            session_id=nonempty,
            request_id=nonempty,
            protocol=protocol,
            cwd={"anyOf": [nonempty, {"type": "null"}]},
            payload_json={"anyOf": [{"type": "string", "contentMediaType": "application/json"}, {"type": "null"}]},
        )
    elif name == "RunBudget":
        required = []
        properties.update(
            timeout_seconds={"type": "number", "exclusiveMinimum": 0, "default": 60.0},
            max_input_chars={"type": "integer", "minimum": 1, "default": 1_000_000},
            max_output_chars={"type": "integer", "minimum": 1, "default": 1_000_000},
        )
    elif name == "RunResult":
        required = ["request_id", "session_id", "protocol", "text", "elapsed_seconds"]
        properties.update(
            request_id=nonempty,
            session_id=nonempty,
            protocol=protocol,
            text={"type": "string"},
            elapsed_seconds={"type": "number", "minimum": 0},
        )
    else:
        raise ValueError(f"Unknown schema {name!r}; choose Task, RunBudget, or RunResult")
    # JSON round-trip prevents aliases among reusable property definitions.
    return json.loads(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"urn:darpy:schema:{SCHEMA_VERSION}:{name}",
                "title": name,
                "type": "object",
                "properties": properties,
                "required": ["schema_version", *required],
                "additionalProperties": False,
            }
        )
    )
