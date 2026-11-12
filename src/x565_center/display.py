"""Частота и яркость встроенного экрана (WinAPI через ctypes)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG),
        ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


ENUM_CURRENT_SETTINGS = -1
DM_DISPLAYFREQUENCY = 0x400000
CDS_TEST = 0x2
DISP_CHANGE_SUCCESSFUL = 0

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.EnumDisplaySettingsW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DEVMODE)]
_user32.ChangeDisplaySettingsExW.argtypes = [
    wintypes.LPCWSTR, ctypes.POINTER(DEVMODE), wintypes.HWND, wintypes.DWORD, ctypes.c_void_p,
]
_user32.ChangeDisplaySettingsExW.restype = wintypes.LONG


def _current() -> DEVMODE | None:
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    if _user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS & 0xFFFFFFFF, ctypes.byref(dm)):
        return dm
    return None


def current_mode() -> tuple[int, int, int] | None:
    """(ширина, высота, Гц) основного экрана."""
    dm = _current()
    return (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency) if dm else None


def current_hz() -> int | None:
    mode = current_mode()
    return mode[2] if mode else None


def available_hz() -> list[int]:
    """Частоты, доступные при текущем разрешении."""
    cur = _current()
    if cur is None:
        return []
    rates = set()
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    i = 0
    while _user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        if (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmBitsPerPel) == (
            cur.dmPelsWidth, cur.dmPelsHeight, cur.dmBitsPerPel,
        ):
            rates.add(dm.dmDisplayFrequency)
        i += 1
    return sorted(rates)


def set_hz(hz: int) -> bool:
    """Меняет только частоту. Изменение временное: в реестр не пишется и после перезагрузки сбрасывается."""
    dm = _current()
    if dm is None:
        return False
    if dm.dmDisplayFrequency == hz:
        return True
    dm.dmDisplayFrequency = hz
    dm.dmFields = DM_DISPLAYFREQUENCY
    if _user32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, CDS_TEST, None) != DISP_CHANGE_SUCCESSFUL:
        return False
    return _user32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, 0, None) == DISP_CHANGE_SUCCESSFUL


# --- Яркость: стандартный интерфейс Windows \\.\LCD (не методы производителя) ---

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS = 0x230498
IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS = 0x23049C
INVALID_HANDLE = wintypes.HANDLE(-1).value


def _lcd_ioctl(code: int, data: bytes | None) -> bytes | None:
    handle = _kernel32.CreateFileW(r"\\.\LCD", 0xC0000000, 3, None, 3, 0, None)
    if handle in (None, INVALID_HANDLE):
        return None
    try:
        out = (ctypes.c_ubyte * 3)()
        returned = wintypes.DWORD()
        if data is None:
            ok = _kernel32.DeviceIoControl(handle, code, None, 0, out, 3, ctypes.byref(returned), None)
        else:
            buf = (ctypes.c_ubyte * 3)(*data)
            ok = _kernel32.DeviceIoControl(handle, code, buf, 3, None, 0, ctypes.byref(returned), None)
        return bytes(out) if ok else None
    finally:
        _kernel32.CloseHandle(handle)


def get_brightness(on_ac: bool = True) -> int | None:
    """Яркость 0–100 или None, если экран её не отдаёт."""
    res = _lcd_ioctl(IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS, None)
    if res is None:
        return None
    return res[1] if on_ac else res[2]


def set_brightness(value: int) -> bool:
    value = max(0, min(100, int(value)))
    # policy 3 = и от сети, и от батареи
    return _lcd_ioctl(IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS, bytes((3, value, value))) is not None
