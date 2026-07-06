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
