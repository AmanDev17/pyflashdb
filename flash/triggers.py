"""
pyflashdb — Trigger / hook system.

Provides before/after hooks for insert, update, delete, and select
operations on any table or collection — including MongoDB, which has
no native trigger support.

Usage (decorator style)
-----------------------
    @flash.before_insert("users")
    def validate(data):
        assert data.get("email"), "Email required"

    @flash.after_insert("users")
    def on_created(data, result):
        print(f"Created with ID: {result}")

Usage (programmatic)
--------------------
    flash.add_hook("before", "insert", "users", my_fn)
"""

from collections import defaultdict
from typing import Callable, Optional


class TriggerRegistry:
    """
    Stores and dispatches before/after hooks per (timing, event, table).

    Internal structure
    ------------------
    {
        "before": { "insert": { "users": [fn1, fn2], ... }, ... },
        "after":  { "insert": { "users": [fn3],      ... }, ... },
    }
    """

    VALID_EVENTS  = {"insert", "update", "delete", "select"}
    VALID_TIMINGS = {"before", "after"}

    def __init__(self):
        self._hooks: dict = {
            timing: defaultdict(lambda: defaultdict(list))
            for timing in self.VALID_TIMINGS
        }

    def register(self, timing: str, event: str, table: str, fn: Callable):
        """Register fn to be called at timing/event/table."""
        if timing not in self.VALID_TIMINGS:
            raise ValueError(
                f"Invalid timing {timing!r}. Choose from: {self.VALID_TIMINGS}"
            )
        if event not in self.VALID_EVENTS:
            raise ValueError(
                f"Invalid event {event!r}. Choose from: {self.VALID_EVENTS}"
            )
        self._hooks[timing][event][table].append(fn)

    def fire(self, timing: str, event: str, table: str, data, result=None):
        """
        Invoke all registered hooks for (timing, event, table).

        Before hooks receive: fn(data)
        After  hooks receive: fn(data, result)

        Exceptions raised inside hooks are caught and printed as warnings
        so they never abort the underlying database operation.
        """
        for fn in self._hooks[timing][event].get(table, []):
            try:
                if timing == "after":
                    fn(data, result)
                else:
                    fn(data)
            except Exception as exc:
                print(
                    f"[pyflashdb warning] Hook '{fn.__name__}' "
                    f"({timing}_{event}:{table}) raised: {exc}"
                )

    def clear(self, table: Optional[str] = None):
        """Remove all hooks, or hooks for a specific table only."""
        if table:
            for timing in self.VALID_TIMINGS:
                for event in self.VALID_EVENTS:
                    self._hooks[timing][event].pop(table, None)
        else:
            self.__init__()

    def list_hooks(self) -> dict:
        """Return a readable summary of all registered hooks."""
        summary = {}
        for timing in self.VALID_TIMINGS:
            for event in self.VALID_EVENTS:
                for tbl, fns in self._hooks[timing][event].items():
                    if fns:
                        summary[f"{timing}_{event}:{tbl}"] = [
                            fn.__name__ for fn in fns
                        ]
        return summary


def make_trigger_mixin():
    """
    Factory that returns a TriggerMixin class.

    Called once at FlashDB class-definition time. Each FlashDB *instance*
    calls _init_triggers() which creates its own TriggerRegistry, so hooks
    are strictly per-instance and never bleed between connections.
    """

    class TriggerMixin:

        def _init_triggers(self):
            """Create a fresh per-instance registry. Called from FlashDB.__init__."""
            self._triggers = TriggerRegistry()

        # ── Decorator API ──────────────────────────────────────────────────

        def before_insert(self, table: str):
            """Decorator: run fn(data) before add() / bulk_insert()."""
            def decorator(fn: Callable):
                self._triggers.register("before", "insert", table, fn)
                return fn
            return decorator

        def after_insert(self, table: str):
            """Decorator: run fn(data, result) after add() / bulk_insert()."""
            def decorator(fn: Callable):
                self._triggers.register("after", "insert", table, fn)
                return fn
            return decorator

        def before_update(self, table: str):
            """Decorator: run fn(payload) before update(). payload = {"filters":…,"data":…}"""
            def decorator(fn: Callable):
                self._triggers.register("before", "update", table, fn)
                return fn
            return decorator

        def after_update(self, table: str):
            """Decorator: run fn(payload, count) after update()."""
            def decorator(fn: Callable):
                self._triggers.register("after", "update", table, fn)
                return fn
            return decorator

        def before_delete(self, table: str):
            """Decorator: run fn(filters) before delete()."""
            def decorator(fn: Callable):
                self._triggers.register("before", "delete", table, fn)
                return fn
            return decorator

        def after_delete(self, table: str):
            """Decorator: run fn(filters, count) after delete()."""
            def decorator(fn: Callable):
                self._triggers.register("after", "delete", table, fn)
                return fn
            return decorator

        def before_select(self, table: str):
            """Decorator: run fn(payload) before all()/select()/where()."""
            def decorator(fn: Callable):
                self._triggers.register("before", "select", table, fn)
                return fn
            return decorator

        def after_select(self, table: str):
            """Decorator: run fn(payload, results) after any read operation."""
            def decorator(fn: Callable):
                self._triggers.register("after", "select", table, fn)
                return fn
            return decorator

        # ── Programmatic API ──────────────────────────────────────────────

        def add_hook(self, timing: str, event: str, table: str, fn: Callable):
            """Register a hook without using the decorator syntax."""
            self._triggers.register(timing, event, table, fn)

        def list_hooks(self) -> dict:
            """Return a dict summarising all registered hooks for this instance."""
            return self._triggers.list_hooks()

        def clear_hooks(self, table: Optional[str] = None):
            """Remove hooks — all of them, or only those for a specific table."""
            self._triggers.clear(table)

    return TriggerMixin