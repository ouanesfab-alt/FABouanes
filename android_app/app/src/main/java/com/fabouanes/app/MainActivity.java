package com.fabouanes.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean isServerReady = false;
    private static final String APP_URL = "https://127.0.0.1:5000";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Déclencher le démarrage silencieux de Termux et PostgreSQL en arrière-plan
        startTermuxServer();

        // 2. Initialiser le WebView plein écran
        webView = new WebView(this);
        setContentView(webView);

        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                // Accepter le certificat SSL auto-signé local (https://127.0.0.1:5000)
                handler.proceed();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame() && !isServerReady) {
                    showLoadingPage();
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (url != null && url.startsWith(APP_URL)) {
                    isServerReady = true;
                    handler.removeCallbacks(checkServerRunnable);
                }
            }
        });

        // 3. Charger l'application avec boucle active de vérification
        showLoadingPage();
        handler.post(checkServerRunnable);
    }

    private final Runnable checkServerRunnable = new Runnable() {
        @Override
        public void run() {
            if (!isServerReady && webView != null) {
                webView.loadUrl(APP_URL);
                handler.postDelayed(this, 2000);
            }
        }
    };

    private void startTermuxServer() {
        try {
            // Commande tout-en-un 0-IT :
            // 1. Configurer allow-external-apps = true
            // 2. Installer si première exécution (curl setup_termux.sh)
            // 3. Lancer le serveur (start_fab.sh)
            String autoSetupCmd = "mkdir -p ~/.termux && " +
                    "(grep -q 'allow-external-apps' ~/.termux/termux.properties 2>/dev/null || echo 'allow-external-apps = true' >> ~/.termux/termux.properties) && " +
                    "if [ ! -f ~/start_fab.sh ]; then curl -fsSL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh | bash; fi; " +
                    "~/start_fab.sh";

            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.execute.PATH", "/data/data/com.termux/files/usr/bin/bash");
            intent.putExtra("com.termux.execute.ARGUMENTS", new String[]{"-c", autoSetupCmd});
            intent.putExtra("com.termux.execute.BACKGROUND", true);
            startService(intent);
        } catch (Exception ignored) {}
    }

    private void showLoadingPage() {
        String loadingHtml = "<html><body style='background:#16253F;color:white;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;margin:0;padding:25px;text-align:center;'>"
                + "<div style='font-size:48px;margin-bottom:15px;'>📦</div>"
                + "<h2 style='margin:0 0 12px 0;font-weight:700;'>FABOuanes ERP</h2>"
                + "<p style='color:#A0AEC0;font-size:15px;margin:0 0 8px 0;line-height:1.5;'>Installation et démarrage automatique du serveur & base de données...</p>"
                + "<p style='color:#007AFF;font-size:13px;margin:0;font-weight:600;'>Configuration Zéro-IT en cours. Veuillez patienter...</p>"
                + "<div style='margin-top:30px;border:3.5px solid #2B3649;border-top:3.5px solid #007AFF;border-radius:50%;width:36px;height:36px;animation:spin 0.9s linear infinite;'></div>"
                + "<style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>"
                + "</body></html>";
        webView.loadDataWithBaseURL(null, loadingHtml, "text/html", "UTF-8", null);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
