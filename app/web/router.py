from fastapi import APIRouter, Depends

from app.modules.accounting.web import router as operations_router
from app.modules.admin.api import router as admin_api_router
from app.modules.admin.web import router as admin_router
from app.modules.clients.web import router as clients_router
from app.modules.reports.web import router as report_router
from app.modules.users.web import router as auth_router
from app.web.dashboard_pages import router as dashboard_router
from app.web.deps import verify_csrf_token
from app.web.manual_pages import router as manual_router
from app.web.search_pages import router as search_router

router = APIRouter()
router.include_router(auth_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(dashboard_router)
router.include_router(clients_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(operations_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(admin_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(admin_api_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(report_router, dependencies=[Depends(verify_csrf_token)])
router.include_router(search_router)
router.include_router(manual_router)
