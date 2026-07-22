# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import patch, AsyncMock
from tests.test_services_coverage import client

# Mocking enforce_permission (authentication & authorization bypass for test cases)
@patch("app.web.admin_api.enforce_permission", return_value={"username": "admin", "role": "admin"})
class TestAdminApi:
    def test_api_get_users(self, mock_enforce):
        response = client.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "users" in data

    def test_api_create_user(self, mock_enforce):
        payload = {"username": "new_test_user", "password": "1234", "role": "operator"}
        with patch("app.web.admin_api.create_user_account", new_callable=AsyncMock, return_value={"ok": True, "message": "Compte créé."}):
            response = client.post("/api/admin/users", json=payload)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_update_user(self, mock_enforce):
        payload = {"role": "manager", "is_active": True, "new_password": "4321"}
        with patch("app.web.admin_api.update_user_account", new_callable=AsyncMock, return_value={"ok": True, "message": "Mis à jour."}):
            response = client.put("/api/admin/users/1", json=payload)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_get_backups(self, mock_enforce):
        with patch("app.web.admin_api.list_restore_backups", return_value=[{"value": "b1", "label": "Backup 1"}]):
            response = client.get("/api/admin/backups")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "backups" in data
            assert "jobs" in data

    def test_api_trigger_backup(self, mock_enforce):
        with patch("app.web.admin_api.create_manual_backup", new_callable=AsyncMock, return_value={"ok": True, "message": "Sauvegarde lancée"}):
            response = client.post("/api/admin/backups")
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_restore_backup(self, mock_enforce):
        payload = {"backup_name": "backup.sql"}
        with patch("app.web.admin_api.restore_backup_by_value", new_callable=AsyncMock, return_value={"ok": True, "message": "Restauration effectuée"}):
            response = client.put("/api/admin/backups/restore", json=payload)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_save_backup_settings(self, mock_enforce):
        payload = {"gdrive_backup_dir": "C:\\", "backup_snapshot_time": "03:00", "backup_local_retention": 10, "backup_event_retention": 10}
        with patch("app.web.admin_api.save_backup_settings_from_form", new_callable=AsyncMock, return_value={"ok": True, "message": "Configuration sauvegardée"}):
            response = client.patch("/api/admin/backups/settings", json=payload)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_get_audit_logs(self, mock_enforce):
        response = client.get("/api/admin/audit?q=test")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "audit_logs" in data
        assert "activity_logs" in data

    def test_api_get_system_status(self, mock_enforce):
        response = client.get("/api/admin/system")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "status" in data
        assert "error_logs" in data

    def test_api_run_maintenance(self, mock_enforce):
        with patch("app.web.admin_api.run_database_maintenance", return_value={"ok": True, "message": "Maintenance terminée"}):
            response = client.post("/api/admin/maintenance")
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_save_sabrina_settings(self, mock_enforce):
        payload = {"chat_mode": "online", "gemini_model": "gemini-2.5-flash", "gemini_api_key": "dummy_key"}
        response = client.patch("/api/admin/sabrina/settings", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_api_delete_user_success(self, mock_enforce):
        with patch("app.web.admin_api.delete_user_account", new_callable=AsyncMock, return_value={"ok": True, "message": "Utilisateur supprimé."}):
            response = client.delete("/api/admin/users/999")
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_api_delete_self_fails(self, mock_enforce):
        with patch("app.web.admin_api.enforce_permission", return_value={"id": 1, "username": "admin", "role": "admin"}):
            response = client.delete("/api/admin/users/1")
            assert response.status_code == 200
            assert response.json()["ok"] is False
            assert "propre compte" in response.json()["message"]
