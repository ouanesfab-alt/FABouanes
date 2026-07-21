package com.fabouanes.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RelativeLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

public class MainActivity extends AppCompatActivity {

    // Views
    private FrameLayout    root;
    private ScrollView     screenSelect;
    private FrameLayout    screenSetup;
    private WebView        webView;

    // Setup screen elements
    private TextView       tvSetupTitle;
    private TextView       tvSetupSub;
    private ProgressBar    progressBar;
    private LinearLayout   stepList;
    private Button         btnChangeMode;

    // External input
    private EditText       etExternalUrl;

    // State
    private boolean        isLoaded      = false;
    private int            retryCount    = 0;
    private String         selectedMode  = "";   // "local" | "external"
    private String         targetUrl     = "http://localhost:5000";

    private final Handler  handler       = new Handler(Looper.getMainLooper());
    private SharedPreferences prefs;
    private BroadcastReceiver serviceReceiver;

    // Setup steps
    private String[] STEP_LABELS = {
        "Extraction de l'environnement",
        "Initialisation PostgreSQL",
        "Démarrage du serveur",
        "Connexion…"
    };
    private TextView[] stepViews;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("fab", Context.MODE_PRIVATE);
        selectedMode = prefs.getString("mode", "");
        targetUrl    = prefs.getString("url", "http://localhost:5000");

        root = new FrameLayout(this);
        root.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        root.setBackgroundColor(0xFF0A0F1E);
        setContentView(root);

        buildWebView();
        buildSelectScreen();
        buildSetupScreen();

        registerServiceReceiver();

