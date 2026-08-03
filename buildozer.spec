[app]
title = AntiDown
package.name = antidown
package.domain = org.local

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,json,txt,md,ini,xml,so,bin
source.include_patterns = bin/android/arm64-v8a/*,bin/android/arm64-v8a/lib/*
source.exclude_dirs = .git,__pycache__,.buildozer,.ffmpeg-downloads,downloads,dist

version = 0.1.1

requirements = python3,kivy,pyjnius,yt-dlp,certifi,requests,urllib3,websockets,mutagen,pycryptodomex,brotli,cffi,curl-cffi,yt-dlp-ejs

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,POST_NOTIFICATIONS,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,MANAGE_EXTERNAL_STORAGE
android.api = 35
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.manifest.intent_filters = intent_filters.xml
android.manifest.launch_mode = standard
android.add_libs_arm64_v8a = bin/android/arm64-v8a/lib/*.so,bin/android/arm64-v8a/native/*.so

log_level = 2
warn_on_root = 0

[buildozer]
log_level = 2
warn_on_root = 0
