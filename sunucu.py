"""Piksel Stüdyo: local web app. Runs on 127.0.0.1 only and opens in an Edge app window.
Started by Uygulamayi_Ac.bat; quits by itself shortly after the window is closed.

Images come from the Gemini chat site (Gemini Plus). The clipboard autopilot watches the clipboard:
when an image is copied it is saved under the current topic(s) and the next prompt is put on the
clipboard, so the user never has to switch windows.
"""
import collections
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

from PIL import Image  # noqa: E402

import kitap_yap  # noqa: E402
import konu_uret  # noqa: E402
import pano  # noqa: E402
import pixelbook as pb  # noqa: E402
import promptlar  # noqa: E402

INPUT, OUTPUT, TRASH = BASE / "girdi", BASE / "cikti", BASE / "silinenler"
TOPICS, SETTINGS, PAGE, ERRLOG = BASE / "konular.csv", BASE / "ayarlar.json", BASE / "arayuz.html", BASE / "hata.log"
TOKEN = secrets.token_urlsafe(16)  # blocks other web pages from driving this local server
MAX_UPLOAD = 50 * 1024 * 1024
SHEET_INSET = 0.03  # trim 3% of each panel edge so the dividing lines never end up in a picture
SETTING_KEYS = {"title": "Pixel Color by Number", "shape": "square", "sort": True, "per_prompt": 4}

lock = threading.Lock()
save_lock = threading.Lock()  # clipboard watcher and uploads must not save to the same topic at once
topics_lock = threading.Lock()  # konular.csv is rewritten when topics are added or refreshed
logs = collections.deque(maxlen=400)
log_seq = 0
last_seen = time.time()
bye_at = 0.0
cache = {}
task = {"kind": None, "running": False}
autopilot = {"on": False, "cursor": 0, "last_saved": [], "own_seq": None, "saves": 0}


def load_settings():
    try:
        saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    # only known keys: old API keys/options from earlier versions are dropped on the next save
    return {k: saved.get(k, default) for k, default in SETTING_KEYS.items()}


settings = load_settings()


def save_settings():
    SETTINGS.write_text(json.dumps(settings, ensure_ascii=False, indent=1), encoding="utf-8")


def log(msg):
    global log_seq
    with lock:
        log_seq += 1
        logs.append({"id": log_seq, "t": time.strftime("%H:%M:%S"), "msg": msg})


