"""
Module Registry — Auto-discovery et enregistrement des feature modules.

Usage:
    # Dans app/modules/expenses/__init__.py :
    from app.core.registry import ModuleDescriptor, register
    register(ModuleDescriptor(name="expenses", label="Dépenses", ...))

    # Au démarrage (main.py) :
    from app.core.registry import discover_modules
    discover_modules(Path("app/modules"))
"""
from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field, InitVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter
    from app.modules.base import ModuleBase

logger = logging.getLogger("fabouanes.registry")


@dataclass
class ModuleDescriptor:
    """Décrit un feature module de l'application."""

    name: str  # Identifiant unique (ex: "catalog", "expenses")
    label: str  # Nom affiché en UI (ex: "Catalogue", "Dépenses")
    icon: str = "bi-box"  # Icône Bootstrap Icons
    nav_order: int = 100  # Ordre dans la navigation (plus petit = plus à gauche)
    schema_sql: list[str] = field(default_factory=list)  # DDL SQL du module
    permissions: list[str] = field(default_factory=list)  # Permissions déclarées
    role_permissions: dict[str, list[str]] = field(default_factory=dict)  # Permissions par rôle
    enabled: bool = True  # Peut être désactivé via env
    _module: "ModuleBase" | None = None  # Reference module pour resolution tardive

    def __init__(
        self,
        name: str,
        label: str,
        icon: str = "bi-box",
        nav_order: int = 100,
        schema_sql: list[str] | None = None,
        permissions: list[str] | None = None,
        role_permissions: dict[str, list[str]] | None = None,
        enabled: bool = True,
        _module: "ModuleBase" | None = None,
        web_router: APIRouter | None = None,
        api_router: APIRouter | None = None,
    ):
        self.name = name
        self.label = label
        self.icon = icon
        self.nav_order = nav_order
        self.schema_sql = schema_sql or []
        self.permissions = permissions or []
        self.role_permissions = role_permissions or {}
        self.enabled = enabled
        self._module = _module
        self._web_router = web_router
        self._api_router = api_router

    @property
    def web_router(self) -> APIRouter | None:
        if self._web_router is not None:
            return self._web_router
        if self._module is not None:
            return self._module.web_router
        return None

    @property
    def api_router(self) -> APIRouter | None:
        if self._api_router is not None:
            return self._api_router
        if self._module is not None:
            return self._module.api_router
        return None

    @classmethod
    def from_module(cls, module: "ModuleBase") -> ModuleDescriptor:
        return cls(
            name=module.name,
            label=module.label,
            icon=module.icon,
            nav_order=module.nav_order,
            schema_sql=module.schema_sql,
            permissions=module.permissions,
            role_permissions=getattr(module, "role_permissions", {}),
            _module=module,
        )


# ── Registre global ──
_modules: dict[str, ModuleDescriptor] = {}


def register(module: ModuleDescriptor | "ModuleBase") -> None:
    """Enregistre un module dans le registre global."""
    from app.modules.base import ModuleBase
    if isinstance(module, ModuleBase):
        descriptor = ModuleDescriptor.from_module(module)
    elif isinstance(module, ModuleDescriptor):
        descriptor = module
    else:
        raise TypeError(f"Expected ModuleBase or ModuleDescriptor, got {type(module)}")

    _modules[descriptor.name] = descriptor
    logger.info("Module registered: %s (%s)", descriptor.name, descriptor.label)




def get_module(name: str) -> ModuleDescriptor | None:
    """Récupère un module par son nom."""
    return _modules.get(name)


def get_all_modules() -> list[ModuleDescriptor]:
    """Retourne tous les modules triés par nav_order."""
    return sorted(_modules.values(), key=lambda m: m.nav_order)


def get_enabled_modules() -> list[ModuleDescriptor]:
    """Retourne uniquement les modules activés."""
    return [m for m in get_all_modules() if m.enabled]


def get_module_permissions() -> list[str]:
    """Collecte toutes les permissions déclarées par les modules."""
    perms: list[str] = []
    for module in get_all_modules():
        perms.extend(module.permissions)
    return perms


def discover_modules(modules_dir: Path) -> None:
    """Scanne app/modules/ et charge chaque package contenant un __init__.py.

    Chaque module doit appeler `register()` dans son __init__.py.
    Les modules listés dans FAB_MODULES_DISABLED sont désactivés.
    """
    if not modules_dir.is_dir():
        logger.debug("Modules directory not found: %s", modules_dir)
        return

    # Feature flags : désactivation via env
    disabled_raw = os.getenv("FAB_MODULES_DISABLED", "").strip()
    disabled_names = {
        name.strip().lower()
        for name in disabled_raw.split(",")
        if name.strip()
    }

    for child in sorted(modules_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "__init__.py").exists():
            continue

        module_name = child.name
        if module_name.startswith("_"):
            continue

        try:
            importlib.import_module(f"app.modules.{module_name}")
            logger.info("Discovered module: %s", module_name)

            # Appliquer les feature flags
            if module_name.lower() in disabled_names:
                mod = _modules.get(module_name)
                if mod:
                    mod.enabled = False
                    logger.info("Module disabled via env: %s", module_name)

        except Exception:
            logger.exception("Failed to load module: %s", module_name)


def mount_web_routes(parent_router: "APIRouter") -> int:
    """Monte les web_router de tous les modules activés. Retourne le nombre monté."""
    from fastapi import Depends
    from app.web.deps import verify_csrf_token
    count = 0
    for module in get_enabled_modules():
        if module.web_router:
            parent_router.include_router(module.web_router, dependencies=[Depends(verify_csrf_token)])
            count += 1
            logger.debug("Mounted web routes for module: %s", module.name)
    return count


def mount_api_routes(parent_router: "APIRouter") -> int:
    """Monte les api_router de tous les modules activés. Retourne le nombre monté."""
    count = 0
    for module in get_enabled_modules():
        if module.api_router:
            parent_router.include_router(module.api_router)
            count += 1
            logger.debug("Mounted API routes for module: %s", module.name)
    return count
