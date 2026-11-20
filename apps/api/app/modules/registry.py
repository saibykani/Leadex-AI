"""Auto-discovery of bounded-context modules.

Each package in app/modules may expose:
  - models.py  -> SQLAlchemy models (imported so Base.metadata is complete)
  - router.py  -> `router` (APIRouter) and optionally `extra_routers` (list[APIRouter]), mounted under /api/v1
New modules need no edits to main.py or alembic/env.py.
"""
import importlib
import pkgutil

import app.modules as _pkg


def _module_names() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(_pkg.__path__) if m.ispkg)


def import_models() -> None:
    for name in _module_names():
        try:
            importlib.import_module(f"app.modules.{name}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{name}.models":
                raise


def routers() -> list:
    found = []
    for name in _module_names():
        try:
            mod = importlib.import_module(f"app.modules.{name}.router")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{name}.router":
                raise
            continue
        if getattr(mod, "router", None) is not None:
            found.append(mod.router)
        found.extend(getattr(mod, "extra_routers", []))
    return found
