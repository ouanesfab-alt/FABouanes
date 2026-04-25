from tests.business_flow_case import *  # noqa: F401,F403


class SystemBusinessFlowTests(BusinessFlowTestCase):
    def test_admin_renders_button_switcher_sections(self) -> None:
        self._login()

        response = self.client.get("/admin")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="adminSwitchButtons"', body)
        self.assertIn('data-fab-switch-root', body)
        self.assertIn('id="adminSwitchPlaceholder"', body)
        for panel_id in (
            "adminCreateUser",
            "adminCloudBackup",
            "adminBackupActions",
            "adminUsers",
            "adminAuditLogs",
            "adminBackupJobs",
            "adminRecentActivity",
            "adminSystemLogs",
        ):
            self.assertIn(f'id="{panel_id}"', body)
            self.assertIn(f'data-fab-switch-target="{panel_id}"', body)
        self.assertEqual(body.count('class="fab-switch-btn"'), 8)
        self.assertEqual(body.count('class="card p-3 fab-switch-panel" hidden'), 8)
        self.assertIn('<th class="hide-mobile">Source</th>', body)
        self.assertIn('<th class="hide-mobile">Erreur</th>', body)

    def test_modular_route_handlers_are_registered_for_business_flows(self) -> None:
        self.assertEqual(app.view_functions["clients"].__module__, "fabouanes.routes.client_routes")
        self.assertEqual(app.view_functions["purchases"].__module__, "fabouanes.routes.purchase_routes")
        self.assertEqual(app.view_functions["sales"].__module__, "fabouanes.routes.sale_routes")
        self.assertEqual(app.view_functions["payments"].__module__, "fabouanes.routes.payment_routes")
        self.assertEqual(app.view_functions["production"].__module__, "fabouanes.routes.production_routes")
        self.assertEqual(app.view_functions["contacts"].__module__, "fabouanes.routes.contact_routes")
        self.assertEqual(app.view_functions["supplier_detail"].__module__, "fabouanes.routes.contact_routes")
        self.assertEqual(app.view_functions["operations"].__module__, "fabouanes.routes.transaction_routes")
        self.assertEqual(app.view_functions["transactions"].__module__, "fabouanes.routes.transaction_routes")
        self.assertEqual(app.view_functions["notes_page"].__module__, "fabouanes.routes.tools_routes")
        self.assertEqual(app.view_functions["pdf_reader"].__module__, "fabouanes.routes.tools_routes")
        self.assertEqual(app.view_functions["print_document"].__module__, "fabouanes.routes.print_routes")

    def test_ai_entry_points_are_removed(self) -> None:
        self._login()

        registered_rules = {rule.rule for rule in app.url_map.iter_rules()}
        assistant_response = self.client.get("/assistant")
        ai_config_response = self.client.get("/api/ai-config")
        web_search_response = self.client.get("/api/web-search?q=test")
        admin_response = self.client.get("/admin")

        self.assertNotIn("/assistant", registered_rules)
        self.assertNotIn("/api/assistant/chat", registered_rules)
        self.assertNotIn("/api/ai-config", registered_rules)
        self.assertNotIn("/api/web-search", registered_rules)
        self.assertEqual(assistant_response.status_code, 404)
        self.assertEqual(ai_config_response.status_code, 404)
        self.assertEqual(web_search_response.status_code, 404)
        self.assertEqual(admin_response.status_code, 200)
        self.assertNotIn("Configuration IA", admin_response.get_data(as_text=True))

    def test_operator_cannot_access_admin_panel(self) -> None:
        self._create_user("operator1", TEST_OPERATOR_PASSWORD, role="operator")
        self._login_as("operator1", TEST_OPERATOR_PASSWORD)

        response = self.client.get("/admin", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers.get("Location", ""))

    def test_audit_log_is_written_for_client_creation(self) -> None:
        self._login()

        response = self._post_form(
            "/clients/new",
            {
                "name": "Audit Client",
                "phone": "0550000000",
                "address": "Ouanes",
                "notes": "trace",
                "opening_credit": "15",
            },
            preflight_path="/clients/new",
        )

        self.assertEqual(response.status_code, 200)
        audit_row = self._fetchone(
            "SELECT action, entity_type, after_json, status FROM audit_logs WHERE action = 'create_client' ORDER BY id DESC",
            (),
        )
        self.assertIsNotNone(audit_row)
        self.assertEqual(str(audit_row["entity_type"]), "client")
        self.assertEqual(str(audit_row["status"]), "success")
        self.assertIn("Audit Client", str(audit_row["after_json"]))

    def test_api_login_returns_tokens_and_me_payload(self) -> None:
        self._create_user("manager1", TEST_MANAGER_PASSWORD, role="manager")

        auth_payload = self._api_login("manager1", TEST_MANAGER_PASSWORD)
        me_response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_payload['access_token']}"},
        )

        self.assertEqual(me_response.status_code, 200)
        me_payload = me_response.get_json()["data"]
        self.assertEqual(me_payload["username"], "manager1")
        self.assertEqual(me_payload["role"], "manager")
        self.assertIn("must_change_password", me_payload)
        refresh_row = self._fetchone("SELECT token_hint FROM api_refresh_tokens ORDER BY id DESC", ())
        self.assertIsNotNone(refresh_row)

    def test_api_permissions_distinguish_operator_and_manager_for_audit(self) -> None:
        self._create_user("manager2", TEST_MANAGER_PASSWORD, role="manager")
        self._create_user("operator2", TEST_OPERATOR_PASSWORD, role="operator")

        manager_auth = self._api_login("manager2", TEST_MANAGER_PASSWORD)
        operator_auth = self._api_login("operator2", TEST_OPERATOR_PASSWORD)
        manager_response = self.client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {manager_auth['access_token']}"},
        )
        operator_response = self.client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {operator_auth['access_token']}"},
        )

        self.assertEqual(manager_response.status_code, 200)
        self.assertEqual(operator_response.status_code, 403)

    def test_manual_backup_creates_queue_job(self) -> None:
        self._login()

        response = self._post_form(
            "/admin",
            {"action": "backup_now"},
            preflight_path="/admin",
        )

        self.assertEqual(response.status_code, 200)
        backup_job = self._fetchone("SELECT reason, status FROM backup_jobs ORDER BY id DESC", ())
        self.assertIsNotNone(backup_job)
        self.assertEqual(str(backup_job["reason"]), "manual")
        self.assertIn(str(backup_job["status"]), {"pending", "running", "success"})

    def test_backup_jobs_store_json_context(self) -> None:
        import json

        from fabouanes.services.backup_service import enqueue_backup_upload

        backup_path = TEST_ROOT / "manual_context_backup.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text("backup", encoding="utf-8")

        with app.app_context():
            job_id = enqueue_backup_upload(
                "manual",
                "event",
                backup_path,
                meta={"scheduled": False, "source": "test"},
            )

        backup_job = self._fetchone("SELECT context_json FROM backup_jobs WHERE id = ?", (job_id,))

        self.assertIsNotNone(backup_job)
        self.assertEqual(json.loads(str(backup_job["context_json"])), {"scheduled": False, "source": "test"})
        self.assertNotIn("'", str(backup_job["context_json"]))

    def test_admin_page_renders_simple_google_drive_folder_setup(self) -> None:
        self._login()
        registered_rules = {rule.rule for rule in app.url_map.iter_rules()}
        response = self.client.get("/admin")
        body = response.get_data(as_text=True)
        text = html.unescape(body)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/admin/google-drive/connect", registered_rules)
        self.assertNotIn("/admin/google-drive/callback", registered_rules)
        self.assertIn("Sauvegarde Google Drive", text)
        self.assertIn("Dossier Google Drive local", text)
        self.assertIn("Google Drive Desktop", text)
        self.assertNotIn("Google Client ID", text)
        self.assertNotIn("Google Client Secret", text)
        self.assertNotIn("Drive Folder ID", text)
        self.assertNotIn("Connecter Google Drive", text)
        self.assertNotIn("Configuration Google Cloud recommandee", text)
        self.assertNotIn("Authorized redirect URIs", text)
        self.assertNotIn("access_denied", text)

    def test_windows_builder_no_longer_requires_google_cloud_dependencies(self) -> None:
        build_script = (Path(__file__).resolve().parents[1] / "deploy" / "windows" / "COMPILER_EXE_AVEC_TESTS.bat").read_text(encoding="utf-8")

        self.assertNotIn("Verification des dependances cloud", build_script)
        self.assertNotIn("pip show google-auth", build_script)
        self.assertNotIn('--hidden-import "google.auth.transport.requests"', build_script)
        self.assertNotIn('--hidden-import "googleapiclient.discovery"', build_script)
        self.assertNotIn('--collect-submodules "googleapiclient"', build_script)
        self.assertIn('static\\FABOuanes_desktop.ico', build_script)
        self.assertIn("if not defined FAB_NO_PAUSE pause", build_script)

    def test_desktop_launcher_uses_splash_logo_and_desktop_icon(self) -> None:
        launcher_text = (Path(__file__).resolve().parents[1] / "launcher.py").read_text(encoding="utf-8")

        self.assertIn("desktop_logo_shield.png", launcher_text)
        self.assertIn("FABOuanes_desktop.ico", launcher_text)
        self.assertIn("show_startup_splash", launcher_text)
        self.assertIn("storage_path=str(WEBVIEW_STORAGE_DIR)", launcher_text)
        self.assertIn("desktop_install_state.json", launcher_text)
        self.assertIn("create_pre_migration_backup", launcher_text)
        self.assertIn('"--bootstrap-only"', launcher_text)
        self.assertIn('os.environ.get("FAB_HOST", "0.0.0.0")', launcher_text)

    def test_windows_installer_script_targets_desktop_user_install(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        setup_text = (project_root / "deploy" / "windows" / "FABOuanes_Setup.iss").read_text(encoding="utf-8")
        build_text = (project_root / "deploy" / "windows" / "BUILD_INSTALLATEUR_DESKTOP.bat").read_text(encoding="utf-8")

        self.assertIn(r"DefaultDirName={localappdata}\Programs\FABOuanes", setup_text)
        self.assertIn("PrivilegesRequired=lowest", setup_text)
        self.assertIn(r"SetupIconFile=..\..\static\FABOuanes_desktop.ico", setup_text)
        self.assertIn(r'Name: "{group}\Desinstaller FABOuanes"', setup_text)
        self.assertIn(r'Name: "{localappdata}\FABOuanes\webview"', setup_text)
        self.assertIn("RunDesktopBootstrap", setup_text)
        self.assertIn("--bootstrap-only --post-install", setup_text)
        self.assertIn("COMPILER_EXE_AVEC_TESTS.bat", build_text)
        self.assertIn("ISCC.exe", build_text)

    def test_desktop_performance_files_enable_cache_and_lazy_datagrids(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        perf_cache_text = (project_root / "fabouanes" / "core" / "perf_cache.py").read_text(encoding="utf-8")
        dashboard_repo_text = (project_root / "fabouanes" / "repositories" / "dashboard_repository.py").read_text(encoding="utf-8")
        admin_service_text = (project_root / "fabouanes" / "services" / "admin_service.py").read_text(encoding="utf-8")
        base_template_text = (project_root / "templates" / "base.html").read_text(encoding="utf-8")
        app_css_text = (project_root / "static" / "app.css").read_text(encoding="utf-8")
        app_js_text = (project_root / "static" / "app.js").read_text(encoding="utf-8")
        launcher_text = (project_root / "launcher.py").read_text(encoding="utf-8")

        self.assertIn("def cached_result(", perf_cache_text)
        self.assertIn('("dashboard_snapshot", resolved_date)', dashboard_repo_text)
        self.assertIn('("dashboard_kpis", target_date)', dashboard_repo_text)
        self.assertIn('("admin_view_data", filter_key)', admin_service_text)
        self.assertIn("app.css", base_template_text)
        self.assertIn("app.js", base_template_text)
        self.assertIn("requestIdleCallback", app_js_text)
        self.assertIn("fab:panel-open", app_js_text)
        self.assertIn("row.dataset.searchText", app_js_text)
        self.assertIn("body.desktop-app .table-scroll{scrollbar-gutter:auto;}", app_css_text)
        self.assertIn('{% set is_print_view = request.path.startswith(\'/print/\') or request.endpoint in [\'print_client_history\'] %}', base_template_text)
        self.assertIn('<body class="{% if is_desktop_app %}desktop-app {% endif %}{% if is_print_view %}print-route{% endif %}">', base_template_text)
        self.assertIn("html.desktop-app-root,body.desktop-app{height:100%;overflow:hidden;}", app_css_text)
        self.assertIn("body.desktop-app .app-content{", app_css_text)
        self.assertIn("!document.body.classList.contains('print-route')", base_template_text)
        self.assertIn("document.documentElement.classList.add('desktop-app-root');", base_template_text)
        self.assertIn("body.print-route .app-content{max-width:none;padding:0;height:auto;overflow:visible;animation:none;}", app_css_text)
        self.assertIn("body.print-route .alert{display:none!important;}", app_css_text)
        self.assertIn('os.environ.get("FAB_SERVER_THREADS"', launcher_text)

    def test_desktop_icon_assets_are_tightly_cropped_for_windows(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        for relative_path in ("static/desktop_logo_shield.png", "static/FABOuanes_desktop.ico"):
            with Image.open(project_root / relative_path) as source_image:
                image = source_image.convert("RGBA")
            alpha = image.getchannel("A").point(lambda value: 255 if value > 12 else 0)
            bbox = alpha.getbbox()
            self.assertIsNotNone(bbox, relative_path)
            width_ratio = (bbox[2] - bbox[0]) / image.width
            height_ratio = (bbox[3] - bbox[1]) / image.height
            self.assertGreater(width_ratio, 0.5, relative_path)
            self.assertGreater(height_ratio, 0.75, relative_path)
            center_x = ((bbox[0] + bbox[2]) / 2) / image.width
            center_y = ((bbox[1] + bbox[3]) / 2) / image.height
            self.assertLess(abs(center_x - 0.5), 0.04, relative_path)
            self.assertLess(abs(center_y - 0.5), 0.04, relative_path)

    def test_pwa_assets_include_offline_and_dashboard_start_url(self) -> None:
        manifest_response = self.client.get("/static/manifest.json")
        service_worker_response = self.client.get("/static/sw.js")
        offline_response = self.client.get("/static/offline.html")
        try:
            self.assertEqual(manifest_response.status_code, 200)
            self.assertEqual(service_worker_response.status_code, 200)
            self.assertEqual(offline_response.status_code, 200)
            manifest_body = manifest_response.get_data(as_text=True)
            sw_body = service_worker_response.get_data(as_text=True)
            self.assertIn('"start_url": "/dashboard"', manifest_body)
            self.assertIn("/static/offline.html", sw_body)
        finally:
            manifest_response.close()
            service_worker_response.close()
            offline_response.close()
