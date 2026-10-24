"""Ввод мыши и клавиатуры: Windows — WinAPI SendInput, macOS — события Quartz (CGEvent).

Roblox игнорирует часть «программных» событий (например, PostMessage),
поэтому шлём настоящие аппаратные события со скан-кодами.
На macOS программе нужно разрешение «Универсальный доступ» (Accessibility) — без него
система молча выбрасывает события. На других системах модуль ничего не делает (для тестов).
Координаты на macOS — в пунктах экрана (как у Tk и mss), а не в пикселях Retina.
"""
import ctypes
import sys
import time
from .i18n import tr

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
CAN_CONTROL = IS_WINDOWS or IS_MAC      # есть настоящий ввод и поиск окна Roblox
ROBLOX = "Roblox"                       # так называется окно (Windows) или приложение (macOS)

# «Anti-Detect Micro Delay»: пауза между абсолютным перемещением и подёргиванием курсора
micro_delay = 0.05

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

# Виртуальные коды для клавиш, которые нам нужны
VK = {str(d): 0x30 + d for d in range(10)}
VK.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({f"f{i}": 0x6F + i for i in range(1, 13)})
VK.update({"enter": 0x0D, "esc": 0x1B, "space": 0x20, "backspace": 0x08, "tab": 0x09,
           "shift": 0x10, "alt": 0x12})


if IS_WINDOWS:
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)

    def _send(*inputs):
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _mouse(flags, dx=0, dy=0):
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi = MOUSEINPUT(dx, dy, 0, flags, 0, 0)
        return inp

    def _key(vk, up=False):
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = KEYBDINPUT(0, scan, flags, 0, 0)
        return inp


# Коды клавиш macOS (раскладка ANSI; кнопку жмём физически, буква от раскладки не зависит)
MAC_KEYS = {"a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
            "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
            "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38,
            "k": 40, "n": 45, "m": 46, "enter": 36, "tab": 48, "space": 49, "backspace": 51, "esc": 53,
            "shift": 56, "alt": 58, "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
            "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111}

if IS_MAC:
    try:
        import Quartz
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace
    except ImportError:          # без pyobjc (разработка) — как на прочих системах
        Quartz = None

    _held = False                # ЛКМ зажата: движение мыши — это «перетаскивание»

    def _post(event):
        if Quartz is not None and event is not None:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _cursor():
        return Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))

    def _mouse_event(kind, point):
        return Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)

    def _roblox_app():
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if app.localizedName() in (ROBLOX, "RobloxPlayer"):
                return app
        return None


