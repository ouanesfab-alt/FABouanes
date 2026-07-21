package com.fabouanes.mobile;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.tukaani.xz.XZInputStream;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public class ServerService extends Service {

    static final String ACTION_EXTRACT = "extract";
    static final String ACTION_START   = "start";
    static final String ACTION_STOP    = "stop";
    static final String EXTRA_CALLBACK = "callback_class";

    // Broadcast actions sent back to MainActivity
    static final String BROADCAST_PROGRESS = "com.fabouanes.mobile.PROGRESS";
    static final String BROADCAST_STARTED  = "com.fabouanes.mobile.STARTED";
    static final String BROADCAST_ERROR    = "com.fabouanes.mobile.ERROR";

    static final String EXTRA_MESSAGE  = "message";
    static final String EXTRA_PERCENT  = "percent";

    private static final String TAG = "FABServerService";

    private Process serverProcess;
    private File    runtimeDir;

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;
        String action = intent.getStringExtra("action");
        if (action == null) action = "";
        switch (action) {
            case "extract": new Thread(this::doExtract).start(); break;
            case "start":   new Thread(this::doStart).start();   break;
            case "stop":    doStop(); stopSelf();                 break;
        }
        return START_NOT_STICKY;
    }

    // ─── PATHS ──────────────────────────────────────────────────────────────

    private File getPrefix() {
        return new File(getFilesDir(), "usr");
    }

    private File getHome() {
        return new File(getFilesDir(), "home");
    }

    private File getFABDir() {
        return new File(getHome(), "FABouanes");
    }

    // ─── EXTRACTION ─────────────────────────────────────────────────────────

    private void doExtract() {
        broadcast(BROADCAST_PROGRESS, "Préparation de l'environnement...", 2);
        try {
            File prefix = getPrefix();
            File home   = getHome();
            prefix.mkdirs();
            home.mkdirs();

            broadcast(BROADCAST_PROGRESS, "Extraction de l'archive runtime (73 Mo)...", 5);
            extractAsset("fabouanes_runtime.tar.xz");

            broadcast(BROADCAST_PROGRESS, "Correction des permissions d'exécution...", 80);
            setExecutable(new File(getPrefix(), "bin/bash"));
            setExecutable(new File(getPrefix(), "bin/python3.14"));
            setExecutable(new File(getPrefix(), "bin/postgres"));
            setExecutable(new File(getPrefix(), "bin/pg_ctl"));
            setExecutable(new File(getPrefix(), "bin/initdb"));
            setExecutable(new File(getPrefix(), "bin/createdb"));

            broadcast(BROADCAST_PROGRESS, "Écriture du fichier de configuration .env...", 88);
            writeEnvFile();

            broadcast(BROADCAST_PROGRESS, "Extraction terminée ✓", 95);
            getSharedPreferences("fab", Context.MODE_PRIVATE)
                    .edit().putBoolean("extracted", true).apply();

            doStart();

        } catch (Exception e) {
            Log.e(TAG, "Extraction error", e);
            broadcast(BROADCAST_ERROR, "Erreur extraction: " + e.getMessage(), 0);
        }
    }

    private void extractAsset(String assetName) throws IOException {
        File outDir = getFilesDir();
        broadcast(BROADCAST_PROGRESS, "Décompression de l'archive runtime...", 10);

        // Pure Java extraction — no system commands needed, works on all Android versions
        try (InputStream raw    = getAssets().open(assetName, android.content.res.AssetManager.ACCESS_STREAMING);
             BufferedInputStream bis = new BufferedInputStream(raw, 131072);
             XZInputStream xzIn     = new XZInputStream(bis);
             TarArchiveInputStream tarIn = new TarArchiveInputStream(xzIn)) {

            TarArchiveEntry entry;
            int count = 0;
            while ((entry = (TarArchiveEntry) tarIn.getNextEntry()) != null) {
                File dest = new File(outDir, entry.getName());

                if (entry.isSymbolicLink()) {
                    // Recreate symlinks
                    dest.getParentFile().mkdirs();
                    try {
                        java.nio.file.Files.deleteIfExists(dest.toPath());
                        java.nio.file.Files.createSymbolicLink(
                            dest.toPath(),
                            java.nio.file.Paths.get(entry.getLinkName()));
                    } catch (Exception ignored) {}
                    continue;
                }

                if (entry.isDirectory()) {
                    dest.mkdirs();
                    continue;
                }

                dest.getParentFile().mkdirs();
                try (FileOutputStream fos = new FileOutputStream(dest)) {
                    byte[] buf = new byte[65536];
                    int len;
                    while ((len = tarIn.read(buf)) != -1) {
                        fos.write(buf, 0, len);
                    }
                }

                // Restore executable bit from tar metadata
                int mode = entry.getMode();
                if ((mode & 0111) != 0) {
                    dest.setExecutable(true, false);
                }

                count++;
                // Broadcast rough progress from 10% to 75%
                if (count % 500 == 0) {
                    broadcast(BROADCAST_PROGRESS, "Extraction: " + count + " fichiers...",
                            Math.min(75, 10 + count / 100));
                }
            }
        }
        broadcast(BROADCAST_PROGRESS, "Extraction terminée — " + "OK", 76);
    }

    private void setExecutable(File f) {
        if (f.exists()) {
            f.setExecutable(true, false);
            f.setReadable(true, false);
        }
    }

    // ─── ENV FILE ────────────────────────────────────────────────────────────

    private void writeEnvFile() throws IOException {
        File fabDir = getFABDir();
        File envFile = new File(fabDir, ".env");
        if (!envFile.exists()) {
            String prefix = getPrefix().getAbsolutePath();
            String pgData = new File(getFilesDir(), "pgdata").getAbsolutePath();
            String content =
                    "SECRET_KEY=fab-android-local-secret-" + System.currentTimeMillis() + "\n" +
                    "DATABASE_URL=postgresql://fab@localhost:5432/fabouanes\n" +
                    "FASTAPI_ENV=production\n" +
                    "FAB_DESKTOP=0\n" +
                    "FAB_DATA_DIR=" + getFilesDir().getAbsolutePath() + "\n";
            try (FileOutputStream fos = new FileOutputStream(envFile)) {
                fos.write(content.getBytes());
            }
        }
    }

    // ─── START SERVER ────────────────────────────────────────────────────────

    private void doStart() {
        try {
            String prefix  = getPrefix().getAbsolutePath();
            String home    = getHome().getAbsolutePath();
            String pgData  = new File(getFilesDir(), "pgdata").getAbsolutePath();
            String libPath = prefix + "/lib";
            String binPath = prefix + "/bin";

            broadcast(BROADCAST_PROGRESS, "Démarrage de PostgreSQL...", 96);
            startPostgres(prefix, pgData, libPath, binPath);

            Thread.sleep(3000);

            broadcast(BROADCAST_PROGRESS, "Démarrage du serveur FABouanes...", 98);
            startPython(prefix, home, libPath, binPath);

            Thread.sleep(2000);
            broadcast(BROADCAST_STARTED, "Serveur démarré !", 100);

        } catch (Exception e) {
            Log.e(TAG, "Start error", e);
            broadcast(BROADCAST_ERROR, "Erreur démarrage: " + e.getMessage(), 0);
        }
    }

    private void startPostgres(String prefix, String pgData, String libPath, String binPath)
            throws IOException, InterruptedException {
        File pgDataDir = new File(pgData);
        if (!pgDataDir.exists()) {
            // initdb
            broadcast(BROADCAST_PROGRESS, "Initialisation de la base de données...", 96);
            runCmd(new String[]{binPath + "/initdb", "-D", pgData, "-U", "fab"},
                   prefix, libPath, true);
            Thread.sleep(2000);
        }
        // start postgres
        runCmd(new String[]{binPath + "/pg_ctl", "start", "-D", pgData,
                "-o", "-p 5432 -k /tmp"},
               prefix, libPath, false);
        Thread.sleep(3000);
        // create db
        runCmd(new String[]{binPath + "/createdb", "-h", "/tmp", "-p", "5432",
                "-U", "fab", "fabouanes"},
               prefix, libPath, false);
    }

    private void startPython(String prefix, String home, String libPath, String binPath)
            throws IOException {
        File fabDir = getFABDir();
        String[] cmd = {binPath + "/python3.14", "launcher.py", "--server-only"};
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(fabDir);
        pb.environment().put("PREFIX", prefix);
        pb.environment().put("HOME", home);
        pb.environment().put("PYTHONHOME", prefix);
        pb.environment().put("PYTHONPATH", prefix + "/lib/python3.14:" + prefix + "/lib/python3.14/site-packages");
        pb.environment().put("LD_LIBRARY_PATH", libPath);
        pb.environment().put("PATH", binPath + ":/system/bin:/system/xbin");
        pb.environment().put("TMPDIR", getCacheDir().getAbsolutePath());
        pb.environment().put("PGHOST", "/tmp");
        pb.environment().put("PGPORT", "5432");
        pb.environment().put("PGUSER", "fab");
        pb.redirectErrorStream(true);
        serverProcess = pb.start();
    }

    private void runCmd(String[] cmd, String prefix, String libPath, boolean waitFor)
            throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.environment().put("PREFIX", prefix);
        pb.environment().put("LD_LIBRARY_PATH", libPath);
        pb.environment().put("PATH", prefix + "/bin:/system/bin");
        pb.environment().put("TMPDIR", getCacheDir().getAbsolutePath());
        pb.redirectErrorStream(true);
        Process p = pb.start();
        if (waitFor) {
            try (InputStream is = p.getInputStream()) { is.transferTo(OutputStream.nullOutputStream()); }
            p.waitFor();
        }
    }

    // ─── STOP ────────────────────────────────────────────────────────────────

    private void doStop() {
        if (serverProcess != null) {
            serverProcess.destroyForcibly();
            serverProcess = null;
        }
    }

    // ─── BROADCAST ───────────────────────────────────────────────────────────

    private void broadcast(String action, String message, int percent) {
        Intent intent = new Intent(action);
        intent.putExtra(EXTRA_MESSAGE, message);
        intent.putExtra(EXTRA_PERCENT, percent);
        sendBroadcast(intent);
        Log.d(TAG, "[" + percent + "%] " + message);
    }

    @Override
    public void onDestroy() {
        doStop();
        super.onDestroy();
    }
}
