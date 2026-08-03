import os
import platform as py_platform
import json
import re
import shutil
import stat
import subprocess
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from pathlib import Path

import requests
import yt_dlp
from kivy.app import App
from kivy.utils import platform

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except Exception:
    ImpersonateTarget = None


PRESET_FORMATS = [
    {
        "label": "Best video + audio",
        "format_id": "bestvideo+bestaudio/best",
        "ext": "auto",
        "height": "",
        "note": "Needs ffmpeg for merge on many sites",
    },
    {
        "label": "Best MP4 if available",
        "format_id": "best[ext=mp4]/best",
        "ext": "mp4",
        "height": "",
        "note": "Good compatibility",
    },
    {
        "label": "Best audio",
        "format_id": "bestaudio/best",
        "ext": "audio",
        "height": "",
        "note": "Audio only",
    },
]

TIKTOK_IMPERSONATE_TARGET = (
    ImpersonateTarget.from_str("safari:ios") if ImpersonateTarget else None
)
TIKTOK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tiktok.com/",
}
TIKTOK_VIDEO_HEADERS = {
    **TIKTOK_HEADERS,
    "Accept": "*/*",
    "Origin": "https://www.tiktok.com",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "si",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
    "_r",
    "_t",
    "is_from_webapp",
    "sender_device",
}

COOKIE_MODE_NONE = "No cookies"
COOKIE_MODE_AUTO_FILE = "Auto cookies.txt"
COOKIE_MODE_CUSTOM_FILE = "Custom cookies.txt"
COOKIE_MODE_CHROME = "Chrome desktop"
COOKIE_MODE_EDGE = "Edge desktop"
COOKIE_MODE_FIREFOX = "Firefox desktop"

COOKIE_MODES = (
    COOKIE_MODE_NONE,
    COOKIE_MODE_AUTO_FILE,
    COOKIE_MODE_CUSTOM_FILE,
    COOKIE_MODE_CHROME,
    COOKIE_MODE_EDGE,
    COOKIE_MODE_FIREFOX,
)


class YtDlpLogBridge:
    def __init__(self, logger):
        self.logger = logger

    def debug(self, message):
        if message and not str(message).startswith("[debug]"):
            self.logger(message)

    def warning(self, message):
        self.logger(f"WARNING: {message}")

    def error(self, message):
        self.logger(f"ERROR: {message}")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _current_android_abi() -> str:
    machine = py_platform.machine().lower()
    if machine in {"aarch64", "arm64", "arm64-v8a"}:
        return "arm64-v8a"
    if machine in {"armv7l", "armeabi-v7a"}:
        return "armeabi-v7a"
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    return machine


def _chmod_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _android_native_library_dir() -> Path | None:
    if platform != "android":
        return None
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        native_dir = PythonActivity.mActivity.getApplicationInfo().nativeLibraryDir
        return Path(str(native_dir)) if native_dir else None
    except Exception:
        return None


def _replace_link_or_copy(link_path: Path, target_path: Path) -> None:
    if link_path.exists() or link_path.is_symlink():
        try:
            if link_path.is_symlink() and Path(os.readlink(link_path)) == target_path:
                return
            link_path.unlink()
        except OSError:
            pass

    try:
        os.symlink(str(target_path), str(link_path))
        return
    except OSError:
        pass

    if not link_path.exists() or target_path.stat().st_size != link_path.stat().st_size:
        shutil.copyfile(target_path, link_path)
    _chmod_executable(link_path)