def set_dpi_aware():
    """Чтобы координаты мыши совпадали с пикселями скриншота при масштабе 125%/150%."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def move_to(x, y):
    if IS_MAC:
        if Quartz is None:
            return
        kind = Quartz.kCGEventLeftMouseDragged if _held else Quartz.kCGEventMouseMoved
        _post(_mouse_event(kind, (float(x), float(y))))
        # Как и на Windows: Roblox замечает курсор только после небольшого движения
        time.sleep(micro_delay)
        _post(_mouse_event(kind, (float(x) + 1, float(y))))
        _post(_mouse_event(kind, (float(x), float(y))))
        return
    if not IS_WINDOWS:
        return
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    nx = int((x - vx) * 65535 / max(vw - 1, 1))
    ny = int((y - vy) * 65535 / max(vh - 1, 1))
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    _send(_mouse(flags, nx, ny))
    # Roblox обновляет позицию курсора только после относительного движения
    time.sleep(micro_delay)
    _send(_mouse(MOUSEEVENTF_MOVE, 1, 0))
    _send(_mouse(MOUSEEVENTF_MOVE, -1, 0))


def mouse_down():
    global _held
    if IS_WINDOWS:
        _send(_mouse(MOUSEEVENTF_LEFTDOWN))
    elif IS_MAC and Quartz is not None:
        _held = True
        _post(_mouse_event(Quartz.kCGEventLeftMouseDown, _cursor()))


def mouse_up():
    global _held
    if IS_WINDOWS:
        _send(_mouse(MOUSEEVENTF_LEFTUP))
    elif IS_MAC and Quartz is not None:
        _held = False
        _post(_mouse_event(Quartz.kCGEventLeftMouseUp, _cursor()))


def click(x=None, y=None, hold=0.05):
    if x is not None and y is not None:
        move_to(x, y)
        time.sleep(micro_delay)
    mouse_down()
    time.sleep(hold)
    mouse_up()


def press_key(name, hold=0.05):
    if IS_MAC:
        code = MAC_KEYS.get(str(name).lower())
        if code is None:
            raise ValueError(tr("Неизвестная клавиша: {name}", name=name))
        if Quartz is not None:
            _post(Quartz.CGEventCreateKeyboardEvent(None, code, True))
            time.sleep(hold)
            _post(Quartz.CGEventCreateKeyboardEvent(None, code, False))
        return
    if not IS_WINDOWS:
        return
    vk = VK.get(str(name).lower())
    if vk is None:
        raise ValueError(tr("Неизвестная клавиша: {name}", name=name))
    _send(_key(vk))
    time.sleep(hold)
    _send(_key(vk, up=True))


def type_text(text):
    for ch in str(text):
        press_key(ch)
        time.sleep(0.03)


def accessibility_ok(prompt=False):
    """macOS: разрешён ли программе «Универсальный доступ» (без него клики и клавиши не доходят).
    prompt=True — система сама покажет окно с кнопкой «Открыть Системные настройки»."""
    if not IS_MAC or Quartz is None:
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: bool(prompt)}))
    except Exception:
        return True


def screen_capture_ok(prompt=False):
    """macOS: разрешена ли «Запись экрана» (без неё снимки — только обои рабочего стола, без окон)."""
    if not IS_MAC or Quartz is None:
        return True
    try:
        if Quartz.CGPreflightScreenCaptureAccess():
            return True
        if prompt:
            Quartz.CGRequestScreenCaptureAccess()
        return False
    except Exception:
        return True


def foreground_title():
    """Заголовок активного окна; на macOS — имя активного приложения ('' на прочих системах)."""
    if IS_MAC:
        if Quartz is None:
            return ""
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        name = str(app.localizedName() or "") if app else ""
        return ROBLOX if name == "RobloxPlayer" else name
    if not IS_WINDOWS:
        return ""
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def _mac_roblox_window():
    """Самое большое обычное окно приложения Roblox: (x, y, w, h) в пунктах или None."""
    if Quartz is None:
        return None
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    best = None
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
        if w.get("kCGWindowOwnerName") not in (ROBLOX, "RobloxPlayer") or w.get("kCGWindowLayer", 0) != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        rect = (int(b.get("X", 0)), int(b.get("Y", 0)), int(b.get("Width", 0)), int(b.get("Height", 0)))
        if best is None or rect[2] * rect[3] > best[2] * best[3]:
            best = rect
    return best


def roblox_rect():
    """(x, y, w, h) окна Roblox на экране или None."""
    if IS_MAC:
        return _mac_roblox_window()
    if not IS_WINDOWS:
        return None
    hwnd = user32.FindWindowW(None, "Roblox")
    if not hwnd:
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def roblox_window_exists():
    if IS_MAC:
        return Quartz is None or _roblox_app() is not None
    if not IS_WINDOWS:
        return True
    return bool(user32.FindWindowW(None, "Roblox"))


def focus_roblox():
    """Выводит окно Roblox на передний план. True, если окно найдено."""
    if IS_MAC:
        if Quartz is None:
            return True
        app = _roblox_app()
        if app is None:
            return False
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        return True
    if not IS_WINDOWS:
        return True
    hwnd = user32.FindWindowW(None, "Roblox")
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # Windows не даёт фоновому процессу забрать фокус, пока не было ввода — нажимаем Alt
    _send(_key(VK["alt"]))
    _send(_key(VK["alt"], up=True))
    user32.SetForegroundWindow(hwnd)
    return True
