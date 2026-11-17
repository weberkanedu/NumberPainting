"""Windows clipboard helpers for the autopilot (ctypes + Pillow, no extra installs)."""
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002

_u32, _k32 = ctypes.windll.user32, ctypes.windll.kernel32
_u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
_u32.OpenClipboard.argtypes = [wintypes.HWND]
_u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_u32.SetClipboardData.restype = wintypes.HANDLE
_k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_k32.GlobalAlloc.restype = wintypes.HGLOBAL
_k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_k32.GlobalLock.restype = wintypes.LPVOID
_k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_k32.GlobalFree.argtypes = [wintypes.HGLOBAL]


def sequence():
    """Changes every time anything is copied; cheap to poll."""
    return _u32.GetClipboardSequenceNumber()


def set_text(text):
    data = text.encode("utf-16-le") + b"\0\0"
    for _ in range(20):  # another app may hold the clipboard for a moment
        if _u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise OSError("Pano başka bir uygulama tarafından kullanılıyor")
    try:
        _u32.EmptyClipboard()
        handle = _k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ctypes.memmove(_k32.GlobalLock(handle), data, len(data))
        _k32.GlobalUnlock(handle)
        if not _u32.SetClipboardData(CF_UNICODETEXT, handle):
            _k32.GlobalFree(handle)  # ownership only passes to the clipboard on success
            raise OSError("Panoya yazılamadı")
    finally:
        _u32.CloseClipboard()


def get_image():
    """The image on the clipboard: a copied picture, or a copied image file. None otherwise."""
    try:
        content = ImageGrab.grabclipboard()
    except OSError:
        return None  # clipboard busy; the caller polls again
    if isinstance(content, Image.Image):
        return content
    if isinstance(content, list):
        for p in content:
            if Path(p).suffix.lower() in IMAGE_EXT:
                try:
                    img = Image.open(p)
                    img.load()
                    return img
                except OSError:
                    continue
    return None
