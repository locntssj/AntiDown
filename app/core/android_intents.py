import re

from kivy.utils import platform


URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_INTENT_CALLBACKS = []


def extract_first_url(text: str | None) -> str:
    if not text:
        return ""
    match = URL_PATTERN.search(str(text))
    return match.group(0).rstrip(").,;]") if match else ""


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
