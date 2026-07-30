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
                    // Si le serveur est en train de démarrer, afficher une page de chargement et réessayer
                    showLoadingPage();
                    handler.postDelayed(() -> webView.loadUrl(APP_URL), 2000);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (url.startsWith(APP_URL)) {
                    isServerReady = true;
                }
            }
        });

        // 3. Charger l'application avec fallback
        showLoadingPage();
        webView.loadUrl(APP_URL);
    }

    private void startTermuxServer() {
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.execute.PATH", "/data/data/com.termux/files/usr/bin/bash");
            intent.putExtra("com.termux.execute.ARGUMENTS", new String[]{"-c", "~/start_fab.sh"});
            intent.putExtra("com.termux.execute.BACKGROUND", true);
            startService(intent);
        } catch (Exception ignored) {}
    }

    private void showLoadingPage() {
        String loadingHtml = "<html><body style='background:#16253F;color:white;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;margin:0;padding:20px;text-align:center;'>"
                + "<div style='font-size:42px;margin-bottom:15px;'>📦</div>"
                + "<h2 style='margin:0 0 10px 0;'>FABOuanes ERP</h2>"
                + "<p style='color:#A0AEC0;font-size:15px;margin:0;'>Démarrage du moteur et de la base de données en cours...</p>"
                + "<div style='margin-top:25px;border:3px solid #2B3649;border-top:3px solid #007AFF;border-radius:50%;width:30px;height:30px;animation:spin 1s linear infinite;'></div>"
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
