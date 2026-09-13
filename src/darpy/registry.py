"""Inspectable capability declarations, separate from dependency discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from .schemas import _string


class CapabilityState(StrEnum):
    NATIVE = "native"
    SCOPED = "scoped"
    PLANNED = "planned"


@dataclass(frozen=True, slots=True)
class Capability:
    """Declared implementation scope; availability is not parity evidence."""

    name: str
    state: CapabilityState
    summary: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _string(self.name, "name")
        _string(self.summary, "summary")
        if not isinstance(self.state, CapabilityState):
            raise TypeError("state must be a CapabilityState")
        if type(self.limitations) is not tuple:
            raise TypeError("limitations must be a tuple")
        for item in self.limitations:
            _string(item, "limitation")
        if self.state in (CapabilityState.SCOPED, CapabilityState.PLANNED) and not self.limitations:
            raise ValueError("Scoped and planned capabilities must declare limitations")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CapabilityRegistry:
    """Local, explicit registry. Duplicate names are rejected, never replaced."""

    def __init__(self) -> None:
        self._entries: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if not isinstance(capability, Capability):
            raise TypeError("capability must be a Capability")
        if capability.name in self._entries:
            raise ValueError(f"Capability already registered: {capability.name}")
        self._entries[capability.name] = capability

    def get(self, name: str) -> Capability:
        return self._entries[name]

    def list(self, *, state: CapabilityState | None = None) -> tuple[Capability, ...]:
        if state is not None and not isinstance(state, CapabilityState):
            raise TypeError("state must be a CapabilityState")
        return tuple(item for _, item in sorted(self._entries.items()) if state is None or item.state == state)


def default_registry() -> CapabilityRegistry:
    """Return fresh declarations without importing optional integrations."""
    registry = CapabilityRegistry()
    entries = (
        Capability(
            "runtime",
            CapabilityState.NATIVE,
            "Bounded cooperative asynchronous local execution",
            ("No process sandbox, token accounting, or automatic retry",),
        ),
        Capability("schemas", CapabilityState.NATIVE, "Versioned validated task, budget, and success receipts"),
        Capability(
            "teams",
            CapabilityState.SCOPED,
            "Named local runtimes with ordered task outcomes",
            ("Single process only; no distributed leases, durable queue, or consensus",),
        ),
        Capability(
            "improvement",
            CapabilityState.SCOPED,
            "Strict evidence comparison and versioned promotion records",
            ("No optimizer, training loop, evaluator execution, or evidence attestation",),
        ),
        Capability(
            "array",
            CapabilityState.SCOPED,
            "Immutable native arrays with scalar and same-shape operations",
            ("No full NumPy parity, arbitrary strides, fixed-width integer overflow, or native kernels",),
        ),
        Capability(
            "symbolic",
            CapabilityState.SCOPED,
            "Exact rational polynomial expressions and differentiation",
            ("No full SymPy parity, general solvers, or transcendental algebra",),
        ),
        Capability(
            "plot",
            CapabilityState.SCOPED,
            "Native line, scatter, bar, histogram, and deterministic SVG export",
            ("Single numeric linear Axes; no Matplotlib Artist, interactive, raster, or full API parity",),
        ),
        Capability(
            "matplotlib-parity",
            CapabilityState.PLANNED,
            "Tracked target for Matplotlib public feature, behavior, and rendering parity",
            ("Not implemented or certified; the plot module is a deliberately narrow native SVG subset",),
        ),
        Capability(
            "numpy-parity",
            CapabilityState.PLANNED,
            "Tracked target for NumPy public feature and behavior parity",
            ("Not implemented or certified; the array module is a deliberately narrow native subset",),
        ),
        Capability(
            "sympy-parity",
            CapabilityState.PLANNED,
            "Tracked target for SymPy public feature and behavior parity",
            ("Not implemented or certified; the symbolic module is a deliberately narrow native subset",),
        ),
        Capability(
            "distributed-swarm",
            CapabilityState.PLANNED,
            "Durable distributed task coordination",
            ("No distributed swarm implementation in this release",),
        ),
        Capability(
            "swe-agent",
            CapabilityState.PLANNED,
            "Repository editing, execution, and review workflow",
            ("Runtime handlers must be supplied by the application; no autonomous SWE implementation",),
        ),
    )
    for entry in entries:
        registry.register(entry)
    return registry


def capabilities() -> tuple[Capability, ...]:
    return default_registry().list()


__all__ = ["Capability", "CapabilityRegistry", "CapabilityState", "capabilities", "default_registry"]
