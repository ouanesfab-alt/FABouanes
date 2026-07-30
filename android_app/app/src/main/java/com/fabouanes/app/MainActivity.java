package com.fabouanes.app;

import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;

import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;

import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.SslErrorHandler;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import android.widget.Button;
import android.widget.FrameLayout;

import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private static final String TARGET_URL = "http://127.0.0.1:5000";
    private static final int FILE_CHOOSER_RESULT_CODE = 1001;

    private WebView webView;
    private ProgressBar progressBar;
    private SwipeRefreshLayout swipeRefreshLayout;
    private LinearLayout errorLayout;
    private ValueCallback<Uri[]> uploadMessage;
    private boolean isErrorState = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Styling Status Bar (Navy Blue #16253F)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(Color.parseColor("#16253F"));
        }

        // Parent FrameLayout
        FrameLayout rootLayout = new FrameLayout(this);
        rootLayout.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        rootLayout.setBackgroundColor(Color.parseColor("#F8FAFC"));

        // SwipeRefreshLayout
        swipeRefreshLayout = new SwipeRefreshLayout(this);
        swipeRefreshLayout.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        swipeRefreshLayout.setColorSchemeColors(Color.parseColor("#16253F"), Color.parseColor("#2563EB"));

        // WebView
        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        swipeRefreshLayout.addView(webView);
        rootLayout.addView(swipeRefreshLayout);

        // Top Horizontal Progress Bar
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        FrameLayout.LayoutParams pbParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dpToPx(4)
        );
        pbParams.gravity = Gravity.TOP;
        progressBar.setLayoutParams(pbParams);
        progressBar.setMax(100);
        progressBar.setProgress(0);

        rootLayout.addView(progressBar);

        // Custom Error Layout (Native Start/Retry Card)
        createErrorLayout();
        rootLayout.addView(errorLayout);

        setContentView(rootLayout);

        // Configure Clients
        setupWebViewClients();

        // Swipe Refresh Listener
        swipeRefreshLayout.setOnRefreshListener(() -> {
            if (isErrorState) {
                hideErrorView();
            }
            webView.reload();
        });

        // Initial Load
        webView.loadUrl(TARGET_URL);
    }

    private void setupWebViewClients() {
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.proceed(); // Accepte certificats SSL auto-signés
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                swipeRefreshLayout.setRefreshing(false);
                progressBar.setVisibility(View.GONE);
                if (!isErrorState) {
                    webView.setVisibility(View.VISIBLE);
                    hideErrorView();
                }
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                showErrorView();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    if (request.isForMainFrame()) {
                        showErrorView();
                    }
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress < 100) {
                    progressBar.setVisibility(View.VISIBLE);
                    progressBar.setProgress(newProgress);
                } else {
                    progressBar.setVisibility(View.GONE);
                }
            }

            // Support import de fichiers (Factures CSV, PDF, etc.)
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (uploadMessage != null) {
                    uploadMessage.onReceiveValue(null);
                    uploadMessage = null;
                }
                uploadMessage = filePathCallback;

                Intent intent = fileChooserParams.createIntent();
                try {
                    startActivityForResult(intent, FILE_CHOOSER_RESULT_CODE);
                } catch (ActivityNotFoundException e) {
                    uploadMessage = null;
                    Toast.makeText(MainActivity.this, "Aucun explorateur de fichiers disponible", Toast.LENGTH_LONG).show();
                    return false;
                }
                return true;
            }
        });
    }

    private void createErrorLayout() {
        errorLayout = new LinearLayout(this);
        errorLayout.setOrientation(LinearLayout.VERTICAL);
        errorLayout.setGravity(Gravity.CENTER);
        errorLayout.setBackgroundColor(Color.parseColor("#F8FAFC"));
        errorLayout.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        errorLayout.setPadding(dpToPx(24), dpToPx(24), dpToPx(24), dpToPx(24));
        errorLayout.setVisibility(View.GONE);

        // Icon Header Emoji / Graphic
        TextView iconTv = new TextView(this);
        iconTv.setText("🚀");
        iconTv.setTextSize(48);
        iconTv.setGravity(Gravity.CENTER);

        // Title
        TextView titleTv = new TextView(this);
        titleTv.setText("FABOuanes - Serveur non prêt");
        titleTv.setTextSize(20);
        titleTv.setTextColor(Color.parseColor("#1E293B"));
        titleTv.setGravity(Gravity.CENTER);
        titleTv.setPadding(0, dpToPx(16), 0, dpToPx(8));

        // Description
        TextView descTv = new TextView(this);
        descTv.setText("Le serveur local n'est pas encore démarré.\nLancez Termux et exécutez la commande 'fab'.");
        descTv.setTextSize(14);
        descTv.setTextColor(Color.parseColor("#64748B"));
        descTv.setGravity(Gravity.CENTER);
        descTv.setPadding(0, 0, 0, dpToPx(24));

        // Retry Button
        Button retryBtn = new Button(this);
        retryBtn.setText("🔄  Réessayer la connexion");
        retryBtn.setBackgroundColor(Color.parseColor("#16253F"));
        retryBtn.setTextColor(Color.WHITE);
        retryBtn.setPadding(dpToPx(16), dpToPx(12), dpToPx(16), dpToPx(12));
        retryBtn.setOnClickListener(v -> {
            hideErrorView();
            webView.loadUrl(TARGET_URL);
        });

        errorLayout.addView(iconTv);
        errorLayout.addView(titleTv);
        errorLayout.addView(descTv);
        errorLayout.addView(retryBtn);
    }

    private void showErrorView() {
        isErrorState = true;
        webView.setVisibility(View.GONE);
        swipeRefreshLayout.setRefreshing(false);
        errorLayout.setVisibility(View.VISIBLE);
    }

    private void hideErrorView() {
        isErrorState = false;
        errorLayout.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_RESULT_CODE) {
            if (uploadMessage == null) return;
            uploadMessage.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            uploadMessage = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private int dpToPx(int dp) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(dp * density);
    }
}


