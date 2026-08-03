import threading
import traceback
import json
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import ListProperty
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from app.core.android_intents import bind_shared_url_handler, extract_first_url, get_initial_shared_url
from app.core.downloader import (
    COOKIE_MODE_AUTO_FILE,
    COOKIE_MODE_CUSTOM_FILE,
    COOKIE_MODE_NONE,
    COOKIE_MODES,
    VideoDownloader,
    get_download_dir,
    get_private_download_dir,
    request_android_permissions,
)
from app.core.webview_cookie import open_cookie_webview


COLORS = {
    "page": (0.95, 0.97, 0.99, 1),
    "surface": (1, 1, 1, 1),
    "text": (0.08, 0.12, 0.19, 1),
    "muted": (0.35, 0.41, 0.49, 1),
    "border": (0.84, 0.87, 0.91, 1),
    "accent": (0.10, 0.42, 0.86, 1),
    "accent_dark": (0.06, 0.29, 0.63, 1),
    "accent_soft": (0.89, 0.94, 1, 1),
    "success": (0.08, 0.53, 0.32, 1),
    "warning": (0.84, 0.46, 0.06, 1),
    "danger": (0.76, 0.20, 0.19, 1),
}

APP_BUILD = "0.1.3 webview-login-overlay"


class Surface(BoxLayout):
    """A restrained panel used to separate related controls."""

    background_color = ListProperty(COLORS["surface"])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._background = Color(*self.background_color)
            self._shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._sync_canvas, size=self._sync_canvas, background_color=self._sync_color)

    def _sync_canvas(self, *_args):
        self._shape.pos = self.pos
        self._shape.size = self.size

    def _sync_color(self, _instance, color):
        self._background.rgba = color


