# AntiDown

Personal Android video downloader built with Kivy, yt-dlp, and bundled Android ffmpeg binaries.

This is for personal use with videos you have permission to download. It does not bypass DRM.

## Project layout

- `main.py` starts the Kivy app.
- `app/main.py` contains the simple UI.
- `app/core/downloader.py` wraps yt-dlp and prepares ffmpeg.
- `bin/android/<abi>/ffmpeg`, `ffprobe`, and `lib/*.so` are bundled binaries.
- `buildozer.spec` is the Android build config.

## Build APK

Buildozer works best on Linux. On Windows, use WSL Ubuntu.

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip openjdk-17-jdk
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip buildozer cython
buildozer android debug
```

The APK will be created under `bin/`.

## Build APK on Google Colab

Use `colab_build_antidown.ipynb` to build on Google's Colab runtime instead of your local Windows machine.

Direct Colab link:

```text
https://colab.research.google.com/github/locntssj/AntiDown/blob/main/colab_build_antidown.ipynb
```

Open the notebook, choose `Runtime > Run all`, and wait for the APK download prompt at the end. The first build can take 20-45 minutes because Colab needs to download Android SDK/NDK and compile dependencies.

## Download path

On Android, the app tries to save to:

```text
/storage/emulated/0/Download/AntiDown
```

If Android blocks public storage writes, it falls back to the app-private `downloads` folder.

## Notes

- High quality YouTube downloads often need `bestvideo+bestaudio`, which requires ffmpeg for merging.
- The bundled ffmpeg package includes executable files plus shared libraries. The app copies them to app-private storage and sets `LD_LIBRARY_PATH` before yt-dlp invokes ffmpeg.
- If a site breaks, update yt-dlp and rebuild the APK.
- Android storage permission behavior varies by version and device.
- TikTok extraction uses browser impersonation and an alternate API host fallback for links that fail with `Unable to extract universal data for rehydration`.

## Cookies

Use cookies only for accounts and content you have permission to access.

Cookie options in the app:

- `No cookies`: default.
- `Auto cookies.txt`: reads `cookies.txt` from the download folder. On Android this is `/storage/emulated/0/Download/AntiDown/cookies.txt`.
- `Custom cookies.txt`: enter a full path to a Netscape-format cookies file.
- `Chrome desktop`, `Edge desktop`, `Firefox desktop`: reads cookies from a desktop browser profile when running the desktop preview. This is not available on Android due to app sandboxing.

### Android WebView login

Tap `Login WebView` after pasting a URL. The app opens an internal Android WebView:

1. Log in to the matching site.
2. Tap `Save Cookies & Close`.
3. The app writes `/storage/emulated/0/Download/AntiDown/cookies.txt`.
4. Keep cookie mode as `Auto cookies.txt` and run `Analyze` / `Download`.

Some services may block WebView login, require CAPTCHA/2FA, or expire cookies quickly.
