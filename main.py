"""Point d'entrée Android pour FABouanes (Kivy WebView + FastAPI embedded)."""
import os
import sys
import time
import threading
from pathlib import Path

# Définir l'environnement mobile
os.environ["FAB_DESKTOP"] = "1"
os.environ["FAB_HOST"] = "127.0.0.1"
os.environ["FAB_PORT"] = "5000"
os.environ["DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "1234"
os.environ["FAB_ALLOW_INSECURE_DEFAULT_ADMIN"] = "1"

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

def start_fastapi_server():
    """Démarre le serveur FastAPI uvicorn en arrière-plan."""
    try:
        import uvicorn
        from app.core.database import bootstrap_and_migrate
        from app.core.runtime_paths import ensure_runtime_dirs
        
        ensure_runtime_dirs()
        bootstrap_and_migrate()
        
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=5000,
            log_level="warning",
            access_log=False,
        )
    except Exception as e:
        print(f"FastAPI error: {e}", flush=True)

# Lancer FastAPI dans un thread démon
server_thread = threading.Thread(target=start_fastapi_server, daemon=True)
server_thread.start()

# Attendre 2 secondes que le serveur FastAPI s'allume sur le port 5000
time.sleep(2)

# Interface Android Kivy / WebView
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

class FABouanesAndroidApp(App):
    def build(self):
        self.icon = "static/icon_512.png"
        self.title = "FABouanes"
        
        layout = BoxLayout(orientation='vertical')
        
        if platform == 'android':
            try:
                from android.runnable import run_on_ui_thread
                from jnius import autoclass
                
                WebView = autoclass('android.webkit.WebView')
                WebViewClient = autoclass('android.webkit.WebViewClient')
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                
                @run_on_ui_thread
                def create_webview():
                    webview = WebView(activity)
                    webview.getSettings().setJavaScriptEnabled(True)
                    webview.getSettings().setDomStorageEnabled(True)
                    webview.getSettings().setAllowFileAccess(True)
                    webview.setWebViewClient(WebViewClient())
                    webview.loadUrl("http://127.0.0.1:5000")
                    activity.setContentView(webview)
                
                create_webview()
            except Exception as exc:
                print(f"Android WebView init error: {exc}", flush=True)
        else:
            # En développement local / fallback web-browser
            import webbrowser
            webbrowser.open("http://127.0.0.1:5000")
            
        return layout

if __name__ == "__main__":
    FABouanesAndroidApp().run()
