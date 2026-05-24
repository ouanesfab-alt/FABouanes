from fastapi import APIRouter

from app.web.admin_pages import router as admin_router
from app.web.auth_pages import router as auth_router
from app.web.client_pages import router as client_router
from app.web.contacts_pages import router as contacts_router
from app.web.dashboard_pages import router as dashboard_router
from app.web.operations_pages import router as operations_router
from app.web.production_pages import router as production_router
from app.web.report_pages import router as report_router
from app.web.search_pages import router as search_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(client_router)
router.include_router(contacts_router)
router.include_router(operations_router)
router.include_router(production_router)
router.include_router(admin_router)
router.include_router(report_router)
router.include_router(search_router)
