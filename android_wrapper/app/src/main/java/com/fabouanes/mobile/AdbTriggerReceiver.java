package com.fabouanes.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Exported receiver to allow triggering local server mode from ADB:
 *   adb shell am broadcast -a com.fabouanes.mobile.START_LOCAL
 *
 * This starts the extraction + server without needing to touch the screen.
 */
public class AdbTriggerReceiver extends BroadcastReceiver {

    private static final String TAG = "AdbTrigger";

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.d(TAG, "ADB trigger received — starting ServerService (extract)");

        // Save mode so MainActivity also knows
        context.getSharedPreferences("fab", Context.MODE_PRIVATE)
               .edit()
               .putString("mode", "local")
               .remove("extracted")   // force re-extraction with correct chmod
               .apply();

        // Start the extraction + server chain
        Intent svc = new Intent(context, ServerService.class);
        svc.putExtra("action", "extract");
        context.startForegroundService(svc);

        Log.d(TAG, "ServerService started via ADB trigger");
    }
}
