"""Распознавание текста встроенным в систему OCR — без Tesseract.

Windows — Windows.Media.Ocr (пакеты winrt-*), macOS — Apple Vision (pyobjc-framework-Vision).
Если их нет или система не умеет OCR, read_text() возвращает "" — журнал улова тогда группирует
рыбу по иконке.
"""
import asyncio
import sys

_engine = None
_unavailable = False


def _get_engine():
    global _engine, _unavailable
    if _engine is not None or _unavailable:
        return _engine
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
        # Текст в GPO английский: сначала английский движок, иначе — языки профиля
        engine = None
        try:
            if OcrEngine.is_language_supported(Language("en-US")):
                engine = OcrEngine.try_create_from_language(Language("en-US"))
        except Exception:
            engine = None
        _engine = engine or OcrEngine.try_create_from_user_profile_languages()
        if _engine is None:
            _unavailable = True
    except Exception:
        _unavailable = True
    return _engine


def available():
    if sys.platform == "darwin":
        return _vision() is not None
    return sys.platform == "win32" and _get_engine() is not None


_vision_mod = None


def _vision():
    global _vision_mod, _unavailable
    if _vision_mod is None and not _unavailable:
        try:
            import Quartz
            import Vision
            _vision_mod = (Vision, Quartz)
        except Exception:
            _unavailable = True
    return _vision_mod


def _recognize_mac(rgb):
    """Apple Vision: строки со словами и рамками в пикселях картинки (начало координат — сверху слева)."""
    import numpy as np
    from Foundation import NSData, NSMakeRange
    Vision, Quartz = _vision()
    h, w = rgb.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = 255
    raw = rgba.tobytes()
    provider = Quartz.CGDataProviderCreateWithCFData(NSData.dataWithBytes_length_(raw, len(raw)))
    image = Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                                 Quartz.kCGImageAlphaNoneSkipLast, provider, None, False,
                                 Quartz.kCGRenderingIntentDefault)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)        # названия рыб — не словарные слова
    request.setRecognitionLanguages_(["en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision: {error}")

    def box(r):   # нормированная рамка Vision (начало снизу слева) → пиксели (начало сверху слева)
        return (r.origin.x * w, (1 - r.origin.y - r.size.height) * h, r.size.width * w, r.size.height * h)

    lines = []
    for obs in request.results() or []:
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        cand = candidates[0]
        text = str(cand.string())
        words, pos = [], 0
        for word in text.split():
            start = text.find(word, pos)
            pos = start + len(word)
            rect, _err = cand.boundingBoxForRange_error_(NSMakeRange(start, len(word)), None)
            words.append((word, box(rect.boundingBox() if rect is not None else obs.boundingBox())))
        lines.append({"text": text, "words": words, "_y": box(obs.boundingBox())[1]})
    lines.sort(key=lambda line: line.pop("_y"))       # сверху вниз, как у Windows OCR
    return lines


async def _recognize(engine, rgb):
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter
    h, w = rgb.shape[:2]
    import numpy as np
    bgra = np.empty((h, w, 4), dtype=np.uint8)
    bgra[:, :, 0] = rgb[:, :, 2]
    bgra[:, :, 1] = rgb[:, :, 1]
    bgra[:, :, 2] = rgb[:, :, 0]
    bgra[:, :, 3] = 255
    writer = DataWriter()
    writer.write_bytes(bgra.tobytes())
    buffer = writer.detach_buffer()
    try:
        bitmap = SoftwareBitmap.create_copy_from_buffer(buffer, BitmapPixelFormat.BGRA8, w, h)
    except TypeError:
        # В разных версиях winrt разный набор перегрузок — запасной путь
        bitmap = SoftwareBitmap(BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED)
        bitmap.copy_from_buffer(buffer)
    result = await engine.recognize_async(bitmap)
    lines = []
    for line in result.lines:
        words = []
        for w in line.words:
            r = w.bounding_rect
            words.append((w.text, (r.x, r.y, r.width, r.height)))
        lines.append({"text": line.text, "words": words})
    return {"text": result.text or "", "lines": lines}


last_error = None


def read_lines(rgb, raise_errors=False):
    """Строки текста со словами и их рамками в координатах исходной картинки:
    [{"text": "New Item <Fangfish>", "words": [("New", (x, y, w, h)), …]}, …]"""
    global last_error
    mac = sys.platform == "darwin"
    engine = _get_engine() if sys.platform == "win32" else None
    if engine is None and not (mac and _vision() is not None):
        return []
    # Мелкий игровой текст OCR читает лучше, если картинку увеличить
    from PIL import Image
    import numpy as np
    img = Image.fromarray(np.ascontiguousarray(rgb))
    k = 1.0
    if img.height < 60:
        k = 60 / max(img.height, 1)
        img = img.resize((int(img.width * k), 60), Image.LANCZOS)
    try:
        pixels = np.ascontiguousarray(np.asarray(img))
        data = {"lines": _recognize_mac(pixels)} if mac else asyncio.run(_recognize(engine, pixels))
    except Exception as exc:
        last_error = exc
        if raise_errors:
            raise
        return []
    for line in data["lines"]:
        line["words"] = [(t, tuple(v / k for v in rect)) for t, rect in line["words"]]
    return data["lines"]


def read_text(rgb, raise_errors=False):
    """rgb — HxWx3 uint8. Распознанный текст или "" (ошибку — в ocr.last_error)."""
    return "\n".join(line["text"] for line in read_lines(rgb, raise_errors))
