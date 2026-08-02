import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from kivy.utils import platform


URL_PATTERN = re.compile(r"https?://[^\s\"'<>\]\)]+", re.IGNORECASE)
_INTENT_CALLBACKS = []
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


def _clean_url(url: str) -> str:
    cleaned = str(url or "").strip().strip("*_`")
    cleaned = cleaned.rstrip(").,;]").strip().strip("*_`")
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return ""

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))


def extract_urls(text: str | None) -> list[str]:
    if not text:
        return []

    found = []
    seen = set()
    for match in URL_PATTERN.finditer(str(text)):
        url = _clean_url(match.group(0))
        if url and url not in seen:
            found.append(url)
            seen.add(url)
    return found


def _url_score(url: str) -> tuple[int, int]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    score = 0
    if "tiktok.com" in host:
        score += 20
    if "tiktoklite" in path:
        score -= 30
    if host in {"vm.tiktok.com", "vt.tiktok.com"}:
        score += 10
    if "/@/" in path or "/video/" in path or re.search(r"/@[^/]+/video/\d+", path):
        score += 12
    return score, -len(url)


def extract_first_url(text: str | None) -> str:
    urls = extract_urls(text)
    if not urls:
        return ""
    return max(urls, key=_url_score)


def _intent_text(intent) -> str:
    if platform != "android" or intent is None:
        return ""

    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    action = intent.getAction()

    if action == Intent.ACTION_SEND:
        value = intent.getStringExtra(Intent.EXTRA_TEXT)
        return str(value) if value else ""

    if action == Intent.ACTION_VIEW:
        value = intent.getDataString()
        return str(value) if value else ""

    try:
        value = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)
        return str(value) if value else ""
    except Exception:
        return ""


def get_initial_shared_url(logger=None) -> str:
    logger = logger or (lambda message: None)
    if platform != "android":
        return ""

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        intent = PythonActivity.mActivity.getIntent()
        return extract_first_url(_intent_text(intent))
    except Exception as exc:
        logger(f"Could not read Android share intent: {exc}")
        return ""


def bind_shared_url_handler(callback, logger=None) -> bool:
    logger = logger or (lambda message: None)
    if platform != "android":
        return False

    try:
        from android import activity

        def on_new_intent(intent):
            url = extract_first_url(_intent_text(intent))
            if url:
                callback(url)

        activity.bind(on_new_intent=on_new_intent)
        _INTENT_CALLBACKS.append(on_new_intent)
        return True
    except Exception as exc:
        logger(f"Could not bind Android share listener: {exc}")
        return False