def _probe_ffmpeg(runtime_dir: Path, logger) -> bool:
    ffmpeg = runtime_dir / "ffmpeg"
    if not ffmpeg.exists() and not ffmpeg.is_symlink():
        logger(f"ffmpeg runtime file missing: {ffmpeg}")
        return False

    try:
        result = subprocess.run(
            [str(ffmpeg), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception as exc:
        logger(f"ffmpeg probe failed: {exc}")
        return False

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        logger(f"ffmpeg probe exit {result.returncode}: {stderr[:500]}")
        return False

    first_line = (result.stdout or "").splitlines()[0] if result.stdout else "ffmpeg OK"
    logger(first_line)
    return True


def _desktop_ffmpeg_dirs() -> list[Path]:
    roots = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(_project_root())

    candidates = []
    seen = set()
    for root in roots:
        for candidate in (root, root / "bin" / "windows", root / "ffmpeg"):
            key = str(candidate).lower()
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
    return candidates


def ensure_ffmpeg_runtime(logger=None) -> str | None:
    """Return a directory usable as yt-dlp's ffmpeg_location."""
    logger = logger or (lambda message: None)
    if platform != "android":
        for candidate in _desktop_ffmpeg_dirs():
            ffmpeg = candidate / "ffmpeg.exe"
            ffprobe = candidate / "ffprobe.exe"
            if ffmpeg.exists() and ffprobe.exists():
                return str(candidate)
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg and ffprobe:
            return str(Path(ffmpeg).parent)
        return None

    app = App.get_running_app()
    abi = _current_android_abi()
    bundled_dir = _project_root() / "bin" / "android" / abi
    native_dir = _android_native_library_dir()
    runtime_dir = Path(app.user_data_dir) / "bin" / abi
    runtime_lib_dir = runtime_dir / "lib"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_lib_dir.mkdir(parents=True, exist_ok=True)

    copied_any = False
    binary_sources = {
        "ffmpeg": [
            native_dir / "libantidown_ffmpeg.so" if native_dir else None,
            bundled_dir / "ffmpeg.bin",
            bundled_dir / "ffmpeg",
        ],
        "ffprobe": [
            native_dir / "libantidown_ffprobe.so" if native_dir else None,
            bundled_dir / "ffprobe.bin",
            bundled_dir / "ffprobe",
        ],
    }

    logger(f"Android ABI: {abi}")
    logger(f"Android native lib dir: {native_dir or 'not found'}")
    logger(f"Bundled ffmpeg dir: {bundled_dir}")
    logger(f"Runtime ffmpeg dir: {runtime_dir}")

    for name, candidates in binary_sources.items():
        source = next((candidate for candidate in candidates if candidate and candidate.exists()), None)
        target = runtime_dir / name
        if source:
            _replace_link_or_copy(target, source)
            copied_any = True
            logger(f"Prepared {name}: {target} -> {source}")
        else:
            logger(f"Missing bundled {name}. Checked: {', '.join(str(item) for item in candidates if item)}")

    source_lib_dir = bundled_dir / "lib"
    if source_lib_dir.exists():
        for source in source_lib_dir.glob("*.so"):
            target = runtime_lib_dir / source.name
            if not target.exists() or source.stat().st_size != target.stat().st_size:
                shutil.copyfile(source, target)

    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    paths = []
    if native_dir:
        paths.append(str(native_dir))
    paths.append(str(runtime_lib_dir))
    if current_ld_path:
        paths.append(current_ld_path)
    os.environ["LD_LIBRARY_PATH"] = ":".join(paths)

    if copied_any and _probe_ffmpeg(runtime_dir, logger):
        return str(runtime_dir)
    return str(runtime_dir) if copied_any else None


def _writable_dir(path: Path) -> Path | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except OSError:
        return None


def get_private_download_dir() -> Path:
    app = App.get_running_app()
    private_dir = Path(app.user_data_dir) / "downloads" if app else _project_root() / "downloads"
    private_dir.mkdir(parents=True, exist_ok=True)
    return private_dir


def get_download_dir(preferred_dir: str | None = None) -> Path:
    if preferred_dir:
        selected = _writable_dir(Path(preferred_dir).expanduser())
        if selected:
            return selected

    if platform == "android":
        public_dir = _writable_dir(Path("/storage/emulated/0/Download/AntiDown"))
        if public_dir:
            return public_dir

    return get_private_download_dir()


def request_android_permissions(logger=None, *, open_all_files_settings=False) -> None:
    logger = logger or (lambda message: None)
    if platform != "android":
        return
    try:
        from android.permissions import request_permissions

        permissions = [
            "android.permission.INTERNET",
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.READ_MEDIA_VIDEO",
            "android.permission.READ_MEDIA_AUDIO",
        ]
        request_permissions(permissions)
    except Exception as exc:
        logger(f"Could not request runtime permissions: {exc}")

    if not open_all_files_settings:
        return

    try:
        from jnius import autoclass

        Environment = autoclass("android.os.Environment")
        if Environment.isExternalStorageManager():
            return

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")

        activity = PythonActivity.mActivity
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse(f"package:{activity.getPackageName()}"))
        activity.startActivity(intent)
        logger("Opened Android storage permission settings.")
    except Exception as exc:
        logger(f"Could not open Android storage permission settings: {exc}")


class VideoDownloader:
    def __init__(self, logger=None, progress=None, cookie_mode=COOKIE_MODE_NONE, cookie_value="", output_dir=""):
        self.logger = logger or (lambda message: None)
        self.progress = progress or (lambda percent, status: None)
        self.cookie_mode = cookie_mode or COOKIE_MODE_NONE
        self.cookie_value = (cookie_value or "").strip()
        self.ffmpeg_location = ensure_ffmpeg_runtime(self.logger)
        self.output_dir = get_download_dir(output_dir)

    def _is_tiktok_url(self, url: str) -> bool:
        hostname = urlparse(url).hostname or ""
        return hostname.endswith("tiktok.com")

    def _clean_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMS
        ]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))

    def _resolve_tiktok_short_url(self, url: str) -> str:
        cleaned = self._clean_url(url)
        parsed = urlparse(cleaned)
        hostname = (parsed.hostname or "").lower()
        if hostname not in {"vm.tiktok.com", "vt.tiktok.com"}:
            return cleaned

        try:
            response = requests.get(
                cleaned,
                allow_redirects=True,
                timeout=12,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                        "Mobile/15E148 Safari/604.1"
                    )
                },
            )
            resolved = self._clean_url(response.url)
            if resolved and resolved != cleaned:
                self.logger(f"Resolved TikTok share URL: {resolved}")
                return resolved
        except Exception as exc:
            self.logger(f"Could not resolve TikTok share URL, using original: {exc}")
        return cleaned

    def prepare_url(self, url: str) -> str:
        cleaned = self._clean_url(url)
        if self._is_tiktok_url(cleaned):
            return self._resolve_tiktok_short_url(cleaned)
        return cleaned

    def _decode_js_string(self, value: str) -> str:
        try:
            return json.loads(f'"{value}"')
        except Exception:
            return value.replace(r"\u002F", "/").replace(r"\u0026", "&")

    def _private_data_dir(self) -> Path:
        app = App.get_running_app()
        if app:
            return Path(app.user_data_dir)
        return _project_root() / ".ffmpeg-downloads"

    def _write_tiktok_session_cookie_file(self, session: requests.Session) -> str | None:
        cookies = list(session.cookies)
        if not cookies:
            return None

        cookie_dir = self._private_data_dir() / "cookies"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = cookie_dir / "tiktok-session.cookies.txt"
        lines = ["# Netscape HTTP Cookie File\n"]
        for cookie in cookies:
            if not cookie.name or cookie.value is None:
                continue
            domain = cookie.domain or ".tiktok.com"
            if domain.endswith("tiktok.com"):
                domain = ".tiktok.com"
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            path = cookie.path or "/"
            secure = "TRUE" if cookie.secure else "FALSE"
            expires = str(cookie.expires or 0)
            value = str(cookie.value).replace("\t", "%09").replace("\r", "").replace("\n", "")
            lines.append("\t".join([domain, include_subdomains, path, secure, expires, cookie.name, value]) + "\n")

        if len(lines) == 1:
            return None
        cookie_file.write_text("".join(lines), encoding="utf-8")
        return str(cookie_file)

    def _extract_tiktok_web_direct(self, url: str) -> dict:
        parsed = urlparse(url)
        match = re.search(r"/video/(\d+)", parsed.path)
        video_id = match.group(1) if match else parsed.path.rstrip("/").rsplit("/", 1)[-1]
        self.logger("Trying TikTok direct webpage fallback...")

        session = requests.Session()
        response = session.get(url, headers=TIKTOK_HEADERS, timeout=20)
        response.raise_for_status()
        webpage = response.text
        video_headers = {**TIKTOK_VIDEO_HEADERS, "Referer": url}
        cookie_file = self._write_tiktok_session_cookie_file(session)
        if cookie_file:
            self.logger("TikTok session cookies prepared for direct download.")

        formats = []
        seen = set()
        for field, quality in (("playAddr", "web-play"), ("downloadAddr", "web-download")):
            for raw_url in re.findall(rf'"{field}"\s*:\s*"([^"]+)"', webpage):
                video_url = self._decode_js_string(raw_url)
                if not video_url or video_url in seen:
                    continue
                seen.add(video_url)
                formats.append(
                    {
                        "format_id": quality if len(formats) == 0 else f"{quality}-{len(formats) + 1}",
                        "url": video_url,
                        "ext": "mp4",
                        "vcodec": "h264",
                        "acodec": "aac",
                        "protocol": "https",
                        "http_headers": dict(video_headers),
                    }
                )

        if not formats:
            raise ExtractorError("TikTok direct webpage fallback found no playable URLs", video_id=video_id)

        def first_json_string(key: str) -> str:
            match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', webpage)
            return self._decode_js_string(match.group(1)) if match else ""

        title = first_json_string("desc") or first_json_string("shareTitle") or f"TikTok video {video_id}"
        thumbnail = first_json_string("cover") or first_json_string("originCover") or first_json_string("dynamicCover")
        uploader = first_json_string("uniqueId") or first_json_string("nickname")

        self.logger(f"TikTok direct fallback found {len(formats)} playable URL(s).")
        return {
            "id": video_id,
            "title": title,
            "description": title,
            "uploader": uploader,
            "webpage_url": url,
            "thumbnail": thumbnail or None,
            "formats": formats,
            "http_headers": dict(video_headers),
            "_antidown_cookiefile": cookie_file,
            "_antidown_direct": True,
        }

    def _default_cookie_file(self) -> Path:
        return self.output_dir / "cookies.txt"

    def _browser_cookie_source(self) -> str | None:
        browsers = {
            COOKIE_MODE_CHROME: "chrome",
            COOKIE_MODE_EDGE: "edge",
            COOKIE_MODE_FIREFOX: "firefox",
        }
        return browsers.get(self.cookie_mode)

    def _apply_cookie_options(self, opts: dict) -> None:
        if self.cookie_mode == COOKIE_MODE_AUTO_FILE:
            cookie_file = self._default_cookie_file()
            if cookie_file.exists():
                opts["cookiefile"] = str(cookie_file)
                self.logger(f"Using cookies file: {cookie_file}")
            else:
                self.logger(f"No cookies file found at: {cookie_file}")
            return

        if self.cookie_mode == COOKIE_MODE_CUSTOM_FILE:
            if not self.cookie_value:
                self.logger("Custom cookies selected but path is empty.")
                return
            cookie_file = Path(self.cookie_value).expanduser()
            if cookie_file.exists():
                opts["cookiefile"] = str(cookie_file)
                self.logger(f"Using cookies file: {cookie_file}")
            else:
                self.logger(f"Cookies file not found: {cookie_file}")
            return

        browser = self._browser_cookie_source()
        if browser:
            if platform == "android":
                self.logger("Browser cookie extraction is not available on Android. Use cookies.txt.")
                return
            profile = self.cookie_value or None
            opts["cookiesfrombrowser"] = (browser, profile, None, None)
            label = f"{browser}:{profile}" if profile else browser
            self.logger(f"Using cookies from browser: {label}")

    def _base_options(self, url: str | None = None, *, tiktok_fallback: bool = False) -> dict:
        opts = {
            "quiet": True,
            "noprogress": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "noplaylist": True,
            "cachedir": False,
            "encoding": "utf-8",
            "no_color": True,
            "logger": YtDlpLogBridge(self.logger),
        }
        if self.ffmpeg_location:
            opts["ffmpeg_location"] = self.ffmpeg_location
        self._apply_cookie_options(opts)
        if url and self._is_tiktok_url(url):
            if platform == "android":
                opts["http_headers"] = TIKTOK_HEADERS
            elif TIKTOK_IMPERSONATE_TARGET:
                opts["impersonate"] = TIKTOK_IMPERSONATE_TARGET
            if tiktok_fallback:
                opts["extractor_args"] = {
                    "tiktok": {
                        "api_hostname": [
                            "api19-normal-c-useast1a.tiktokv.com",
                            "api16-normal-c-useast1a.tiktokv.com",
                        ],
                    }
                }
        return opts

    def extract_info(self, url: str) -> dict:
        url = self.prepare_url(url)
        opts = self._base_options(url)
        opts["skip_download"] = True
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as first_error:
            if not self._is_tiktok_url(url):
                raise
            self.logger(f"TikTok normal extraction failed: {first_error}")
            self.logger("Retrying TikTok with alternate API host...")
            fallback_opts = self._base_options(url, tiktok_fallback=True)
            fallback_opts["skip_download"] = True
            try:
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except Exception as fallback_error:
                self.logger(f"TikTok fallback extraction failed: {fallback_error}")
                try:
                    return self._extract_tiktok_web_direct(url)
                except Exception as direct_error:
                    self.logger(f"TikTok direct fallback failed: {direct_error}")
                    raise first_error

    def list_formats(self, info: dict) -> list[dict]:
        rows = [] if info.get("_antidown_direct") else list(PRESET_FORMATS)
        seen = {row["format_id"] for row in rows}

        for item in info.get("formats") or []:
            format_id = item.get("format_id")
            if not format_id or format_id in seen:
                continue
            seen.add(format_id)

            height = item.get("height") or ""
            ext = item.get("ext") or ""
            vcodec = item.get("vcodec") or ""
            acodec = item.get("acodec") or ""
            filesize = item.get("filesize") or item.get("filesize_approx")
            size_note = f"{round(filesize / 1024 / 1024, 1)} MB" if filesize else ""
            codec_note = []
            if vcodec and vcodec != "none":
                codec_note.append("video")
            if acodec and acodec != "none":
                codec_note.append("audio")

            label_parts = [format_id]
            if height:
                label_parts.append(f"{height}p")
            if ext:
                label_parts.append(ext)
            if size_note:
                label_parts.append(size_note)

            rows.append(
                {
                    "label": " | ".join(label_parts),
                    "format_id": format_id,
                    "ext": ext,
                    "height": height,
                    "note": ", ".join(codec_note),
                }
            )

        return rows

    def download(self, url: str, format_id: str) -> None:
        url = self.prepare_url(url)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(self.output_dir / "%(title).80B [%(id)s] [%(format_id)s].%(ext)s")

        info = self.extract_info(url)
        opts = self._base_options(url, tiktok_fallback=self._is_tiktok_url(url))
        if info.get("_antidown_cookiefile"):
            opts["cookiefile"] = info["_antidown_cookiefile"]
            self.logger("Using TikTok session cookies for direct download.")
        opts.update(
            {
                "format": format_id,
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "progress_hooks": [self._progress_hook],
            }
        )

        self.logger(f"Saving to: {self.output_dir}")
        if self.ffmpeg_location:
            self.logger(f"Using ffmpeg: {self.ffmpeg_location}")
        else:
            self.logger("ffmpeg not found. Some high quality formats may fail.")

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.process_ie_result(info, download=True)

    def _progress_hook(self, data: dict) -> None:
        status = data.get("status", "")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            percent = int(downloaded * 100 / total) if total else 0
            speed = data.get("_speed_str") or ""
            eta = data.get("_eta_str") or ""
            self.progress(percent, f"Downloading {percent}% {speed} ETA {eta}".strip())
        elif status == "finished":
            self.progress(100, "Download finished. Merging/converting if needed...")
        else:
            self.progress(0, status or "Working")
