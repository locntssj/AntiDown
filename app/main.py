import threading
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from app.core.downloader import COOKIE_MODE_NONE, COOKIE_MODES, VideoDownloader, request_android_permissions
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
        request_android_permissions()
        self.info = None
        self.formats = []
        self.selected_format = "bestvideo+bestaudio/best"
        self.analyzed_url = ""

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
        content.add_widget(self._build_options_panel())
        content.add_widget(self._build_progress_panel())
        content.add_widget(self._build_log_panel())

        scroll.add_widget(content)
        root.add_widget(scroll)
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
        title_row.add_widget(mark)
        title_row.add_widget(title)
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

    def _build_options_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(12),
            size_hint_y=None,
            height=dp(245),
        )
        panel.add_widget(self._label("Tùy chọn đăng nhập", size=16, height=25, bold=True))
        panel.add_widget(self._label("Dùng khi video riêng tư hoặc cần phiên đăng nhập.", color=COLORS["muted"], size=13, height=22))

        self.cookie_spinner = Spinner(
            text=COOKIE_MODE_NONE,
            values=COOKIE_MODES,
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_down="",
            background_color=COLORS["surface"],
            color=COLORS["text"],
            font_size=sp(14),
        )
        self.cookie_spinner.bind(text=self.on_cookie_mode_selected)
        panel.add_widget(self.cookie_spinner)

        self.cookie_input = InputField(
            hint_text="Không dùng cookie",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        panel.add_widget(self.cookie_input)

        self.login_button = AppButton(
            text="Đăng nhập bằng WebView nội bộ",
            fill_color=COLORS["accent_soft"],
            text_color=COLORS["accent_dark"],
        )
        self.login_button.height = dp(42)
        self.login_button.bind(on_press=lambda *_: self.start_login_webview())
        panel.add_widget(self.login_button)
        return panel

    def _build_progress_panel(self):
        panel = Surface(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(12),
            size_hint_y=None,
            height=dp(125),
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
            text="Sẵn sàng. Dán liên kết video để bắt đầu.\n",
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

    def on_cookie_mode_selected(self, _spinner, value):
        if value == "Auto cookies.txt":
            self.cookie_input.text = ""
            self.cookie_input.hint_text = "Dùng Download/AntiDown/cookies.txt"
        elif value == "Custom cookies.txt":
            self.cookie_input.hint_text = "Đường dẫn đầy đủ đến cookies.txt"
        elif value.endswith("desktop"):
            self.cookie_input.hint_text = "Tên profile trình duyệt (không bắt buộc)"
        else:
            self.cookie_input.text = ""
            self.cookie_input.hint_text = "Không dùng cookie"

    def get_downloader(self):
        return VideoDownloader(
            logger=self.thread_log,
            progress=self.thread_progress,
            cookie_mode=self.cookie_spinner.text,
            cookie_value=self.cookie_input.text.strip(),
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

    def start_login_webview(self):
        self.cookie_spinner.text = "Auto cookies.txt"
        start_url = self.guess_login_url()
        self.set_status("Mở trang đăng nhập", "Đăng nhập rồi nhấn lưu cookie.", COLORS["warning"])
        self.write_log(f"Mở WebView đăng nhập: {start_url}")
        open_cookie_webview(start_url, logger=self.thread_log)

    def start_analyze(self):
        url = self.url_input.text.strip()
        if not url:
            self.write_log("Hãy dán liên kết video trước.")
            self.set_status("Thiếu liên kết", "Dán URL video rồi thử lại.", COLORS["danger"])
            return

        self.set_busy(True)
        self.set_status("Đang phân tích", "Đang lấy tiêu đề và các định dạng có sẵn...", COLORS["warning"])
        self.write_log("Đang phân tích liên kết...")
        threading.Thread(target=self._analyze_worker, args=(url,), daemon=True).start()

    def _analyze_worker(self, url):
        try:
            downloader = self.get_downloader()
            info = downloader.extract_info(url)
            formats = downloader.list_formats(info)
            Clock.schedule_once(lambda *_: self.apply_info(url, info, formats), 0)
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
        self.login_button.disabled = busy

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
