package com.fabouanes.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private FrameLayout mainRoot;
    
    // UI selection screen components
    private ScrollView selectionView;
    private EditText ipEditText;
    
    // Loading screen components
    private FrameLayout loadingView;
    private TextView statusTextView;
    private Button settingsButton;

    private String selectedMode = ""; // "local" or "external"
    private String targetUrl = "http://localhost:5000";
    
    private boolean isLoaded = false;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int attemptCount = 0;
    
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        
        prefs = getSharedPreferences("FABouanesPrefs", Context.MODE_PRIVATE);
        selectedMode = prefs.getString("selected_mode", "");
        targetUrl = prefs.getString("target_url", "http://localhost:5000");

        // 1. Root Layout
        mainRoot = new FrameLayout(this);
        mainRoot.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        setContentView(mainRoot);

        // 2. Create the WebView
        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        webView.setVisibility(View.GONE);
        configureWebView();
        mainRoot.addView(webView);

        // 3. Create Selection Screen UI
        createSelectionUI();
        mainRoot.addView(selectionView);

        // 4. Create Loading UI
        createLoadingUI();
        mainRoot.addView(loadingView);

        // 5. Navigate based on stored preference
        if (!selectedMode.isEmpty()) {
            startApplicationFlow();
        } else {
            showSelectionScreen();
        }
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                if (!isLoaded) {
                    isLoaded = true;
                    webView.setVisibility(View.VISIBLE);
                    loadingView.setVisibility(View.GONE);
                    selectionView.setVisibility(View.GONE);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    if (selectedMode.equals("local")) {
                        retryLoading();
                    } else {
                        statusTextView.setText("Erreur de connexion au serveur externe.\nVérifiez l'adresse et assurez-vous que le serveur est démarré.");
                        settingsButton.setVisibility(View.VISIBLE);
                    }
                }
            }
        });
    }

    private void createSelectionUI() {
        selectionView = new ScrollView(this);
        selectionView.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        selectionView.setBackgroundColor(0xFF0F172A); // Dark slate 900
        selectionView.setVisibility(View.GONE);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER_HORIZONTAL);
        layout.setPadding(40, 80, 40, 80);
        layout.setLayoutParams(new ScrollView.LayoutParams(-1, -2));

        // Title
        TextView title = new TextView(this);
        title.setText("FABouanes Mobile");
        title.setTextColor(0xFFF8FAFC); // White slate 50
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, 10);
        
        TextView subtitle = new TextView(this);
        subtitle.setText("Choisissez comment vous connecter au serveur :");
        subtitle.setTextColor(0xFF94A3B8); // Slate 400
        subtitle.setTextSize(14);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, 0, 0, 80);

        layout.addView(title);
        layout.addView(subtitle);

        // Local Server Card Button
        Button localButton = createOptionButton("💻 Mode Serveur Local", "Démarre la base de données et l'application sur ce smartphone via Termux.");
        localButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                savePreferences("local", "http://localhost:5000");
                startApplicationFlow();
            }
        });
        layout.addView(localButton);

        // Separator
        TextView orText = new TextView(this);
        orText.setText("OU");
        orText.setTextColor(0xFF64748B);
        orText.setGravity(Gravity.CENTER);
        orText.setPadding(0, 40, 0, 40);
        layout.addView(orText);

        // External Server Card Container
        LinearLayout extContainer = new LinearLayout(this);
        extContainer.setOrientation(LinearLayout.VERTICAL);
        extContainer.setPadding(30, 30, 30, 30);
        
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(0xFF1E293B); // Slate 800
        gd.setCornerRadius(20);
        gd.setStroke(2, 0xFF334155);
        extContainer.setBackground(gd);

        TextView extTitle = new TextView(this);
        extTitle.setText("🌐 Serveur Externe");
        extTitle.setTextColor(0xFFE2E8F0);
        extTitle.setTextSize(18);
        extTitle.setPadding(0, 0, 0, 20);
        extContainer.addView(extTitle);

        ipEditText = new EditText(this);
        ipEditText.setHint("Ex: http://192.168.1.10:5000");
        ipEditText.setHintTextColor(0xFF64748B);
        ipEditText.setTextColor(Color.WHITE);
        ipEditText.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        ipEditText.setPadding(20, 20, 20, 20);
        GradientDrawable inputGd = new GradientDrawable();
        inputGd.setColor(0xFF0F172A);
        inputGd.setCornerRadius(10);
        inputGd.setStroke(2, 0xFF334155);
        ipEditText.setBackground(inputGd);
        extContainer.addView(ipEditText);

        Button connectExtButton = new Button(this);
        connectExtButton.setText("Se connecter");
        connectExtButton.setBackgroundColor(0xFF3B82F6); // Blue 500
        connectExtButton.setTextColor(Color.WHITE);
        LinearLayout.LayoutParams btnParams = new LinearLayout.LayoutParams(-1, -2);
        btnParams.topMargin = 20;
        connectExtButton.setLayoutParams(btnParams);
        connectExtButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String url = ipEditText.getText().toString().trim();
                if (url.isEmpty()) {
                    ipEditText.setError("Entrez une adresse valide");
                    return;
                }
                if (!url.startsWith("http://") && !url.startsWith("https://")) {
                    url = "http://" + url;
                }
                savePreferences("external", url);
                startApplicationFlow();
            }
        });
        extContainer.addView(connectExtButton);
        layout.addView(extContainer);

        selectionView.addView(layout);
    }

    private Button createOptionButton(String mainText, String subText) {
        Button btn = new Button(this);
        btn.setText(mainText + "\n" + subText);
        btn.setTransformationMethod(null); // Keep formatting
        btn.setTextSize(14);
        btn.setPadding(30, 40, 30, 40);
        
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(0xFF1E293B);
        gd.setCornerRadius(20);
        gd.setStroke(2, 0xFF334155);
        btn.setBackground(gd);
        btn.setTextColor(Color.WHITE);
        btn.setLineSpacing(10, 1);
        return btn;
    }

    private void createLoadingUI() {
        loadingView = new FrameLayout(this);
        loadingView.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        loadingView.setBackgroundColor(0xFF0F172A);
        loadingView.setVisibility(View.GONE);

        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams cParams = new FrameLayout.LayoutParams(-2, -2);
        cParams.gravity = Gravity.CENTER;
        container.setLayoutParams(cParams);

        ProgressBar spinner = new ProgressBar(this);
        container.addView(spinner);

        statusTextView = new TextView(this);
        statusTextView.setText("Démarrage du serveur...");
        statusTextView.setTextColor(0xFFE2E8F0);
        statusTextView.setTextSize(16);
        statusTextView.setGravity(Gravity.CENTER);
        statusTextView.setPadding(0, 40, 0, 40);
        container.addView(statusTextView);

        settingsButton = new Button(this);
        settingsButton.setText("Modifier les paramètres de connexion");
        settingsButton.setBackgroundColor(0xFFEF4444); // Red 500
        settingsButton.setTextColor(Color.WHITE);
        settingsButton.setVisibility(View.GONE);
        settingsButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                resetPreferences();
                showSelectionScreen();
            }
        });
        container.addView(settingsButton);

        loadingView.addView(container);
    }

    private void savePreferences(String mode, String url) {
        selectedMode = mode;
        targetUrl = url;
        SharedPreferences.Editor editor = prefs.edit();
        editor.putString("selected_mode", mode);
        editor.putString("target_url", url);
        editor.apply();
    }

    private void resetPreferences() {
        selectedMode = "";
        targetUrl = "http://localhost:5000";
        SharedPreferences.Editor editor = prefs.edit();
        editor.clear();
        editor.apply();
    }

    private void showSelectionScreen() {
        isLoaded = false;
        webView.setVisibility(View.GONE);
        loadingView.setVisibility(View.GONE);
        selectionView.setVisibility(View.VISIBLE);
        settingsButton.setVisibility(View.GONE);
    }

    private void startApplicationFlow() {
        selectionView.setVisibility(View.GONE);
        loadingView.setVisibility(View.VISIBLE);
        settingsButton.setVisibility(View.GONE);
        isLoaded = false;
        attemptCount = 0;

        if (selectedMode.equals("local")) {
            statusTextView.setText("Initialisation et démarrage du serveur local Termux...\n(Cela peut prendre quelques instants au premier lancement)");
            startTermuxServer();
        } else {
            statusTextView.setText("Connexion au serveur externe :\n" + targetUrl);
        }

        webView.loadUrl(targetUrl);
    }

    private void startTermuxServer() {
        // Build one-click install and startup script
        String command = "if [ -f ~/start_fab.sh ]; then " +
                         "  bash ~/start_fab.sh; " +
                         "else " +
                         "  echo 'Installation automatique de FABouanes...';" +
                         "  curl -sL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh -o ~/setup_termux.sh && bash ~/setup_termux.sh; " +
                         "fi";

        Intent intent = new Intent();
        intent.setClassName("com.termux", "com.termux.app.RunCommandService");
        intent.setAction("com.termux.RUN_COMMAND");
        intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
        intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", command});
        intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
        intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
        try {
            startService(intent);
        } catch (Exception e) {
            statusTextView.setText("Erreur : Impossible de démarrer Termux. Assurez-vous que l'application Termux est installée.");
        }
    }

    private void retryLoading() {
        attemptCount++;
        if (isLoaded) return;
        
        statusTextView.setText("Démarrage du serveur local... Tentative " + attemptCount + "\n(Le premier lancement prend 1-2 minutes)");
        
        // Show change settings button after 10 retries so users can switch to external if needed
        if (attemptCount > 10) {
            settingsButton.setVisibility(View.VISIBLE);
        }
        
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!isLoaded) {
                    webView.loadUrl(targetUrl);
                }
            }
        }, 2000);
    }

    @Override
    public void onBackPressed() {
        if (webView.getVisibility() == View.VISIBLE && webView.canGoBack()) {
            webView.goBack();
        } else if (webView.getVisibility() == View.VISIBLE) {
            // Show settings view to let user change configuration
            webView.setVisibility(View.GONE);
            loadingView.setVisibility(View.VISIBLE);
            statusTextView.setText("Menu de connexion");
            settingsButton.setVisibility(View.VISIBLE);
        } else if (loadingView.getVisibility() == View.VISIBLE) {
            showSelectionScreen();
        } else {
            super.onBackPressed();
        }
    }
}
