[app]

# (str) Title of your application
title = FABouanes

# (str) Package name
package.name = fabouanes

# (str) Package domain (needed for android/ios packaging)
package.domain = com.fabouanes.app

# (str) Source code where the main.py is located
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,jfif,html,css,js,ttf,woff,woff2,sql,json,env,txt,md

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests, bin, venv, .git, .github, .agents, .gemini

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy

# (str) Custom source folders for requirements
# (str) Presplash of the application
presplash.filename = %(source.dir)s/static/143.jfif

# (str) Icon of the application
icon.filename = %(source.dir)s/static/icon_512.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait,landscape

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API required
android.minapi = 24

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25.2.9519653

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) List of Java .jar files to add to the libs so that your custom class
# can access them. Don't add jars that you do not need, since each jar adds
# size to the release issue.
#android.add_jars = foo.jar,bar.jar

# (list) List of Java files to add to the android build (for custom android code)
#android.add_src =

# (list) Android AAR archives to add
#android.add_aars =

# (list) Put these files or directories in the apk assets directory
#android.add_assets =

# (str) Bootstrap to use for android build
android.bootstrap = sdl2

# (bool) Copy library instead of making a libpymodules.so
#android.copy_libs = 1

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a, armeabi-v7a

# (bool) Enable Android logcat output
android.logcat_filters = *:S python:D

#
# Python for android (p4a) specific
#
p4a.branch = master

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = false, 1 = true)
warn_on_root = 1

# (str) Path to build work dir, if you want to use another directory
# build_dir = ./.buildozer

# (str) Path to build output (APK, AAB), if you want to use another directory
# bin_dir = ./bin