        if ("local".equals(selectedMode) && prefs.getBoolean("extracted", false)) {
            // Already set up — just start server and show loader
            showSetupScreen("Démarrage du serveur local…", 70);
            startService("start");
        } else if ("external".equals(selectedMode)) {
            showSetupScreen("Connexion au serveur externe…", 90);
            webView.loadUrl(targetUrl);
        } else {
            showSelectScreen();
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // WEBVIEW
    // ─────────────────────────────────────────────────────────────────────────

    private void buildWebView() {
        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        webView.setVisibility(View.GONE);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                if (!isLoaded) {
                    isLoaded = true;
                    handler.post(() -> showWebView());
                }
            }
            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) handler.post(() -> retryConnect());
            }
        });
        root.addView(webView);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SELECTION SCREEN
    // ─────────────────────────────────────────────────────────────────────────

    private void buildSelectScreen() {
        screenSelect = new ScrollView(this);
        screenSelect.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        screenSelect.setBackgroundColor(0xFF0A0F1E);
        screenSelect.setVisibility(View.GONE);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(24), dp(56), dp(24), dp(32));
        col.setGravity(Gravity.CENTER_HORIZONTAL);

        // Logo area
        col.addView(makeLogo());

        // Subtitle
        col.addView(makeLabel("Choisissez votre mode de connexion",
                0xFF94A3B8, 14, 0, 0, 0, dp(40)));

        // === Local card ===
        col.addView(makeCard(
                "💻  Serveur Local",
                "Ce smartphone devient le serveur.\nAucune connexion internet requise.",
                "Démarrer le serveur local",
                0xFF3B82F6,
                v -> onLocalSelected()
        ));

        // Separator
        col.addView(makeLabel("— ou —", 0xFF4B5563, 13, 0, dp(24), 0, dp(24)));

        // === External card ===
        LinearLayout extCard = makeCardShell("🌐  Serveur Externe",
                "Connectez-vous à un autre appareil\n(PC, téléphone ou serveur distant).");

        etExternalUrl = new EditText(this);
        etExternalUrl.setHint("http://192.168.1.10:5000");
        etExternalUrl.setHintTextColor(0xFF4B5563);
        etExternalUrl.setTextColor(0xFFE2E8F0);
        etExternalUrl.setTextSize(14);
        etExternalUrl.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        etExternalUrl.setBackground(makeRoundedBg(0xFF1E293B, 0xFF334155, dp(10)));
        etExternalUrl.setPadding(dp(16), dp(14), dp(16), dp(14));
        etExternalUrl.setSingleLine(true);
        LinearLayout.LayoutParams ep = new LinearLayout.LayoutParams(-1, -2);
        ep.topMargin = dp(12);
        ep.bottomMargin = dp(12);
        etExternalUrl.setLayoutParams(ep);
        extCard.addView(etExternalUrl);

        // Pre-fill saved URL if external was previously selected
        if ("external".equals(selectedMode)) etExternalUrl.setText(targetUrl);

        Button btnConnect = makeButton("Se connecter", 0xFF10B981);
        btnConnect.setOnClickListener(v -> onExternalSelected());
        extCard.addView(btnConnect);

        col.addView(extCard);

        screenSelect.addView(col);
        root.addView(screenSelect);
    }

    private void onLocalSelected() {
        prefs.edit().putString("mode", "local").apply();
        selectedMode = "local";
        if (prefs.getBoolean("extracted", false)) {
            showSetupScreen("Redémarrage du serveur local…", 70);
            startService("start");
        } else {
            showSetupScreen("Premier lancement — installation (quelques minutes)…", 2);
            startService("extract");
        }
    }

    private void onExternalSelected() {
        String url = etExternalUrl.getText().toString().trim();
        if (url.isEmpty()) { etExternalUrl.setError("Entrez une adresse"); return; }
        if (!url.startsWith("http")) url = "http://" + url;
        prefs.edit().putString("mode", "external").putString("url", url).apply();
        selectedMode = "external";
        targetUrl    = url;
        showSetupScreen("Connexion au serveur externe…", 90);
        isLoaded = false;
        retryCount = 0;
        webView.loadUrl(targetUrl);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SETUP / LOADING SCREEN
    // ─────────────────────────────────────────────────────────────────────────

    private void buildSetupScreen() {
        screenSetup = new FrameLayout(this);
        screenSetup.setLayoutParams(new FrameLayout.LayoutParams(-1, -1));
        screenSetup.setBackgroundColor(0xFF0A0F1E);
        screenSetup.setVisibility(View.GONE);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        col.setPadding(dp(32), dp(80), dp(32), dp(32));
        FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(-2, -2);
        cp.gravity = Gravity.CENTER;
        col.setLayoutParams(cp);

        col.addView(makeLogo());

        tvSetupTitle = makeLabel("Initialisation…", 0xFFE2E8F0, 18, 0, dp(8), 0, dp(6));
        tvSetupTitle.setTypeface(null, Typeface.BOLD);
        col.addView(tvSetupTitle);

        tvSetupSub = makeLabel("Cette opération s'effectue uniquement lors du premier lancement.",
                0xFF64748B, 13, 0, 0, 0, dp(32));
        tvSetupSub.setGravity(Gravity.CENTER);
        col.addView(tvSetupSub);

        // Steps
        stepList = new LinearLayout(this);
        stepList.setOrientation(LinearLayout.VERTICAL);
        stepViews = new TextView[STEP_LABELS.length];
        for (int i = 0; i < STEP_LABELS.length; i++) {
            TextView tv = makeLabel("○  " + STEP_LABELS[i], 0xFF4B5563, 14, 0, 0, 0, dp(10));
            stepViews[i] = tv;
            stepList.addView(tv);
        }
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(-1, -2);
        slp.bottomMargin = dp(24);
        stepList.setLayoutParams(slp);
        col.addView(stepList);

        // Progress bar
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setProgress(2);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, dp(6));
        pp.bottomMargin = dp(32);
        progressBar.setLayoutParams(pp);
        col.addView(progressBar);

        // Change mode button
        btnChangeMode = makeButton("Modifier le mode de connexion", 0xFF334155);
        btnChangeMode.setTextSize(12);
        btnChangeMode.setVisibility(View.GONE);
        btnChangeMode.setOnClickListener(v -> {
            prefs.edit().remove("mode").apply();
            selectedMode = "";
            showSelectScreen();
        });
        col.addView(btnChangeMode);

        screenSetup.addView(col);
        root.addView(screenSetup);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SERVICE COMMUNICATION
    // ─────────────────────────────────────────────────────────────────────────

    private void registerServiceReceiver() {
        serviceReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context ctx, Intent intent) {
                String action  = intent.getAction();
                String message = intent.getStringExtra(ServerService.EXTRA_MESSAGE);
                int    percent = intent.getIntExtra(ServerService.EXTRA_PERCENT, 0);

                if (ServerService.BROADCAST_PROGRESS.equals(action)) {
                    handler.post(() -> updateSetupProgress(message, percent));
                } else if (ServerService.BROADCAST_STARTED.equals(action)) {
                    handler.post(() -> {
                        updateSetupProgress("Connexion à l'application…", 100);
                        isLoaded = false;
                        retryCount = 0;
                        webView.loadUrl("http://localhost:5000");
                    });
                } else if (ServerService.BROADCAST_ERROR.equals(action)) {
                    handler.post(() -> onSetupError(message));
                }
            }
        };
        IntentFilter filter = new IntentFilter();
        filter.addAction(ServerService.BROADCAST_PROGRESS);
        filter.addAction(ServerService.BROADCAST_STARTED);
        filter.addAction(ServerService.BROADCAST_ERROR);
        registerReceiver(serviceReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
    }

    private void startService(String action) {
        Intent i = new Intent(this, ServerService.class);
        i.putExtra("action", action);
        startService(i);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // UI TRANSITIONS
    // ─────────────────────────────────────────────────────────────────────────

    private void showSelectScreen() {
        screenSelect.setVisibility(View.VISIBLE);
        screenSetup.setVisibility(View.GONE);
        webView.setVisibility(View.GONE);
    }

    private void showSetupScreen(String msg, int percent) {
        screenSetup.setVisibility(View.VISIBLE);
        screenSelect.setVisibility(View.GONE);
        webView.setVisibility(View.GONE);
        updateSetupProgress(msg, percent);
    }

    private void showWebView() {
        webView.setVisibility(View.VISIBLE);
        screenSetup.setVisibility(View.GONE);
        screenSelect.setVisibility(View.GONE);
    }

    private void updateSetupProgress(String msg, int percent) {
        if (tvSetupTitle != null) tvSetupTitle.setText(msg);
        if (progressBar  != null) progressBar.setProgress(percent);

        // Update step indicators
        if (stepViews != null) {
            int step = 0;
            if (percent > 5)  step = 1;
            if (percent > 50) step = 2;
            if (percent > 90) step = 3;
            for (int i = 0; i < stepViews.length; i++) {
                if (i < step)       stepViews[i].setText("✓  " + STEP_LABELS[i]);
                else if (i == step) stepViews[i].setText("⟳  " + STEP_LABELS[i]);
                else                stepViews[i].setText("○  " + STEP_LABELS[i]);

                stepViews[i].setTextColor(
                        i < step  ? 0xFF22C55E :
                        i == step ? 0xFF60A5FA : 0xFF4B5563);
            }
        }
    }

    private void onSetupError(String msg) {
        if (tvSetupTitle != null) tvSetupTitle.setText("⚠ " + msg);
        if (btnChangeMode != null) btnChangeMode.setVisibility(View.VISIBLE);
    }

    private void retryConnect() {
        retryCount++;
        if (isLoaded) return;
        String status = "local".equals(selectedMode)
                ? "Démarrage du serveur… (" + retryCount + ")"
                : "Connexion au serveur externe… (" + retryCount + ")";
        if (tvSetupTitle != null) tvSetupTitle.setText(status);
        if (retryCount > 12) btnChangeMode.setVisibility(View.VISIBLE);
        handler.postDelayed(() -> { if (!isLoaded) webView.loadUrl(targetUrl); }, 2000);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // UI HELPERS
    // ─────────────────────────────────────────────────────────────────────────

    private View makeLogo() {
        TextView tv = new TextView(this);
        tv.setText("FABouanes");
        tv.setTextSize(32);
        tv.setTypeface(null, Typeface.BOLD);
        tv.setTextColor(0xFF60A5FA);
        tv.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        p.bottomMargin = dp(8);
        tv.setLayoutParams(p);
        return tv;
    }

    private TextView makeLabel(String text, int color, int sp,
                               int ml, int mt, int mr, int mb) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextColor(color);
        tv.setTextSize(sp);
        tv.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        p.setMargins(ml, mt, mr, mb);
        tv.setLayoutParams(p);
        return tv;
    }

    /** Full card with title, subtitle, and a button */
    private LinearLayout makeCard(String title, String sub, String btnLabel, int btnColor,
                                   View.OnClickListener onClick) {
        LinearLayout card = makeCardShell(title, sub);
        Button btn = makeButton(btnLabel, btnColor);
        btn.setOnClickListener(onClick);
        card.addView(btn);
        return card;
    }

    /** Card shell (title + sub only) */
    private LinearLayout makeCardShell(String title, String sub) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(20), dp(20), dp(20), dp(20));
        card.setBackground(makeRoundedBg(0xFF111827, 0xFF1E40AF, dp(16)));
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.bottomMargin = dp(8);
        card.setLayoutParams(cp);

        TextView tvTitle = new TextView(this);
        tvTitle.setText(title);
        tvTitle.setTextColor(0xFFE2E8F0);
        tvTitle.setTextSize(16);
        tvTitle.setTypeface(null, Typeface.BOLD);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.bottomMargin = dp(6);
        tvTitle.setLayoutParams(tp);
        card.addView(tvTitle);

        TextView tvSub = new TextView(this);
        tvSub.setText(sub);
        tvSub.setTextColor(0xFF64748B);
        tvSub.setTextSize(13);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, -2);
        sp.bottomMargin = dp(16);
        tvSub.setLayoutParams(sp);
        card.addView(tvSub);

        return card;
    }

    private Button makeButton(String label, int bgColor) {
        Button btn = new Button(this);
        btn.setText(label);
        btn.setTextColor(Color.WHITE);
        btn.setTextSize(14);
        btn.setBackground(makeRoundedBg(bgColor, 0, dp(12)));
        btn.setPadding(dp(16), dp(14), dp(16), dp(14));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        btn.setLayoutParams(p);
        return btn;
    }

    private android.graphics.drawable.GradientDrawable makeRoundedBg(int fill, int stroke, int radius) {
        android.graphics.drawable.GradientDrawable gd = new android.graphics.drawable.GradientDrawable();
        gd.setColor(fill);
        gd.setCornerRadius(radius);
        if (stroke != 0) gd.setStroke(dp(1), stroke);
        return gd;
    }

    private int dp(int val) {
        return (int) (val * getResources().getDisplayMetrics().density);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // NAVIGATION
    // ─────────────────────────────────────────────────────────────────────────

    @Override
    public void onBackPressed() {
        if (webView.getVisibility() == View.VISIBLE) {
            if (webView.canGoBack()) webView.goBack();
            else { webView.setVisibility(View.GONE); showSelectScreen(); }
        } else if (screenSetup.getVisibility() == View.VISIBLE) {
            showSelectScreen();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (serviceReceiver != null) unregisterReceiver(serviceReceiver);
        super.onDestroy();
    }
}