def errlog(text):
    try:
        with open(ERRLOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except OSError:
        pass


def list_images():
    files = sorted(p for p in INPUT.iterdir() if p.suffix.lower() in kitap_yap.IMAGE_EXT)
    return [{"name": p.name, "title": kitap_yap.title_from(p), "v": int(p.stat().st_mtime)} for p in files]


# ---------- topics & autopilot ----------
def all_topics():
    """Active topics (retired ones left out)."""
    return [t for t in promptlar.load_topics(TOPICS) if t[2] != promptlar.RETIRED]


def retire_topic(file_name):
    """The user deleted this topic's image: don't ask for it again. Returns True if it was a topic."""
    with topics_lock:
        rows = konu_uret.read_rows(TOPICS)
        hit = [r for r in rows if promptlar.file_name(r["no"], r["subject"]) == file_name]
        for r in hit:
            r["category"] = promptlar.RETIRED
        if hit:
            konu_uret.write_rows(TOPICS, rows)
    return bool(hit)


def remove_custom_topic(file_name):
    """Take a typed-in topic that has no image yet out of the queue."""
    with topics_lock:
        rows = konu_uret.read_rows(TOPICS)
        keep = [r for r in rows if not (promptlar.file_name(r["no"], r["subject"]) == file_name
                                        and r["category"].startswith(promptlar.CUSTOM) and not topic_done(r))]
        if len(keep) == len(rows):
            raise ValueError("Bu özel konu sırada bulunamadı.")
        konu_uret.write_rows(TOPICS, keep)
    autopilot["cursor"] = 0
    log(f"Özel konu sıradan kaldırıldı: {kitap_yap.title_from(Path(file_name))}")
    if autopilot["on"]:
        copy_prompt()


def is_custom(topic):
    return topic[2].startswith(promptlar.CUSTOM)


def pending_topics():
    """Topics still without an image, as (file_name, subject, category); topics typed into the app come first."""
    pend = [t for t in all_topics() if not (INPUT / t[0]).exists()]
    return sorted(pend, key=lambda t: not is_custom(t))  # stable: list order otherwise


def topic_done(row):
    return (INPUT / promptlar.file_name(row["no"], row["subject"])).exists()


def add_custom_topic(subject, kids):
    """A topic typed into the app (e.g. a child's wish): next in line, always as its own full image."""
    subject = " ".join(str(subject).split())
    if not 2 <= len(subject) <= 120 or not promptlar.slug(subject):
        raise ValueError("Konuyu 2–120 karakterle yaz, en az bir harf olsun.")
    with topics_lock:
        rows = konu_uret.read_rows(TOPICS)
        key = promptlar.slug(subject)  # compares "BİR zürafa" and "bir zurafa" as the same topic
        if any(promptlar.slug(r["subject"]) == key and not topic_done(r) and r["category"] != promptlar.RETIRED
               for r in rows):
            raise ValueError("Bu konu zaten sırada.")
        nxt = max((int(r["no"]) for r in rows), default=0) + 1
        rows.append({"no": nxt, "subject": subject, "category": promptlar.CUSTOM_KIDS if kids else promptlar.CUSTOM})
        konu_uret.write_rows(TOPICS, rows)
    autopilot["cursor"] = 0
    log(f"Özel konu sıraya alındı ({'çocuk' if kids else 'yetişkin'} stili): {subject}")
    # with the autopilot on, the prompt already on the clipboard stays valid; the custom topic comes next round


def ensure_topics():
    """Never run out: when fewer than 8 topics wait, add 40 fresh generated ones."""
    with topics_lock:
        if len(pending_topics()) < 8:
            added = konu_uret.add_topics(TOPICS, 40)
            log(f"Konu listesine {added} yeni konu eklendi.")


def refresh_topics():
    """Swap every waiting generated topic for new ones (topics with images and hand-written rows stay)."""
    with topics_lock:
        added = konu_uret.refresh_pending(TOPICS, topic_done, 60)
    autopilot["cursor"] = 0
    log(f"Bekleyen konular yenilendi: {added} yeni konu.")
    if autopilot["on"]:
        copy_prompt()


def current_target():
    """The topic(s) the next copied image belongs to: 4 in sheet mode (when 4 are left from here), else 1."""
    ensure_topics()
    pend = pending_topics()
    if not pend:
        return []
    cur = autopilot["cursor"] % len(pend)
    sheet = settings["per_prompt"] == 4 and len(pend) - cur >= 4 and not is_custom(pend[cur])
    return pend[cur:cur + (4 if sheet else 1)]


def locked_target():
    """With the autopilot on: the topic(s) whose prompt is on the clipboard, so an image Gemini is still
    drawing lands there even if the queue changed meanwhile (e.g. a custom topic was added)."""
    lock_ = autopilot.get("locked") or []
    if autopilot["on"] and lock_ and all(not (INPUT / t[0]).exists() for t in lock_):
        return lock_
    return None


def current_prompt(target=None):
    target = current_target() if target is None else target
    if not target:
        return None
    if len(target) == 4:
        return promptlar.sheet_prompt([t[1] for t in target])
    return promptlar.single_prompt(target[0][1], kids=target[0][2] == promptlar.CUSTOM_KIDS)


def label(target):
    nums = [t[0].split("_", 1)[0] for t in target]
    return nums[0] if len(nums) == 1 else f"{nums[0]}–{nums[-1]}"


def copy_prompt():
    target = current_target()
    if not target:
        autopilot["locked"] = None
        log("Bütün konuların görseli hazır.")
        return False
    pano.set_text(current_prompt(target))
    autopilot["own_seq"] = pano.sequence()
    autopilot["locked"] = target
    log(f"Prompt panoya kopyalandı: {label(target)}")
    return True


def split_sheet(img):
    w, h = img.size
    tiles = []
    for row in range(2):
        for col in range(2):
            x0, y0, x1, y1 = col * w / 2, row * h / 2, (col + 1) * w / 2, (row + 1) * h / 2
            dx, dy = (x1 - x0) * SHEET_INSET, (y1 - y0) * SHEET_INSET
            tiles.append(img.crop((round(x0 + dx), round(y0 + dy), round(x1 - dx), round(y1 - dy))))
    return tiles  # top-left, top-right, bottom-left, bottom-right


def save_to_current(img, source):
    """Save an image under the current topic(s); a 4-topic target is cut as a 2x2 sheet."""
    with save_lock:
        target = locked_target() or current_target()
        if not target:
            raise ValueError("Bekleyen konu yok. Konu listesine yeni konu ekle ya da görseli 'Kendi görselin'e bırak.")
        img = img.convert("RGB")
        pieces = split_sheet(img) if len(target) == 4 else [img]
        INPUT.mkdir(exist_ok=True)
        names = [t[0] for t in target]
        for name, piece in zip(names, pieces):
            tmp = INPUT / (name + ".part")  # write fully, then rename: the gallery never reads a half file
            piece.save(tmp, "PNG")
            tmp.replace(INPUT / name)
        autopilot["last_saved"] = names
        autopilot["saves"] += 1
        log(f"Kaydedildi ({source}): {label(target)} · " + ", ".join(kitap_yap.title_from(Path(n)) for n in names))
    if autopilot["on"]:
        copy_prompt()
    return names


def undo_last():
    names = autopilot["last_saved"]
    if not names:
        raise ValueError("Geri alınacak kayıt yok.")
    TRASH.mkdir(exist_ok=True)
    for n in names:
        if (INPUT / n).exists():
            shutil.move(str(INPUT / n), TRASH / f"{int(time.time())}_{n}")
    pend = [t[0] for t in pending_topics()]
    autopilot["cursor"] = pend.index(names[0]) if names[0] in pend else 0
    autopilot["last_saved"] = []
    log(f"Geri alındı: {', '.join(n.split('_', 1)[0] for n in names)} (silinenler klasöründe)")
    if autopilot["on"]:
        copy_prompt()


def clipboard_watcher():
    last = pano.sequence()
    while True:
        time.sleep(0.4)
        try:
            seq = pano.sequence()
            if seq == last:
                continue
            if not autopilot["on"] or seq == autopilot["own_seq"]:
                last = seq
                continue
            img = pano.get_image()
            if img is None:
                # text, or the copying app has not finished writing the image yet: look again once
                time.sleep(0.3)
                img = pano.get_image()
            last = pano.sequence()
            if img is not None:
                w, h = img.size
                # Gemini gives portrait/square images of ~1000px; screenshots (Win+Shift+S also lands on the
                # clipboard) are usually wide or small, and must not be saved as a topic
                if min(w, h) < 500 or not 0.55 <= w / h <= 1.1:
                    log(f"Panodaki {w}×{h} görsel Gemini görseline benzemiyor (ekran görüntüsü?), kaydedilmedi. "
                        "Yine de kullanmak için uygulamaya sürükle.")
                    continue
                save_to_current(img, "pano")
        except ValueError as e:
            log(str(e))
            autopilot["on"] = False
        except Exception:  # noqa: BLE001 - the watcher must keep running
            errlog(traceback.format_exc())
            log("Pano okunamadı, tekrar dene (ayrıntı: hata.log).")


def manual_view():
    target = locked_target() or current_target()
    total = len(all_topics())
    pend = pending_topics()
    queued = [t for t in pend if is_custom(t) and t not in target]
    return {"on": autopilot["on"], "per_prompt": settings["per_prompt"], "total": total, "done": total - len(pend),
            "pending": len(pend), "label": label(target) if target else None, "saves": autopilot["saves"],
            "target": [{"num": t[0].split("_", 1)[0], "title": kitap_yap.title_from(Path(t[0])), "name": t[0],
                        "custom": is_custom(t), "kids": t[2] == promptlar.CUSTOM_KIDS} for t in target],
            "queued_custom": [{"name": t[0], "subject": t[1], "kids": t[2] == promptlar.CUSTOM_KIDS} for t in queued],
            "can_undo": bool(autopilot["last_saved"])}


def manual_action(action):
    if action in ("start", "copy"):
        if not copy_prompt():
            raise ValueError("Bekleyen konu yok.")
        if action == "start":
            autopilot["on"] = True
            log("Otopilot açık: Gemini'de Ctrl+V → Enter → görsele sağ tık → Görseli kopyala.")
    elif action == "stop":
        autopilot["on"] = False
        log("Otopilot kapatıldı.")
    elif action in ("next", "prev"):
        pend = len(pending_topics())
        if pend:
            step = len(current_target()) if action == "next" else -(4 if settings["per_prompt"] == 4 else 1)
            autopilot["cursor"] = (autopilot["cursor"] % pend + step) % pend
        if autopilot["on"]:
            copy_prompt()
    elif action == "undo":
        undo_last()
    elif action == "refresh":
        refresh_topics()
    else:
        raise ValueError("Bilinmeyen işlem")


# ---------- book ----------
def progress_view():
    t = dict(task)
    if t.get("kind") and t.get("total"):
        now = time.time()
        t["pct"] = round(100 * t["done"] / t["total"], 1)
        per = (now - t["started"]) / t["done"] if t["done"] else None
        t["eta"] = round(per * (t["total"] - t["done"])) if per and t["running"] else None
    return t


def start_build():
    if not list_images():
        raise ValueError("Klasörde görsel yok. Önce Gemini'den görsel al ya da kendi görselini ekle.")
    task.clear()
    task.update(kind="build", running=True, done=0, total=1, started=time.time(), error=None, result=None)
    log("— Kitap oluşturuluyor —")
    summary = {}

    def on_log(msg):
        if msg.startswith("Bitti:"):
            summary["text"] = msg
        log(msg)

    def work():
        try:
            pdf, _ = kitap_yap.build_book(
                INPUT, OUTPUT, settings["title"] or "Pixel Color by Number", shape=settings["shape"],
                hex_offset=settings["shape"] == "circle", sort=settings["sort"], log=on_log,
                progress=lambda d, t: task.update(done=d, total=t))
            task.update(done=task["total"], result={"summary": summary.get("text", ""), "pdf": pdf.name})
        except PermissionError:
            task["error"] = "PDF şu an açık olduğu için üzerine yazılamadı. PDF'i kapatıp tekrar dene."
        except ValueError as e:
            task["error"] = str(e)
        except Exception as e:  # noqa: BLE001
            task["error"] = f"Beklenmeyen hata: {e}"
            errlog(traceback.format_exc())
        finally:
            task["running"] = False
    threading.Thread(target=work, daemon=True).start()


def thumb(path, pixel):
    key = (path.name, path.stat().st_mtime, pixel)
    if key not in cache:
        buf = io.BytesIO()
        if pixel:  # what the colouring page will look like
            grid, _ = pb.convert(path, 40, 54, 15)
            kitap_yap.grid_image(grid, px=8).save(buf, "PNG")
            cache[key] = ("image/png", buf.getvalue())
        else:
            img = Image.open(path).convert("RGB")
            img.thumbnail((420, 560))
            img.save(buf, "JPEG", quality=85)
            cache[key] = ("image/jpeg", buf.getvalue())
    return cache[key]


def safe_input_file(name):
    """Only plain file names that exist in girdi/ (no paths, no traversal)."""
    if not name or Path(name).name != name:
        raise ValueError("Geçersiz dosya adı")
    path = INPUT / name
    if not path.is_file():
        raise ValueError("Dosya bulunamadı")
    return path


def read_image(name, data):
    if Path(name).suffix.lower() not in kitap_yap.IMAGE_EXT:
        raise ValueError(f"{name}: desteklenmeyen dosya türü (png, jpg, webp)")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:  # noqa: BLE001
        raise ValueError(f"{name}: geçerli bir görsel değil") from None


def save_own_photo(name, data):
    read_image(name, data)
    INPUT.mkdir(exist_ok=True)
    # own photos are numbered k001, k002...: plain numbers belong to the (ever-growing) topic list
    nums = [int(p.name[1:].split("_", 1)[0]) for p in INPUT.iterdir()
            if p.name[:1] == "k" and p.name[1:].split("_", 1)[0].isdigit()]
    nxt = max(nums, default=0) + 1
    ext = Path(name).suffix.lower()
    stem = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in Path(name).stem).strip() or "gorsel"
    dest = INPUT / f"k{nxt:03d}_{stem}{ext}"
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    log(f"Eklendi: {dest.name}")
    return dest.name


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self, query):
        return secrets.compare_digest(self.headers.get("X-Token", "") or query.get("t", [""])[0], TOKEN)

    def do_GET(self):
        global last_seen
        last_seen = time.time()
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self._authed(q):
            return self._send(403, {"error": "forbidden"})
        try:
            if url.path == "/":
                return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/state":
                since = int(q.get("since", ["0"])[0])
                with lock:
                    new_logs = [entry for entry in logs if entry["id"] > since]
                out_pdf, out_rep = OUTPUT / "kitap_ic_sayfalar.pdf", OUTPUT / "rapor.html"
                return self._send(200, {
                    "settings": settings, "manual": manual_view(), "task": progress_view(),
                    "images": list_images(), "logs": new_logs,
                    "outputs": {"pdf": out_pdf.exists(), "report": out_rep.exists(),
                                "pdf_time": time.strftime("%d.%m %H:%M", time.localtime(out_pdf.stat().st_mtime))
                                if out_pdf.exists() else None}})
            if url.path.startswith(("/thumb/", "/pixel/")):
                ctype, data = thumb(safe_input_file(unquote(url.path.split("/", 2)[2])), url.path.startswith("/pixel/"))
                return self._send(200, data, ctype)
            self._send(404, {"error": "not found"})
        except (ValueError, OSError) as e:  # e.g. a file deleted or replaced while the gallery loads it
            self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            errlog(traceback.format_exc())
            self._send(500, {"error": f"Beklenmeyen hata: {e}"})

    def do_POST(self):
        global last_seen, bye_at
        last_seen = time.time()
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self._authed(q):
            return self._send(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            return self._send(413, {"error": "Dosya çok büyük (en fazla 50 MB)."})
        raw = self.rfile.read(length) if length else b""
        try:
            if url.path == "/api/bye":
                bye_at = time.time()
                return self._send(200, {})
            if url.path == "/api/upload":
                name = unquote(q.get("name", ["gorsel.png"])[0])
                if q.get("topic", [""])[0] == "current":  # Gemini image dropped/pasted into the app
                    return self._send(200, {"ok": True, "names": save_to_current(read_image(name, raw), "yükleme")})
                return self._send(200, {"ok": True, "name": save_own_photo(name, raw)})
            body = json.loads(raw or b"{}")
            if url.path == "/api/settings":
                for k in SETTING_KEYS:
                    if k in body:
                        settings[k] = body[k]
                if "per_prompt" in body and autopilot["on"]:
                    copy_prompt()  # the prompt on the clipboard must match the new mode
                save_settings()
                return self._send(200, {"ok": True})
            if url.path == "/api/manual":
                manual_action(body.get("action"))
                return self._send(200, {"ok": True})
            if url.path == "/api/custom":
                add_custom_topic(body.get("subject", ""), bool(body.get("kids")))
                return self._send(200, {"ok": True, "now": not autopilot["on"]})
            if url.path == "/api/build":
                if task.get("running"):
                    raise ValueError("Kitap zaten oluşturuluyor.")
                start_build()
                return self._send(200, {"ok": True})
            if url.path == "/api/delete":
                path = safe_input_file(body.get("name", ""))
                TRASH.mkdir(exist_ok=True)
                shutil.move(str(path), TRASH / f"{int(time.time())}_{path.name}")
                retired = retire_topic(path.name)
                log(f"Silinenler klasörüne taşındı: {path.name}" + (" · konu iptal edildi, tekrar istenmeyecek" if retired else ""))
                return self._send(200, {"ok": True, "retired": retired})
            if url.path == "/api/custom/remove":
                remove_custom_topic(body.get("name", ""))
                return self._send(200, {"ok": True})
            if url.path == "/api/open":
                what = body.get("what")
                if what == "gemini":
                    webbrowser.open("https://gemini.google.com/app")
                    return self._send(200, {"ok": True})
                target = {"pdf": OUTPUT / "kitap_ic_sayfalar.pdf", "report": OUTPUT / "rapor.html",
                          "input": INPUT, "topics": TOPICS, "output": OUTPUT}.get(what)
                if not target or not target.exists():
                    raise ValueError("Henüz oluşturulmadı.")
                os.startfile(target)
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})
        except (ValueError, OSError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            errlog(traceback.format_exc())
            self._send(500, {"error": f"Beklenmeyen hata: {e}"})


def watchdog():
    """Quit once the window is gone: a 'bye' with no reconnect (a reload reconnects), or long silence."""
    while True:
        time.sleep(1)
        if task.get("running"):
            continue
        now = time.time()
        if (bye_at and now - bye_at > 5 and last_seen <= bye_at + 0.5) or now - last_seen > 180:
            os._exit(0)


def open_window(url):
    for exe in (shutil.which("msedge"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
        if exe and Path(exe).exists():
            subprocess.Popen([exe, f"--app={url}", "--window-size=1360,900"])
            return
    webbrowser.open(url)


def main():
    INPUT.mkdir(exist_ok=True)
    if not TOPICS.exists():  # fresh install: start an empty list, ensure_topics() fills it on first use
        konu_uret.write_rows(TOPICS, [])
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/?t={TOKEN}"
    log("Stüdyo hazır.")
    for target in (clipboard_watcher, watchdog):
        threading.Thread(target=target, daemon=True).start()
    if "--no-window" not in sys.argv:
        open_window(url)
    else:
        print(url, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        errlog(traceback.format_exc())
        raise
