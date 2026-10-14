# Backward compatibility shim — routes moved to app.modules.users.web
from app.modules.users.web import (  # noqa: F401
    change_password_page,
    change_password_submit,
    login_page,
    login_submit,
    logout,
    router,
)
