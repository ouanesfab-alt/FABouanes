package com.fabouanes.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.net.http.SslError;
import android.os.Bundle;
import android.webkit.SslErrorHandler;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Déclencher le démarrage silencieux de Termux et PostgreSQL en arrière-plan
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.execute.PATH", "/data/data/com.termux/files/usr/bin/bash");
            intent.putExtra("com.termux.execute.ARGUMENTS", new String[]{"-c", "~/start_fab.sh"});
            intent.putExtra("com.termux.execute.BACKGROUND", true);
            startService(intent);
        } catch (Exception ignored) {}

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
        });

        // 3. Charger l'application localement en HTTPS
        webView.loadUrl("https://127.0.0.1:5000");
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
