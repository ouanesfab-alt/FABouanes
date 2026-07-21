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

            broadcast(BROADCAST_PROGRESS, "Application des permissions d’exécution (chmod)...", 80);
            chmodRecursive(getPrefix().getAbsolutePath() + "/bin", "755");
            chmodRecursive(getPrefix().getAbsolutePath() + "/lib", "755");
            chmodRecursive(getPrefix().getAbsolutePath() + "/lib/postgresql", "755");

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

    /** Use system chmod (always available on Android) — much more reliable than File.setExecutable() */
    private void chmodRecursive(String path, String mode) {
        try {
            Process p = new ProcessBuilder("/system/bin/chmod", "-R", mode, path)
                    .redirectErrorStream(true)
                    .start();
            // drain output
            try (InputStream is = p.getInputStream()) {
                byte[] buf = new byte[4096];
                while (is.read(buf) != -1) {}
            }
            p.waitFor();
            Log.d(TAG, "chmod -R " + mode + " " + path + " done");
        } catch (Exception e) {
            Log.e(TAG, "chmod failed on " + path, e);
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
            String prefix    = getPrefix().getAbsolutePath();
            String home      = getHome().getAbsolutePath();
            String pgData    = new File(getFilesDir(), "pgdata").getAbsolutePath();
            String pgShare   = prefix + "/share/postgresql";
            String pgPkgLib  = prefix + "/lib/postgresql";
            String libPath   = prefix + "/lib";
            String binPath   = prefix + "/bin";
            String tmpDir    = getCacheDir().getAbsolutePath();
            // Unix socket for PostgreSQL — must be a short path (PG limit ~107 chars)
            String pgSocket  = tmpDir;

            broadcast(BROADCAST_PROGRESS, "Initialisation de PostgreSQL...", 96);
            startPostgres(prefix, pgData, pgShare, pgPkgLib, libPath, binPath, tmpDir, pgSocket);

            Thread.sleep(4000);

            broadcast(BROADCAST_PROGRESS, "Démarrage du serveur FABouanes...", 98);
            startPython(prefix, home, libPath, binPath, pgSocket, tmpDir);

            Thread.sleep(3000);
            broadcast(BROADCAST_STARTED, "Serveur démarré !", 100);

        } catch (Exception e) {
            Log.e(TAG, "Start error", e);
            broadcast(BROADCAST_ERROR, "Erreur démarrage: " + e.getMessage(), 0);
        }
    }

    /** Build the full env block for any process in our embedded runtime. */
    private java.util.Map<String, String> buildEnv(String prefix, String libPath,
                                                    String pgShare, String pgPkgLib,
                                                    String home, String tmpDir, String pgSocket) {
        java.util.Map<String, String> env = new java.util.HashMap<>();

        // ── Library path: overrides RPATH (takes priority on Android bionic linker) ──
        env.put("LD_LIBRARY_PATH", libPath + ":" + libPath + "/postgresql");

        // ── Python: override compiled-in prefix (was /data/data/com.termux) ──
        env.put("PYTHONHOME",  prefix);
        env.put("PYTHONPATH",  prefix + "/lib/python3.14:" + prefix + "/lib/python3.14/site-packages");

        // ── PostgreSQL: override all compiled-in paths ──
        if (pgShare  != null) env.put("PGSHAREDIR",   pgShare);
        if (pgPkgLib != null) env.put("PGPKGLIBDIR",  pgPkgLib);
        env.put("PGDATA",    new File(getFilesDir(), "pgdata").getAbsolutePath());
        env.put("PGHOST",    pgSocket);
        env.put("PGPORT",    "5432");
        env.put("PGUSER",    "fab");
        env.put("PGDATABASE", "fabouanes");

        // ── System ──
        env.put("PREFIX",   prefix);
        env.put("HOME",     home);
        env.put("TMPDIR",   tmpDir);
        env.put("PATH",     prefix + "/bin:/system/bin:/system/xbin");
        env.put("LANG",     "C.UTF-8");
        env.put("LC_ALL",   "C");

        return env;
    }

    private void startPostgres(String prefix, String pgData,
                                String pgShare, String pgPkgLib,
                                String libPath, String binPath,
                                String tmpDir, String pgSocket)
            throws IOException, InterruptedException {

        java.util.Map<String, String> env =
                buildEnv(prefix, libPath, pgShare, pgPkgLib,
                         getHome().getAbsolutePath(), tmpDir, pgSocket);

        File pgDataDir = new File(pgData);
        if (!pgDataDir.exists()) {
            broadcast(BROADCAST_PROGRESS, "Création de la base de données (initdb)...", 96);
            runProcess(
                new String[]{binPath + "/initdb",
                    "-D", pgData,
                    "-U", "fab",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--locale=C"},
                env, true);
            Thread.sleep(2000);
        }

        broadcast(BROADCAST_PROGRESS, "Démarrage de PostgreSQL...", 97);
        // pg_ctl start — writes log to pgdata/pg_log/
        runProcess(
            new String[]{binPath + "/pg_ctl", "start",
                "-D", pgData,
                "-l", pgData + "/postgres.log",
                "-o", "-p 5432 -k " + pgSocket},
            env, true);
        Thread.sleep(3000);

        // Create DB if not exists (ignore error if already exists)
        runProcess(
            new String[]{binPath + "/createdb",
                "-h", pgSocket, "-p", "5432",
                "-U", "fab", "fabouanes"},
            env, false);
    }

    private void startPython(String prefix, String home,
                              String libPath, String binPath,
                              String pgSocket, String tmpDir)
            throws IOException {
        File fabDir = getFABDir();
        java.util.Map<String, String> env =
                buildEnv(prefix, libPath,
                         prefix + "/share/postgresql",
                         prefix + "/lib/postgresql",
                         home, tmpDir, pgSocket);

        String[] cmd = {binPath + "/python3.14", "launcher.py"};
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(fabDir);
        pb.environment().putAll(env);
        pb.redirectErrorStream(true);
        serverProcess = pb.start();

        // Log output to file for debugging
        final Process proc = serverProcess;
        new Thread(() -> {
            try (InputStream is = proc.getInputStream();
                 FileOutputStream log = new FileOutputStream(
                         new File(getFilesDir(), "python_server.log"))) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = is.read(buf)) != -1) log.write(buf, 0, n);
            } catch (Exception ignored) {}
        }, "python-log").start();
    }

    private void runProcess(String[] cmd, java.util.Map<String, String> env, boolean waitFor)
            throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.environment().putAll(env);
        pb.redirectErrorStream(true);
        Process p = pb.start();
        if (waitFor) {
            // Drain output
            try (InputStream is = p.getInputStream()) {
                byte[] buf = new byte[4096];
                while (is.read(buf) != -1) {}
            }
            p.waitFor();
        }
    }

    // ── keep old runCmd signature for any remaining callers ──
    private void runCmd(String[] cmd, String prefix, String libPath, boolean waitFor)
            throws IOException, InterruptedException {
        java.util.Map<String, String> env = buildEnv(prefix, libPath, null, null,
                getHome().getAbsolutePath(), getCacheDir().getAbsolutePath(), getCacheDir().getAbsolutePath());
        runProcess(cmd, env, waitFor);
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
