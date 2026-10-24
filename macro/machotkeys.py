"""Глобальные горячие клавиши в macOS — через мониторы событий NSEvent, без pynput.

pynput читает раскладку клавиатуры (TSMGetInputSourceProperty) из своего фонового потока, а macOS
разрешает это только главному потоку — программа падала сразу при запуске (EXC_BREAKPOINT в
dispatch_assert_queue). Мониторы NSEvent вызываются в главном потоке, из цикла событий окна Tk.
Глобальный монитор видит нажатия в других приложениях (в Roblox) — для этого нужен «Универсальный
доступ»; локальный — нажатия, когда активно окно FishPilot.
"""
import logging
import os

from . import winput

log = logging.getLogger("fishpilot")


class MacHotkeys:
    def __init__(self, on_key):
        import Quartz
        from AppKit import NSEvent, NSEventMaskKeyDown
        names = {code: name for name, code in winput.MAC_KEYS.items()}
        pid = os.getpid()

        def name_of(event):
            if event.isARepeat():
                return None
            try:
                # Нажатия, которые послал сам макрос (CGEventPost), — не горячие клавиши
                cg = event.CGEvent()
                if cg is not None and Quartz.CGEventGetIntegerValueField(
                        cg, Quartz.kCGEventSourceUnixProcessID) == pid:
                    return None
            except Exception:
                pass
            return names.get(int(event.keyCode()))

        def on_global(event):
            name = name_of(event)
            if name:
                on_key(name)

        def on_local(event):
            on_global(event)
            return event                  # событие идёт дальше, в окно Tk

        log.info("macOS hotkeys: NSEvent monitors")
        self._monitors = [
            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_global),
            NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_local),
        ]

    def stop(self):
        from AppKit import NSEvent
        for monitor in self._monitors:
            if monitor is not None:
                NSEvent.removeMonitor_(monitor)
        log.info("macOS hotkeys: NSEvent monitors")
        self._monitors = []
