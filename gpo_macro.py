"""Точка входа: python gpo_macro.py"""
import sys
import time

from macro import winput

if "--selftest" in sys.argv:
    # Проверка собранного exe в CI: работает ли внутри него Windows OCR
    from macro.selftest import run
    sys.exit(run())


def single_instance():
    """Только одна копия: две ловили бы одновременно (одно F1 — два старта, все клики двойные).
    После обновления новый exe запускается с --wait-instance и ждёт, пока закроется старый."""
    if winput.IS_MAC:
        return _single_instance_lock()
    if not winput.IS_WINDOWS:
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    deadline = time.monotonic() + (20 if "--wait-instance" in sys.argv else 0)
    while True:
        handle = kernel32.CreateMutexW(None, False, "Local\\FishPilot.single-instance")
        if kernel32.GetLastError() != 183:          # ERROR_ALREADY_EXISTS
            single_instance.handle = handle          # держим до выхода из программы
            return True
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def _single_instance_lock():
    """macOS: замок-файл (fcntl) в папке настроек — система снимает его сама, даже если программа упала."""
    import fcntl
    import os
    from macro import config
    deadline = time.monotonic() + (20 if "--wait-instance" in sys.argv else 0)
    f = open(os.path.join(config.data_dir(), "instance.lock"), "w")
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _single_instance_lock.file = f            # держим до выхода из программы
            return True
        except OSError:
            if time.monotonic() >= deadline:
                f.close()
                return False
            time.sleep(0.5)


if not single_instance():
    from macro import config, i18n
    try:
        i18n.set_language(config.load().get("language"))
    except Exception:
        pass
    if winput.IS_WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, i18n.tr("FishPilot уже запущен — посмотрите на панели задач."),
                                         "FishPilot", 0x40)
    else:
        import tkinter
        from tkinter import messagebox
        tkinter.Tk().withdraw()
        messagebox.showinfo("FishPilot", i18n.tr("FishPilot уже запущен — посмотрите в Dock."))
    sys.exit(0)

winput.set_dpi_aware()  # до создания окна, иначе координаты поедут при масштабе > 100%

from macro.gui import App  # noqa: E402

if __name__ == "__main__":
    App().run()
