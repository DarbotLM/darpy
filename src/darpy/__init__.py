"""DarbotLabs' dependency-free Python platform foundation.

Scientific and orchestration modules are imported explicitly to keep importing
the public task runtime inexpensive. Capability declarations expose scope.
"""

from .runtime import BudgetExceededError, Handler, RunBudget, RunResult, Runtime, Task

__version__ = "0.1.0"

__all__ = ["BudgetExceededError", "Handler", "RunBudget", "RunResult", "Runtime", "Task", "__version__"]