class AppButton(Button):
    def __init__(self, *, fill_color, text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = fill_color
        self.color = text_color
        self.font_size = sp(15)
        self.bold = True
        self.size_hint_y = None
        self.height = dp(48)


class InputField(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = COLORS["surface"]
        self.foreground_color = COLORS["text"]
        self.hint_text_color = COLORS["muted"]
        self.cursor_color = COLORS["accent"]
        self.padding = [dp(14), dp(14), dp(14), dp(10)]
        self.font_size = sp(15)


class AntiDownApp(App):
    title = "AntiDown"

    def build(self):
        self.info = None
        self.formats = []
        self.selected_format = "bestvideo+bestaudio/best"
        self.analyzed_url = ""
        self.settings_data = self.load_user_settings()
        self.cookie_mode = self.settings_data.get("cookie_mode") or COOKIE_MODE_NONE
        self.cookie_value = self.settings_data.get("cookie_value") or ""
        self.save_dir = self.settings_data.get("save_dir") or ""
        self.settings_popup = None

        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*COLORS["page"])
            self._page_background = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._sync_page_background, size=self._sync_page_background)

        root.add_widget(self._build_header())

        scroll = ScrollView(bar_width=dp(3), bar_color=COLORS["accent"], bar_inactive_color=(0, 0, 0, 0))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=[dp(16), dp(16), dp(16), dp(24)],
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(self._build_link_panel())
        content.add_widget(self._build_video_panel())
        content.add_widget(self._build_progress_panel())
        content.add_widget(self._build_log_panel())

        scroll.add_widget(content)
        root.add_widget(scroll)
        Clock.schedule_once(lambda *_: self.apply_initial_shared_url(), 0.4)
        return root

    def _sync_page_background(self, instance, *_args):
        self._page_background.pos = instance.pos
        self._page_background.size = instance.size

    def _build_header(self):
        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(86),
            padding=[dp(18), dp(13), dp(18), dp(10)],
        )
        with header.canvas.before:
            Color(*COLORS["accent_dark"])
            self._header_background = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._sync_header_background, size=self._sync_header_background)

        title_row = BoxLayout(spacing=dp(10))
        mark = Label(
            text="AD",
            color=(1, 1, 1, 1),
            font_size=sp(18),
            bold=True,
            size_hint_x=None,
            width=dp(38),
            halign="center",
            valign="middle",
        )
        mark.bind(size=lambda instance, *_: setattr(instance, "text_size", instance.size))
        title = Label(
            text="AntiDown",
            color=(1, 1, 1, 1),
            font_size=sp(23),
            bold=True,
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda instance, *_: setattr(instance, "text_size", instance.size))
        settings_button = AppButton(
            text="Settings",
            fill_color=(0.80, 0.89, 1, 1),
            text_color=COLORS["accent_dark"],
            size_hint_x=None,
            width=dp(94),
        )
        settings_button.height = dp(36)
        settings_button.font_size = sp(13)
        settings_button.bind(on_press=lambda *_: self.open_settings())
        title_row.add_widget(mark)
        title_row.add_widget(title)
        title_row.add_widget(settings_button)
        header.add_widget(title_row)

        subtitle = Label(
            text="Tải video cho mục đích cá nhân",
            color=(0.80, 0.89, 1, 1),
            font_size=sp(13),
            halign="left",
            valign="middle",
            padding=[dp(48), 0],
        )
        subtitle.bind(size=lambda instance, *_: setattr(instance, "text_size", instance.size))
        header.add_widget(subtitle)
        return header

    def _sync_header_background(self, instance, *_args):
        self._header_background.pos = instance.pos
        self._header_background.size = instance.size

    def _label(self, text, *, color=None, size=14, height=None, bold=False):
        label = Label(
            text=text,
            color=color or COLORS["text"],
            font_size=sp(size),
            bold=bold,
            halign="left",
            valign="middle",
        )
        if height is not None:
            label.size_hint_y = None
            label.height = dp(height)
        label.bind(size=lambda instance, *_: setattr(instance, "text_size", instance.size))
        return label

    def settings_path(self) -> Path:
        return Path(self.user_data_dir) / "settings.json"

    def load_user_settings(self) -> dict:
        path = self.settings_path()
        defaults = {
            "cookie_mode": COOKIE_MODE_NONE,
            "cookie_value": "",
            "save_dir": "",
        }
        try:
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                defaults.update({key: loaded.get(key, value) for key, value in defaults.items()})
        except Exception:
            pass
        return defaults

    def save_user_settings(self) -> None:
        self.settings_data = {
            "cookie_mode": self.cookie_mode,
            "cookie_value": self.cookie_value,
            "save_dir": self.save_dir,
        }
        path = self.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.settings_data, indent=2), encoding="utf-8")

    def current_save_dir(self) -> Path:
        return get_download_dir(self.save_dir)

    def update_save_dir_text(self):
        if hasattr(self, "save_dir_label"):
            self.save_dir_label.text = f"Lưu vào: {self.current_save_dir()}"

    def cookie_hint(self, mode):
        if mode == COOKIE_MODE_AUTO_FILE:
            return "Dùng Download/AntiDown/cookies.txt"
        if mode == COOKIE_MODE_CUSTOM_FILE:
            return "Đường dẫn đầy đủ đến cookies.txt"
        if mode.endswith("desktop"):
            return "Tên profile trình duyệt (không bắt buộc)"
        return "Không dùng cookie"

    def open_settings(self):
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=[dp(14), dp(12), dp(14), dp(14)],
        )

        content.add_widget(self._label("Cookie / login", size=16, height=28, bold=True))
        cookie_spinner = Spinner(
            text=self.cookie_mode,
            values=COOKIE_MODES,
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_down="",
            background_color=COLORS["accent_soft"],
            color=COLORS["text"],
            font_size=sp(14),
        )
        content.add_widget(cookie_spinner)

        cookie_input = InputField(
            text=self.cookie_value,
            hint_text=self.cookie_hint(self.cookie_mode),
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        cookie_spinner.bind(text=lambda _spinner, value: self.apply_cookie_hint(cookie_input, value))
        content.add_widget(cookie_input)

        login_button = AppButton(
            text="Đăng nhập bằng WebView nội bộ",
            fill_color=COLORS["accent_soft"],
            text_color=COLORS["accent_dark"],
        )
        login_button.height = dp(42)
        login_button.bind(on_press=lambda *_: self.start_login_webview(cookie_spinner, cookie_input))
        content.add_widget(login_button)

        content.add_widget(self._label("Thư mục lưu", size=16, height=28, bold=True))
        save_dir_input = InputField(
            text=self.save_dir,
            hint_text=str(get_download_dir()),
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        content.add_widget(save_dir_input)

        folder_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        default_button = AppButton(
            text="Download",
            fill_color=COLORS["surface"],
            text_color=COLORS["accent_dark"],
        )
        default_button.height = dp(40)
        default_button.bind(on_press=lambda *_: self.use_default_download_dir(save_dir_input))
        choose_button = AppButton(
            text="Chọn thư mục",
            fill_color=COLORS["surface"],
            text_color=COLORS["accent_dark"],
        )
        choose_button.height = dp(40)
        choose_button.bind(on_press=lambda *_: self.open_folder_picker(save_dir_input))
        folder_row.add_widget(default_button)
        folder_row.add_widget(choose_button)
        content.add_widget(folder_row)

        permission_button = AppButton(
            text="Cấp quyền Android",
            fill_color=COLORS["accent_soft"],
            text_color=COLORS["accent_dark"],
        )
        permission_button.height = dp(40)
        permission_button.bind(
            on_press=lambda *_: request_android_permissions(
                self.thread_log,
                open_all_files_settings=True,
            )
        )
        content.add_widget(permission_button)

        ffmpeg_check_button = AppButton(
            text="Kiểm tra ffmpeg",
            fill_color=COLORS["accent_soft"],
            text_color=COLORS["accent_dark"],
        )
        ffmpeg_check_button.height = dp(40)
        ffmpeg_check_button.bind(on_press=lambda *_: self.check_ffmpeg_runtime())
        content.add_widget(ffmpeg_check_button)

        action_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel_button = AppButton(
            text="Đóng",
            fill_color=COLORS["surface"],
            text_color=COLORS["muted"],
        )
        save_button = AppButton(text="Lưu Settings", fill_color=COLORS["accent"])
        action_row.add_widget(cancel_button)
        action_row.add_widget(save_button)
        content.add_widget(action_row)

        popup = Popup(title="Settings", content=content, size_hint=(0.92, 0.86))
        cancel_button.bind(on_press=lambda *_: popup.dismiss())
        save_button.bind(
            on_press=lambda *_: self.apply_settings_popup(
                popup,
                cookie_spinner.text,
                cookie_input.text,
                save_dir_input.text,
            )
        )
        self.settings_popup = popup
        popup.open()

    def apply_cookie_hint(self, cookie_input, mode):
        if mode in (COOKIE_MODE_NONE, COOKIE_MODE_AUTO_FILE):
            cookie_input.text = ""
        cookie_input.hint_text = self.cookie_hint(mode)

    def use_default_download_dir(self, save_dir_input):
        if platform == "android":
            save_dir_input.text = "/storage/emulated/0/Download/AntiDown"
        else:
            save_dir_input.text = str(get_download_dir())

    def open_folder_picker(self, save_dir_input):
        start_path = save_dir_input.text.strip() or str(get_download_dir())
        if not Path(start_path).exists():
            start_path = str(get_private_download_dir())

        chooser = FileChooserListView(path=start_path, dirselect=True)
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        content.add_widget(chooser)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel_button = AppButton(text="Đóng", fill_color=COLORS["surface"], text_color=COLORS["muted"])
        select_button = AppButton(text="Chọn", fill_color=COLORS["accent"])
        row.add_widget(cancel_button)
        row.add_widget(select_button)
        content.add_widget(row)

        popup = Popup(title="Chọn thư mục lưu", content=content, size_hint=(0.94, 0.88))

        def choose_folder(*_args):
            selected = chooser.selection[0] if chooser.selection else chooser.path
            save_dir_input.text = selected
            popup.dismiss()

        cancel_button.bind(on_press=lambda *_: popup.dismiss())
        select_button.bind(on_press=choose_folder)
        popup.open()

    def apply_settings_popup(self, popup, cookie_mode, cookie_value, save_dir):
        self.cookie_mode = cookie_mode or COOKIE_MODE_NONE
        self.cookie_value = (cookie_value or "").strip()
        self.save_dir = (save_dir or "").strip()
        self.save_user_settings()
        self.update_save_dir_text()
        self.write_log(f"Đã lưu Settings. Thư mục lưu: {self.current_save_dir()}")
        popup.dismiss()

    def check_ffmpeg_runtime(self):
        self.write_log("Đang kiểm tra ffmpeg...")
        downloader = self.get_downloader()
        if downloader.ffmpeg_location:
            self.write_log(f"ffmpeg_location: {downloader.ffmpeg_location}")
        else:
            self.write_log("Không tìm thấy ffmpeg runtime.")

    def bind_android_share(self):
        bind_shared_url_handler(self.receive_shared_url, logger=self.thread_log)

    def apply_initial_shared_url(self):
        url = get_initial_shared_url(logger=self.thread_log)
        if url:
            self.receive_shared_url(url)

    def receive_shared_url(self, url):
        if not url:
            return
        Clock.schedule_once(lambda *_: self.apply_shared_url(url), 0)

    def apply_shared_url(self, url):
        try:
            self.url_input.text = url
            self.write_log(f"Đã nhận link từ Share: {url}")
            self.set_status("Đã nhận link share", "Bấm Phân tích liên kết để chọn chất lượng tải.", COLORS["success"])
        except Exception:
            self.thread_log(traceback.format_exc())

    def _build_link_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(12),
            size_hint_y=None,
            height=dp(205),
        )
        panel.add_widget(self._label("1. Dán liên kết video", size=16, height=25, bold=True))
        panel.add_widget(self._label("Hỗ trợ YouTube, TikTok, Facebook và nhiều trang khác.", color=COLORS["muted"], size=13, height=22))

        self.url_input = InputField(
            hint_text="https://...",
            multiline=False,
            size_hint_y=None,
            height=dp(50),
        )
        self.url_input.bind(text=self.on_url_changed)
        panel.add_widget(self.url_input)

        self.analyze_button = AppButton(text="Phân tích liên kết", fill_color=COLORS["accent"])
        self.analyze_button.bind(on_press=lambda *_: self.start_analyze())
        panel.add_widget(self.analyze_button)
        return panel

    def _build_video_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(7),
            padding=dp(12),
            size_hint_y=None,
            height=dp(254),
        )
        panel.add_widget(self._label("2. Chọn phiên bản tải", size=16, height=25, bold=True))
        self.video_title = self._label("Chưa phân tích video", color=COLORS["muted"], size=14, height=44)
        panel.add_widget(self.video_title)

        self.format_spinner = Spinner(
            text="Chất lượng tốt nhất (video + âm thanh)",
            values=(
                "Chất lượng tốt nhất (video + âm thanh)",
                "MP4 tốt nhất nếu có",
                "Chỉ tải âm thanh",
            ),
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_down="",
            background_color=COLORS["accent_soft"],
            color=COLORS["text"],
            font_size=sp(14),
        )
        self.format_spinner.bind(text=self.on_format_selected)
        panel.add_widget(self.format_spinner)

        self.format_note = self._label(
            "Phân tích liên kết để xem chất lượng có sẵn.",
            color=COLORS["muted"],
            size=13,
            height=24,
        )
        panel.add_widget(self.format_note)

        self.download_button = AppButton(text="Tải xuống", fill_color=COLORS["accent"],)
        self.download_button.disabled = True
        self.download_button.bind(on_press=lambda *_: self.start_download())
        panel.add_widget(self.download_button)
        return panel

    def _build_progress_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(12),
            size_hint_y=None,
            height=dp(150),
        )
        row = BoxLayout(size_hint_y=None, height=dp(25))
        row.add_widget(self._label("Trạng thái", size=16, bold=True))
        self.progress_percent = self._label("Sẵn sàng", color=COLORS["success"], size=13)
        self.progress_percent.halign = "right"
        row.add_widget(self.progress_percent)
        panel.add_widget(row)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(12))
        panel.add_widget(self.progress)
        self.progress_detail = self._label("Video sẽ được lưu trong thư mục Download/AntiDown.", color=COLORS["muted"], size=13, height=32)
        panel.add_widget(self.progress_detail)
        self.save_dir_label = self._label("", color=COLORS["muted"], size=12, height=24)
        panel.add_widget(self.save_dir_label)
        self.update_save_dir_text()
        return panel

    def _build_log_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(6),
            padding=dp(12),
            size_hint_y=None,
            height=dp(220),
        )
        heading = BoxLayout(size_hint_y=None, height=dp(25))
        heading.add_widget(self._label("Nhật ký hoạt động", size=16, bold=True))
        clear_button = AppButton(
            text="Xóa",
            fill_color=COLORS["surface"],
            text_color=COLORS["accent_dark"],
            size_hint_x=None,
            width=dp(58),
        )
        clear_button.height = dp(28)
        clear_button.font_size = sp(13)
        clear_button.bind(on_press=lambda *_: self.clear_log())
        heading.add_widget(clear_button)
        panel.add_widget(heading)

        self.log = InputField(
            text=f"AntiDown build {APP_BUILD}\nSẵn sàng. Dán liên kết video để bắt đầu.\n",
            readonly=True,
            multiline=True,
            font_size=sp(12),
        )
        self.log.background_color = (0.97, 0.98, 1, 1)
        panel.add_widget(self.log)
        return panel

    def on_url_changed(self, _input, value):
        if self.analyzed_url and value.strip() != self.analyzed_url:
            self.info = None
            self.formats = []
            self.download_button.disabled = True
            self.video_title.text = "Liên kết đã thay đổi. Hãy phân tích lại."
            self.format_note.text = "Chọn Phân tích liên kết để cập nhật chất lượng."

    def on_format_selected(self, _spinner, value):
        for item in self.formats:
            if item["label"] == value:
                self.selected_format = item["format_id"]
                self.format_note.text = self._format_note(item)
                return
        preset_map = {
            "Chất lượng tốt nhất (video + âm thanh)": "bestvideo+bestaudio/best",
            "MP4 tốt nhất nếu có": "best[ext=mp4]/best",
            "Chỉ tải âm thanh": "bestaudio/best",
        }
        self.selected_format = preset_map.get(value, value)

    def _format_note(self, item):
        preset_notes = {
            "bestvideo+bestaudio/best": "Video và âm thanh tốt nhất. Có thể cần ghép bằng ffmpeg.",
            "best[ext=mp4]/best": "Ưu tiên MP4 để tương thích tốt hơn.",
            "bestaudio/best": "Chỉ tải âm thanh chất lượng tốt nhất.",
        }
        if item.get("format_id") in preset_notes:
            return preset_notes[item["format_id"]]
        parts = []
        if item.get("height"):
            parts.append(f"Độ phân giải {item['height']}p")
        if item.get("ext"):
            parts.append(item["ext"].upper())
        if item.get("note"):
            note = item["note"].replace("video", "video").replace("audio", "âm thanh")
            parts.append(note)
        return " | ".join(parts) or "Định dạng do trang nguồn cung cấp."

    def get_downloader(self):
        return VideoDownloader(
            logger=self.thread_log,
            progress=self.thread_progress,
            cookie_mode=self.cookie_mode,
            cookie_value=self.cookie_value,
            output_dir=self.save_dir,
        )

    def guess_login_url(self):
        raw_url = self.url_input.text.strip()
        lowered = raw_url.lower()
        if "tiktok.com" in lowered:
            return "https://www.tiktok.com/login"
        if "youtube.com" in lowered or "youtu.be" in lowered or "google.com" in lowered:
            return "https://accounts.google.com/ServiceLogin?service=youtube"
        if "facebook.com" in lowered or "fb.watch" in lowered:
            return "https://www.facebook.com/login"
        if "instagram.com" in lowered:
            return "https://www.instagram.com/accounts/login/"
        if "twitter.com" in lowered or "x.com" in lowered:
            return "https://x.com/i/flow/login"
        if raw_url.startswith(("http://", "https://")):
            return raw_url
        return "https://www.tiktok.com/login"

    def start_login_webview(self, cookie_spinner=None, cookie_input=None):
        self.cookie_mode = COOKIE_MODE_AUTO_FILE
        self.cookie_value = ""
        if cookie_spinner is not None:
            cookie_spinner.text = COOKIE_MODE_AUTO_FILE
        if cookie_input is not None:
            cookie_input.text = ""
            cookie_input.hint_text = self.cookie_hint(COOKIE_MODE_AUTO_FILE)
        self.save_user_settings()
        start_url = self.guess_login_url()
        self.set_status("Mở trang đăng nhập", "Đăng nhập rồi nhấn lưu cookie.", COLORS["warning"])
        self.write_log(f"Mở WebView đăng nhập: {start_url}")
        if self.settings_popup is not None:
            self.settings_popup.dismiss()
        open_cookie_webview(start_url, logger=self.thread_log)

    def start_analyze(self):
        raw_url = self.url_input.text.strip()
        url = extract_first_url(raw_url) or raw_url
        if not url:
            self.write_log("Hãy dán liên kết video trước.")
            self.set_status("Thiếu liên kết", "Dán URL video rồi thử lại.", COLORS["danger"])
            return
        if url != raw_url:
            self.url_input.text = url
            self.write_log(f"Đã lọc link chuẩn: {url}")

        self.set_busy(True)
        self.set_status("Đang phân tích", "Đang lấy tiêu đề và các định dạng có sẵn...", COLORS["warning"])
        self.write_log("Đang phân tích liên kết...")
        threading.Thread(target=self._analyze_worker, args=(url,), daemon=True).start()

    def _analyze_worker(self, url):
        try:
            downloader = self.get_downloader()
            prepared_url = downloader.prepare_url(url)
            info = downloader.extract_info(prepared_url)
            formats = downloader.list_formats(info)
            Clock.schedule_once(lambda *_: self.apply_info(prepared_url, info, formats), 0)
        except Exception:
            self.thread_log(traceback.format_exc())
            Clock.schedule_once(lambda *_: self.analysis_failed(), 0)

    def analysis_failed(self):
        self.set_busy(False)
        self.set_status("Không thể phân tích", "Kiểm tra lại link, cookie hoặc thử lại sau.", COLORS["danger"])

    def apply_info(self, url, info, formats):
        self.info = info
        self.formats = [self._localize_format(item) for item in formats]
        self.analyzed_url = url
        if self.url_input.text.strip() != url:
            self.url_input.text = url
        title = info.get("title") or "Video chưa có tiêu đề"
        duration = info.get("duration")
        duration_text = self._format_duration(duration)
        self.video_title.text = f"{title}\n{duration_text}" if duration_text else title

        values = [item["label"] for item in self.formats]
        self.format_spinner.values = values
        if values:
            self.format_spinner.text = values[0]
            self.selected_format = self.formats[0]["format_id"]
            self.format_note.text = self._format_note(self.formats[0])
        self.download_button.disabled = False
        self.set_busy(False)
        self.set_status("Sẵn sàng tải", f"Đã tìm thấy {len(self.formats)} lựa chọn định dạng.", COLORS["success"])
        self.write_log(f"Đã tìm thấy {len(self.formats)} lựa chọn định dạng.")

    @staticmethod
    def _localize_format(item):
        translated = dict(item)
        preset_labels = {
            "bestvideo+bestaudio/best": "Chất lượng tốt nhất (video + âm thanh)",
            "best[ext=mp4]/best": "MP4 tốt nhất nếu có",
            "bestaudio/best": "Chỉ tải âm thanh",
        }
        translated["label"] = preset_labels.get(item.get("format_id"), item.get("label", "Định dạng không rõ"))
        return translated

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return ""
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"Thời lượng: {hours}:{minutes:02d}:{seconds:02d}" if hours else f"Thời lượng: {minutes}:{seconds:02d}"

    def start_download(self):
        url = self.url_input.text.strip()
        if not url:
            self.write_log("Hãy dán liên kết video trước.")
            return
        if not self.info or url != self.analyzed_url:
            self.write_log("Hãy phân tích lại liên kết trước khi tải.")
            self.set_status("Cần phân tích lại", "Liên kết đã thay đổi hoặc chưa có dữ liệu video.", COLORS["warning"])
            return
        self.set_busy(True)
        self.progress.value = 0
        self.set_status("Đang tải 0%", "Đang chuẩn bị tệp tải xuống...", COLORS["accent"])
        self.write_log(f"Bắt đầu tải định dạng: {self.selected_format}")
        threading.Thread(target=self._download_worker, args=(url, self.selected_format), daemon=True).start()

    def _download_worker(self, url, format_id):
        try:
            downloader = self.get_downloader()
            downloader.download(url, format_id)
            self.thread_progress(100, "Hoàn tất.")
            self.thread_log("Tải xuống hoàn tất.")
        except Exception:
            self.thread_log(traceback.format_exc())
            Clock.schedule_once(lambda *_: self.set_status("Tải thất bại", "Xem nhật ký để biết chi tiết.", COLORS["danger"]), 0)
        finally:
            Clock.schedule_once(lambda *_: self.set_busy(False), 0)

    def set_busy(self, busy):
        self.analyze_button.disabled = busy
        self.download_button.disabled = busy or self.info is None

    def thread_log(self, message):
        Clock.schedule_once(lambda *_: self.write_log(message), 0)

    def thread_progress(self, percent, status):
        Clock.schedule_once(lambda *_: self.apply_progress(percent, status), 0)

    def apply_progress(self, percent, status):
        value = max(0, min(100, percent))
        self.progress.value = value
        if value >= 100 and "Hoàn tất" in status:
            self.set_status("Hoàn tất", "Video đã được lưu trong Download/AntiDown.", COLORS["success"])
        else:
            self.set_status(f"Đang tải {value}%", status or "Đang xử lý...", COLORS["accent"])
        if status:
            self.write_log(status)

    def set_status(self, title, detail, color):
        self.progress_percent.text = title
        self.progress_percent.color = color
        self.progress_detail.text = detail

    def clear_log(self):
        self.log.text = ""

    def write_log(self, message):
        if not message:
            return
        self.log.text += str(message).rstrip() + "\n"
        self.log.cursor = (0, len(self.log.text.splitlines()))
