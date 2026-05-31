from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.clients import router as clients_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.mobile_api import router as mobile_router
from app.api.v1.offline import router as offline_router
from app.api.v1.expenses import router as expenses_router
from app.api.v1.payments import router as payments_router
from app.api.v1.production import router as production_router
from app.api.v1.purchases import router as purchases_router
from app.api.v1.sales import router as sales_router
from app.api.ws import router as ws_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(mobile_router)
router.include_router(clients_router)
router.include_router(sales_router)
router.include_router(purchases_router)
router.include_router(payments_router)
router.include_router(production_router)
router.include_router(admin_router)
router.include_router(offline_router)
router.include_router(ws_router)
router.include_router(alerts_router)
router.include_router(expenses_router)
