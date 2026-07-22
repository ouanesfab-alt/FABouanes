"""Module Assistant IA — Assistant agentique connecté à l'API Gemini."""
from app.modules.base import ModuleBase
from app.modules.assistant.web import router as web_router
from app.core.registry import register

class AssistantModule(ModuleBase):
    @property
    def name(self) -> str:
        return "assistant"

    @property
    def label(self) -> str:
        return "Assistant IA"

    @property
    def icon(self) -> str:
        return "bi-stars"

    @property
    def nav_order(self) -> int:
        return 90

    @property
    def web_router(self):
        return web_router

    @property
    def permissions(self) -> list[str]:
        return ["assistant.read", "assistant.write"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "admin": ["assistant.read", "assistant.write"],
            "manager": ["assistant.read", "assistant.write"],
            "operator": ["assistant.read", "assistant.write"],
        }

# Registration
register(AssistantModule())

# ── Plugin registry — expose assistant callables to app.core without hard imports ──
# This is the single place where assistant crosses the module/core boundary.
# app.core.worker and other core modules use registry.call("get_api_key") and
# registry.acall("get_embedding", ...) instead of importing these directly.
try:
    from app.core.plugin_registry import registry as _plugin_registry
    from app.modules.assistant.schema_context import get_gemini_api_key
    from app.modules.assistant.rag import get_embedding

    _plugin_registry.register("get_api_key", get_gemini_api_key)
    _plugin_registry.register("get_embedding", get_embedding)
except Exception as _e:
    import logging
    logging.getLogger("fabouanes.assistant").warning(
        "Assistant plugin registration skipped (non-critical): %s", _e
    )
