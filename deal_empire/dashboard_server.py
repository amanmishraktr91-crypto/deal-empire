"""
JARVIS COMMAND CENTER — Live 21-Bot Dashboard + AI Chat + Auto-Healing (Production Hardened)
"""
import os
import sys
import json
import time
import threading
import queue
import logging
import random
import re
import html
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, Response, session
from dotenv import load_dotenv

# Ensure line buffering for cloud streaming logs
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aman_jarvis_secret_key_8899")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "aman_empire_secret_9988").strip()
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "aman123").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "6208434509"))
CHAT_ID = os.getenv("CHAT_ID", "6208434509").strip()
MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT", "60"))
MIN_MRP = int(os.getenv("MIN_MRP", "400"))

# Import scraping dependencies
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

# ============================================================
# Gemini client (lazy)
# ============================================================
_gemini = None
def get_gemini():
    global _gemini
    if _gemini is None and GEMINI_API_KEY:
        try:
            from google import genai
            _gemini = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Gemini init fail: {e}")
    return _gemini

# ============================================================
# Live Store (thread-safe)
# ============================================================
HEARTBEAT_TIMEOUT = 60   # 60 sec tak heartbeat na aaye = dead
AUTO_HEAL_CHECK   = 15   # Har 15 sec check karo

class LiveStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs = []
        self.data = {
            "total_scans": 0,
            "loots_found": 0,
            "uptime_start": time.time(),
            "bot_status": {},
            "recent_loots": [],
            "security_pending": [],
            "security_logs": [],
            "heal_logs": [],
            "doctor": {
                "healthy_bots": 21,
                "total_monitored_bots": 21,
                "healing_actions_total": 0,
                "last_check": datetime.now().isoformat(),
            }
        }
        self._init_bots()
        self._start_healer()

    def _init_bots(self):
        stores = ["Amazon"] * 11 + ["Flipkart"] * 10
        for i in range(21):
            name = f"HUNTER-{i+1:02d}"
            self.data["bot_status"][name] = {
                "store": stores[i],
                "scans": 0,
                "loots": 0,
                "status": "idle",       # idle | active | healing | error | dead | blocked
                "last_beat": time.time(),
                "heal_count": 0,
            }

    # -------- Auto-healer thread (PATCH 4: ignores blocked bots during cooldown) --------
    def _start_healer(self):
        t = threading.Thread(target=self._healer_loop, daemon=True)
        t.start()

    def _healer_loop(self):
        while True:
            time.sleep(AUTO_HEAL_CHECK)
            try:
                now = time.time()
                healed = 0
                healthy = 0
                to_revive = []
                with self._lock:
                    for name, b in self.data["bot_status"].items():
                        st = b.get("status")
                        # blocked ya healing ko chhedna nahi (cooldown me hain)
                        if st in ("healing", "blocked"):
                            healthy += 1
                            continue
                        gap = now - b.get("last_beat", now)
                        if gap > HEARTBEAT_TIMEOUT:
                            b["status"] = "healing"
                            b["heal_count"] = b.get("heal_count", 0) + 1
                            b["last_beat"] = now
                            self._log_heal_internal(name, f"No heartbeat {int(gap)}s -> restart")
                            to_revive.append(name)
                            healed += 1
                        else:
                            healthy += 1
                    self.data["doctor"]["healthy_bots"] = healthy
                    self.data["doctor"]["total_monitored_bots"] = len(self.data["bot_status"])
                    self.data["doctor"]["healing_actions_total"] += healed
                    self.data["doctor"]["last_check"] = datetime.now().isoformat()
                for name in to_revive:
                    start_bot_worker(name)
                if healed:
                    logger.info(f"[AutoHealer] Revived {healed} bots cleanly via registry")
                    self._broadcast()
            except Exception as e:
                logger.error(f"Healer error: {e}")

    def _log_heal_internal(self, bot, reason):
        self.data["heal_logs"].insert(0, {
            "bot": bot, "reason": reason,
            "time": datetime.now().isoformat()
        })
        self.data["heal_logs"] = self.data["heal_logs"][:20]

    def _restart_bot_worker(self, bot_name):
        try:
            start_bot_worker(bot_name)
        except Exception as e:
            logger.error(f"Failed to restart {bot_name}: {e}")

    # -------- Public methods --------
    def update_bot(self, name, **kw):
        with self._lock:
            if name in self.data["bot_status"]:
                self.data["bot_status"][name].update(kw)
                self.data["bot_status"][name]["last_beat"] = time.time()
                self._broadcast()

    def inc(self, key, n=1):
        with self._lock:
            self.data[key] = self.data.get(key, 0) + n
            self._broadcast()

    def add_loot(self, loot):
        with self._lock:
            loot["timestamp"] = datetime.now().isoformat()
            self.data["recent_loots"].insert(0, loot)
            self.data["recent_loots"] = self.data["recent_loots"][:50]
            self.data["loots_found"] += 1
            self._broadcast()

    def add_security(self, req):
        with self._lock:
            uid = req.get("user_id")
            if not any(r.get("user_id") == uid for r in self.data["security_pending"]):
                self.data["security_pending"].append(req)
                self._broadcast()

    def resolve_security(self, uid, action):
        with self._lock:
            self.data["security_pending"] = [
                r for r in self.data["security_pending"] if str(r.get("user_id")) != str(uid)
            ]
            self.data["security_logs"].insert(0, {
                "action": action, "user_id": uid,
                "time": datetime.now().isoformat()
            })
            self.data["security_logs"] = self.data["security_logs"][:20]
            self._broadcast()

    def manual_heal(self, bot_name):
        """Manual 'Fix' button from dashboard"""
        with self._lock:
            if bot_name not in self.data["bot_status"]:
                return False
            b = self.data["bot_status"][bot_name]
            b["status"] = "healing"
            b["last_beat"] = time.time()
            b["heal_count"] = b.get("heal_count", 0) + 1
            self._log_heal_internal(bot_name, "Manual fix from dashboard")
            self.data["doctor"]["healing_actions_total"] += 1
            self._broadcast()
            
            start_bot_worker(bot_name)
            return True

    def snapshot(self):
        with self._lock:
            s = dict(self.data)
            s["uptime_seconds"] = int(time.time() - self.data["uptime_start"])
            bots = {}
            now = time.time()
            for n, b in self.data["bot_status"].items():
                nb = dict(b)
                nb["heartbeat_gap"] = int(now - b.get("last_beat", now))
                bots[n] = nb
            s["bot_status"] = bots
            return s

    def subscribe(self):
        q = queue.Queue(maxsize=20)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def _broadcast(self):
        snap = {
            "total_scans": self.data["total_scans"],
            "loots_found": self.data["loots_found"],
            "uptime_seconds": int(time.time() - self.data["uptime_start"]),
            "recent_loots": self.data["recent_loots"][:10],
            "security_pending": self.data["security_pending"],
            "security_logs": self.data["security_logs"][:8],
            "heal_logs": self.data["heal_logs"][:8],
            "doctor": self.data["doctor"],
        }
        now = time.time()
        bots = {}
        for n, b in self.data["bot_status"].items():
            nb = dict(b)
            nb["heartbeat_gap"] = int(now - b.get("last_beat", now))
            bots[n] = nb
        snap["bot_status"] = bots

        dead = []
        for q in self._subs:
            try:
                q.put_nowait(snap)
            except queue.Full:
                dead.append(q)
        for q in dead:
            if q in self._subs:
                self._subs.remove(q)

store = LiveStore()

# ============================================================
# Hooks — bots call these
# ============================================================
def report_bot_scan(bot_name, store_name):
    """Called after every successful scan cycle — serves as heartbeat"""
    store.inc("total_scans", 1)
    cur = store.data["bot_status"].get(bot_name, {})
    store.update_bot(bot_name, store=store_name,
                     scans=cur.get("scans", 0) + 1, status="active")

def report_loot(bot_name, product):
    cur = store.data["bot_status"].get(bot_name, {})
    store.update_bot(bot_name, loots=cur.get("loots", 0) + 1)
    store.add_loot({
        "bot": bot_name,
        "title": product.get("title", "Unknown"),
        "price": product.get("price", "N/A"),
        "mrp": product.get("mrp", "N/A"),
        "discount": product.get("discount", "N/A"),
        "url": product.get("url", "#"),
        "store": product.get("store", "N/A"),
    })

def report_security_request(uid, name, username, channel, chat_id=""):
    store.add_security({
        "user_id": uid, "name": name, "username": username,
        "channel": channel, "chat_id": chat_id, "time": datetime.now().isoformat(),
    })

def report_bot_error(bot_name, err_msg):
    """When bot encounters network error"""
    cur = store.data["bot_status"].get(bot_name, {})
    store.update_bot(bot_name, status="error", last_error=str(err_msg)[:80])

# ============================================================
# Auth
# ============================================================
def api_key_required(f):
    @wraps(f)
    def w(*a, **kw):
        key = request.headers.get("X-Admin-Key", "").strip()
        if session.get("logged_in") or (ADMIN_API_KEY and key == ADMIN_API_KEY):
            return f(*a, **kw)
        return jsonify({"error": "Unauthorized"}), 401
    return w

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("logged_in"):
            return jsonify({"error": "Login required"}), 401
        return f(*a, **kw)
    return w

# ============================================================
# Routes
# ============================================================
@app.route("/")
def index():
    if not session.get("logged_in"):
        return render_template("login.html")
    return render_template("dashboard.html", api_key=ADMIN_API_KEY)

@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    if DASHBOARD_PASSWORD and d.get("password") == DASHBOARD_PASSWORD:
        session["logged_in"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Galat password"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/snapshot")
@login_required
def snapshot():
    return jsonify(store.snapshot())

@app.route("/api/stats")
def api_stats():
    """Public stats endpoint for UptimeRobot monitoring"""
    snap = store.snapshot()
    return jsonify({
        "total_scans": snap["total_scans"],
        "loots_found": snap["loots_found"],
        "uptime_seconds": snap["uptime_seconds"],
        "live_bots": len(snap["bot_status"]),
        "doctor": snap["doctor"]
    })

@app.route("/api/stream")
def stream():
    def gen():
        q = store.subscribe()
        try:
            yield f"data: {json.dumps(store.snapshot())}\n\n"
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            store.unsubscribe(q)
    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# --------- Chat ---------
@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    d = request.get_json() or {}
    msg = (d.get("message") or "").strip()
    history = d.get("history") or []
    if not msg:
        return jsonify({"error": "Khali message"}), 400

    client = get_gemini()
    if client is None:
        return jsonify({"reply": "⚠️ AI chat available nahi hai. `.env` mein `GEMINI_API_KEY` daalein."})

    snap = store.snapshot()
    active = sum(1 for b in snap["bot_status"].values() if b.get("status") == "active")
    dead   = sum(1 for b in snap["bot_status"].values() if b.get("status") in ("error","dead"))

    system = f"""You are JARVIS, the AI assistant of Commander Aman Mishra's 21-bot Amazon/Flipkart loot hunting system.
Current live stats:
- Total scans: {snap['total_scans']}
- Loots caught: {snap['loots_found']}
- Active bots: {active}/21
- Dead/error bots: {dead}
- Pending join requests: {len(snap['security_pending'])}
- Healing actions: {snap['doctor']['healing_actions_total']}

Rules:
- Reply in Hinglish (Hindi + English mix, Roman script).
- Short, friendly, helpful.
- Agar user bot status poochhe to upar ke stats use karo.
- Max 100 words unless zyada detail maangi jaaye."""

    convo = system + "\n\n"
    for h in history[-6:]:
        role = "User" if h.get("role") == "user" else "JARVIS"
        convo += f"{role}: {h.get('content','')}\n"
    convo += f"User: {msg}\nJARVIS:"

    try:
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=convo)
        reply = (resp.text or "").strip() or "Koi jawab nahi mila, dobara try karein."
        return jsonify({"reply": reply})
    except Exception as e:
        logger.error(f"Chat err: {e}")
        return jsonify({"reply": f"⚠️ AI error: {str(e)[:80]}"}), 200

# --------- Security ---------
@app.route("/api/security/approve", methods=["POST"])
@login_required
@api_key_required
def approve():
    d = request.get_json() or {}
    uid = d.get("user_id")
    if not uid: return jsonify({"error": "user_id chahiye"}), 400
    try:
        approve_telegram_user(uid)
    except Exception as e:
        logger.warning(f"approve hook: {e}")
    store.resolve_security(uid, "approved")
    return jsonify({"ok": True})

@app.route("/api/security/reject", methods=["POST"])
@login_required
@api_key_required
def reject():
    d = request.get_json() or {}
    uid = d.get("user_id")
    if not uid: return jsonify({"error": "user_id chahiye"}), 400
    try:
        decline_telegram_user(uid)
    except Exception as e:
        logger.warning(f"reject hook: {e}")
    store.resolve_security(uid, "declined")
    return jsonify({"ok": True})

# --------- Manual Heal ---------
@app.route("/api/bot/heal", methods=["POST"])
@login_required
@api_key_required
def heal_bot():
    d = request.get_json() or {}
    name = d.get("bot_name")
    if not name: return jsonify({"error": "bot_name chahiye"}), 400
    ok = store.manual_heal(name)
    return jsonify({"ok": ok})

@app.route("/api/doctor/heal_all", methods=["POST"])
@login_required
@api_key_required
def heal_all():
    healed = []
    for name, b in list(store.data["bot_status"].items()):
        if b.get("status") in ("error", "dead", "idle"):
            store.manual_heal(name)
            healed.append(name)
    return jsonify({"ok": True, "healed": healed})

# ============================================================
# 🛡️ TELEGRAM SENTINEL & RETRY SENDER (PATCH 2)
# ============================================================
def tg_api(method, payload, retries=4):
    """Safe Telegram API caller with rate-limit retry & backoff"""
    if not BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    for i in range(retries):
        try:
            r = cffi_requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                ra = 5
                try:
                    ra = r.json().get("parameters", {}).get("retry_after", 5)
                except Exception:
                    pass
                logger.warning(f"TG rate-limit, waiting {ra}s")
                time.sleep(ra + 1)
                continue
            logger.warning(f"TG {method} HTTP {r.status_code}: {r.text[:120]}")
            return None
        except Exception as e:
            logger.warning(f"TG {method} error attempt {i+1}: {e}")
            time.sleep(2 ** i)
    return None

def send_telegram_deal_alert(deal):
    """Sends deal with Telegram protect_content & HTML escape protection"""
    raw_title = str(deal.get('title', 'Unknown'))
    safe_title = html.escape(raw_title)
    safe_mrp = html.escape(str(deal.get('mrp', 'N/A')))
    safe_price = html.escape(str(deal.get('price', 'N/A')))
    safe_disc = html.escape(str(deal.get('discount', 'N/A')))
    safe_store = html.escape(str(deal.get('store', 'N/A')))
    deal_url = str(deal.get('url', '#'))

    msg = (
        f"🔥 <b>{safe_disc} OFF Mega Loot Deal!</b> 🔥\n\n"
        f"📦 <b>{safe_title}</b>\n\n"
        f"❌ <b>MRP:</b> {safe_mrp}\n"
        f"💰 <b>Deal Price:</b> {safe_price}\n"
        f"🏷️ <b>Store:</b> {safe_store}\n\n"
        f"⚡ <b>1-Click Buy Link:</b>\n{deal_url}\n\n"
        f"⚠️ <i>Price kabhi bhi badh sakti hai, jaldi check karein!</i>"
    )
    tg_api("sendMessage", {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "protect_content": True
    })

def approve_telegram_user(user_id, chat_id=""):
    try:
        if chat_id:
            tg_api("approveChatJoinRequest", {"chat_id": chat_id, "user_id": int(user_id)})
        tg_api("sendMessage", {
            "chat_id": int(user_id),
            "text": "🛡️ <b>JARVIS SECURITY PROTOCOL // ACCESS GRANTED</b>\n\nCommander Aman Mishra ne aapki request approve kar di hai!",
            "parse_mode": "HTML"
        })
    except Exception as e:
        logger.error(f"Approve TG Error: {e}")

def decline_telegram_user(user_id, chat_id=""):
    try:
        if chat_id:
            tg_api("declineChatJoinRequest", {"chat_id": chat_id, "user_id": int(user_id)})
    except Exception as e:
        logger.error(f"Decline TG Error: {e}")

def telegram_sentinel_daemon():
    logger.info("🛡️ [JARVIS Security Daemon] Sentinel Gatekeeper armed & listening...")
    last_update_id = 0
    while True:
        try:
            if not BOT_TOKEN:
                time.sleep(10); continue
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id + 1,
                "timeout": 20,
                "allowed_updates": '["message","callback_query","chat_join_request"]'
            }
            resp = cffi_requests.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for u in updates:
                    last_update_id = u["update_id"]
                    if "chat_join_request" in u:
                        req = u["chat_join_request"]
                        cid = req["chat"]["id"]
                        ctitle = req["chat"].get("title", "VIP Deals Channel")
                        fu = req["from"]
                        uid = fu["id"]
                        fname = fu.get("first_name", "User")
                        uname = fu.get("username", "")
                        report_security_request(uid, fname, uname, ctitle, cid)

                        # Interactive Telegram buttons to Admin
                        alert = (
                            f"🚨 <b>JARVIS IRON DOME // NEW JOIN REQUEST</b>\n\n"
                            f"👤 <b>Candidate:</b> {html.escape(fname)} (@{html.escape(uname or 'None')})\n"
                            f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                            f"📢 <b>Channel:</b> {html.escape(ctitle)}\n\n"
                            f"<i>Commander Aman, kya ise admit karein?</i>"
                        )
                        btns = {
                            "inline_keyboard": [
                                [
                                    {"text": "✅ APPROVE & ADMIT", "callback_data": f"sec_appr:{uid}:{cid}"},
                                    {"text": "❌ DECLINE & BLOCK", "callback_data": f"sec_decl:{uid}:{cid}"}
                                ]
                            ]
                        }
                        tg_api("sendMessage", {
                            "chat_id": ADMIN_USER_ID, "text": alert, "parse_mode": "HTML", "reply_markup": btns
                        })

                    elif "callback_query" in u:
                        cb = u["callback_query"]
                        cb_data = cb.get("data", "")
                        cb_id = cb["id"]
                        if cb["from"]["id"] == ADMIN_USER_ID:
                            if cb_data.startswith("sec_appr:"):
                                parts = cb_data.split(":")
                                uid = int(parts[1])
                                cid = parts[2] if len(parts) > 2 else ""
                                approve_telegram_user(uid, cid)
                                store.resolve_security(uid, "approved")
                                tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "✅ User Approved!"})
                            elif cb_data.startswith("sec_decl:"):
                                parts = cb_data.split(":")
                                uid = int(parts[1])
                                cid = parts[2] if len(parts) > 2 else ""
                                decline_telegram_user(uid, cid)
                                store.resolve_security(uid, "declined")
                                tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "❌ User Declined!"})
            elif resp.status_code == 409:
                logger.warning("Telegram 409 conflict — another poller is active, backing off 10s")
                time.sleep(10)
        except Exception as e:
            time.sleep(3)

# ============================================================
# 🚨 SILENCE WATCHDOG (PATCH 5: Alert if no loot in 1 hour)
# ============================================================
def silence_watchdog():
    last_alert = 0
    while True:
        time.sleep(600)  # Check every 10 mins
        try:
            snap = store.snapshot()
            last_loot_ts = 0
            if snap["recent_loots"]:
                try:
                    last_loot_ts = datetime.fromisoformat(
                        snap["recent_loots"][0].get("timestamp", "")
                    ).timestamp()
                except Exception:
                    pass
            ref = last_loot_ts or snap["uptime_start"]
            silent_for = time.time() - ref

            if silent_for > 3600 and (time.time() - last_alert) > 3600:
                active = sum(1 for b in snap["bot_status"].values() if b.get("status") == "active")
                blocked = sum(1 for b in snap["bot_status"].values() if b.get("status") == "blocked")
                tg_api("sendMessage", {
                    "chat_id": ADMIN_USER_ID,
                    "text": (
                        f"⚠️ <b>JARVIS WATCHDOG ALERT</b>\n\n"
                        f"Pichle <b>{int(silent_for//60)} min</b> se koi naya loot nahi mila.\n"
                        f"🟢 Active Bots: {active}\n"
                        f"🟠 Blocked/Cooldown: {blocked}\n"
                        f"🩺 Total Doctor Heals: {snap['doctor']['healing_actions_total']}\n\n"
                        f"System check automated diagnostic running..."
                    ),
                    "parse_mode": "HTML"
                })
                last_alert = time.time()
        except Exception as e:
            logger.error(f"Watchdog err: {e}")

# ============================================================
# 🔄 SELF-PING WATCHDOG (Render Free Tier Anti-Sleep)
# ============================================================
def self_ping_watchdog():
    """Pings internal stats endpoint every 9 minutes to avoid idle drops"""
    time.sleep(30)
    while True:
        try:
            cffi_requests.get("http://127.0.0.1:10000/api/stats", timeout=5)
        except Exception:
            pass
        time.sleep(540)

# ==========================================
# 🛒 21 AUTONOMOUS HUNTER WORKERS (PATCH 2, 3, 6)
# ==========================================
BLOCKED_WORDS = ["cover", "case", "tempered glass", "screen protector", "skin", "sticker", "pouch", "disposable", "tissue", "toothpick"]

def is_title_blocked(title):
    if not title: return True
    tl = title.lower()
    for w in BLOCKED_WORDS:
        if " " in w:
            if w in tl: return True
        else:
            if re.search(r'\b' + re.escape(w) + r'\b', tl): return True
    return False

# Bounded LRU Cache (PATCH 6: Expanded to 20,000 items)
import collections
MAX_SEEN = 20000
seen_products = collections.OrderedDict()
seen_lock = threading.Lock()

def is_seen(did):
    with seen_lock:
        if did in seen_products: return True
        seen_products[did] = time.time()
        if len(seen_products) > MAX_SEEN: seen_products.popitem(last=False)
        return False

# Anti-Block Fetcher with User-Agent & Exponential Backoff
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

def fetch_page(url, retries=3):
    """Returns (html, status). html=None if blocked/failed."""
    last_status = 0
    for i in range(retries):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            "Connection": "keep-alive",
        }
        try:
            r = cffi_requests.get(
                url, headers=headers, impersonate="chrome124",
                timeout=25, allow_redirects=True
            )
            last_status = r.status_code
            if r.status_code == 200:
                low = r.text.lower()
                if ("captcha" in low or "enter the characters" in low
                        or "robot check" in low or "api-services-support@amazon.com" in low):
                    logger.warning(f"[CAPTCHA detected] {url[:70]}")
                    time.sleep(random.randint(30, 60))
                    continue
                return r.text, 200
            if r.status_code in (429, 502, 503, 504):
                wait = (2 ** i) * random.uniform(5, 10)
                logger.info(f"[{r.status_code}] backoff {wait:.0f}s — {url[:60]}")
                time.sleep(wait)
                continue
            return None, r.status_code
        except Exception as e:
            logger.warning(f"fetch err ({i+1}/{retries}): {e}")
            time.sleep((2 ** i) * 2)
    return None, last_status

# ============================================================
# WORKER REGISTRY (PATCH 1: Guaranteed 1 thread per bot)
# ============================================================
BOT_WORKERS = {}
WORKER_LOCK = threading.Lock()

def stop_bot_worker(name, timeout=3):
    with WORKER_LOCK:
        w = BOT_WORKERS.pop(name, None)
    if not w:
        return
    w["stop"].set()
    try:
        w["thread"].join(timeout=timeout)
    except Exception:
        pass

def start_bot_worker(name):
    info = HUNTER_TARGETS.get(name)
    if not info:
        return
    stop_bot_worker(name)  # Purana thread band karo pehle!
    ev = threading.Event()
    fn = run_amazon_hunter if info["store"] == "Amazon" else run_flipkart_hunter
    t = threading.Thread(
        target=fn, args=(name, info["cat"], info["kw"], ev), daemon=True
    )
    with WORKER_LOCK:
        BOT_WORKERS[name] = {"thread": t, "stop": ev}
    t.start()

# 21 Targets Definition
HUNTER_TARGETS = {
    # 11 Amazon Targets
    "HUNTER-01": {"store": "Amazon", "cat": "Smartphones", "kw": "smartphone 5g 70% off"},
    "HUNTER-02": {"store": "Amazon", "cat": "Laptops", "kw": "intel core laptop"},
    "HUNTER-03": {"store": "Amazon", "cat": "Audio", "kw": "wireless bluetooth earbuds"},
    "HUNTER-04": {"store": "Amazon", "cat": "Smartwatches", "kw": "smartwatch amoled"},
    "HUNTER-05": {"store": "Amazon", "cat": "Footwear", "kw": "mens running shoes branded"},
    "HUNTER-06": {"store": "Amazon", "cat": "Kitchen Bartan", "kw": "prestige pressure cooker induction"},
    "HUNTER-07": {"store": "Amazon", "cat": "Cookware", "kw": "non stick kadai deep fry pan"},
    "HUNTER-08": {"store": "Amazon", "cat": "Dinner Sets", "kw": "stainless steel dinner set"},
    "HUNTER-09": {"store": "Amazon", "cat": "Groceries", "kw": "dry fruits almonds walnuts combo"},
    "HUNTER-10": {"store": "Amazon", "cat": "Smart TV", "kw": "smart tv 4k 43 inch 55 inch"},
    "HUNTER-11": {"store": "Amazon", "cat": "Fashion", "kw": "branded casual shirt cotton"},
    # 10 Flipkart Targets
    "HUNTER-12": {"store": "Flipkart", "cat": "Mobiles", "kw": "mobile phone 5g"},
    "HUNTER-13": {"store": "Flipkart", "cat": "Laptops", "kw": "gaming laptop"},
    "HUNTER-14": {"store": "Flipkart", "cat": "Audio", "kw": "true wireless earbuds"},
    "HUNTER-15": {"store": "Flipkart", "cat": "Smartwatches", "kw": "smart watch"},
    "HUNTER-16": {"store": "Flipkart", "cat": "Footwear", "kw": "sports shoes men"},
    "HUNTER-17": {"store": "Flipkart", "cat": "Kitchen", "kw": "electric kettle mixer grinder"},
    "HUNTER-18": {"store": "Flipkart", "cat": "Cookware", "kw": "pressure cooker combo"},
    "HUNTER-19": {"store": "Flipkart", "cat": "Televisions", "kw": "smart led tv 43 inch"},
    "HUNTER-20": {"store": "Flipkart", "cat": "Travel & Bags", "kw": "laptop backpack waterproof"},
    "HUNTER-21": {"store": "Flipkart", "cat": "Fashion", "kw": "branded casual shirt cotton"}
}

def run_amazon_hunter(bot_name, cat, kw, stop_event=None):
    base_kw = kw.replace(' ', '+')
    SORT_VARIANTS = ["", "&s=review-rank", "&s=price-asc-rank", "&s=date-desc-rank"]
    empty_streak = 0
    blocked_until = 0
    logger.info(f"[{bot_name}] Amazon hunter active ({cat})")

    while not (stop_event and stop_event.is_set()):
        try:
            if time.time() < blocked_until:
                time.sleep(5)
                continue

            extra = random.choice(SORT_VARIANTS)
            url = f"https://www.amazon.in/s?k={base_kw}{extra}"
            html_text, status = fetch_page(url)

            if html_text is None:
                report_bot_error(bot_name, f"HTTP {status}")
                store.update_bot(bot_name, status="blocked")
                blocked_until = time.time() + random.randint(120, 300)
                continue

            # Heartbeat ONLY on successful fetch
            report_bot_scan(bot_name, "Amazon")

            soup = BeautifulSoup(html_text, "html.parser")
            items = soup.find_all('div', {'data-component-type': 's-search-result'})

            if not items:
                empty_streak += 1
                logger.info(f"[{bot_name}] 0 items on Amazon (streak={empty_streak})")
                if empty_streak >= 3:
                    blocked_until = time.time() + random.randint(180, 360)
                    empty_streak = 0
                    logger.warning(f"[{bot_name}] soft-block detected — cooldown 3-6 min")
            else:
                empty_streak = 0

            for it in items:
                if stop_event and stop_event.is_set():
                    return
                try:
                    h2 = it.find('h2')
                    if not h2: continue
                    title = h2.text.strip()
                    if is_title_blocked(title): continue

                    pw = it.find('span', {'class': 'a-price-whole'})
                    if not pw: continue
                    p_str = re.sub(r'[^\d]', '', pw.text)
                    if not p_str: continue
                    price = int(p_str)

                    mrp_el = it.find('span', {'class': 'a-price', 'data-a-strike': 'true'}) or it.find('span', {'class': 'a-text-price'})
                    if not mrp_el: continue
                    off = mrp_el.find('span', class_='a-offscreen')
                    m_str = re.sub(r'[^\d]', '', off.text if off else mrp_el.text)
                    if not m_str: continue
                    mrp = int(m_str)

                    if mrp <= price or mrp < MIN_MRP: continue
                    discount = int(round(((mrp - price) / mrp) * 100))
                    if discount < MIN_DISCOUNT_PERCENT: continue

                    link_el = it.find('a', {'class': 'a-link-normal s-no-outline'})
                    if not link_el: continue
                    url_p = "https://www.amazon.in" + link_el.get('href', '').split('?')[0]
                    asin_m = re.search(r'/dp/([A-Z0-9]{10})', url_p)
                    did = asin_m.group(1) if asin_m else title[:25]
                    if is_seen(did): continue

                    loot = {
                        "title": title, "price": f"₹{price:,}", "mrp": f"₹{mrp:,}",
                        "discount": f"{discount}%", "url": url_p, "store": "Amazon"
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                except Exception:
                    pass

        except Exception as e:
            report_bot_error(bot_name, e)
            logger.exception(f"{bot_name} loop err")
            time.sleep(10)

        # Interruptible sleep
        for _ in range(random.randint(25, 45)):
            if stop_event and stop_event.is_set():
                return
            time.sleep(1)

def run_flipkart_hunter(bot_name, cat, kw, stop_event=None):
    base_kw = kw.replace(' ', '%20')
    SORT_VARIANTS = ["", "&sort=popularity", "&sort=price_asc"]
    empty_streak = 0
    blocked_until = 0
    logger.info(f"[{bot_name}] Flipkart hunter active ({cat})")

    while not (stop_event and stop_event.is_set()):
        try:
            if time.time() < blocked_until:
                time.sleep(5)
                continue

            extra = random.choice(SORT_VARIANTS)
            url = f"https://www.flipkart.com/search?q={base_kw}{extra}"
            html_text, status = fetch_page(url)

            if html_text is None:
                report_bot_error(bot_name, f"HTTP {status}")
                store.update_bot(bot_name, status="blocked")
                blocked_until = time.time() + random.randint(120, 300)
                continue

            report_bot_scan(bot_name, "Flipkart")

            soup = BeautifulSoup(html_text, "html.parser")
            # Modern + Legacy Flipkart class selectors
            cards = soup.find_all('div', class_=re.compile(r'tUxRFH|_1AtVbE|slAVV4|cPHDOP|_75nlfW|RGLWAk|row'))

            if not cards:
                empty_streak += 1
                logger.info(f"[{bot_name}] 0 cards on Flipkart (streak={empty_streak})")
                if empty_streak >= 3:
                    blocked_until = time.time() + random.randint(180, 360)
                    empty_streak = 0
            else:
                empty_streak = 0

            for c in cards:
                if stop_event and stop_event.is_set():
                    return
                try:
                    te = c.find('div', class_=re.compile(r'KzDlHZ|wjcEIp|_4rR01T|s1Q9rs')) or c.find('a', class_=re.compile(r'IRpwTa|WKTcLC'))
                    if not te: continue
                    title = te.text.strip()
                    if is_title_blocked(title): continue

                    pe = c.find('div', class_=re.compile(r'Nx9bqj|_30jeq3'))
                    if not pe: continue
                    p_str = re.sub(r'[^\d]', '', pe.text)
                    if not p_str: continue
                    price = int(p_str)

                    me = c.find('div', class_=re.compile(r'yRaY8j|_3I9_wc'))
                    if not me: continue
                    m_str = re.sub(r'[^\d]', '', me.text)
                    if not m_str: continue
                    mrp = int(m_str)

                    if mrp <= price or mrp < MIN_MRP: continue
                    discount = int(round(((mrp - price) / mrp) * 100))
                    if discount < MIN_DISCOUNT_PERCENT: continue

                    le = c.find('a', href=True)
                    if not le: continue
                    raw_href = le['href']
                    url_p = f"https://www.flipkart.com{raw_href.split('?')[0]}"
                    did = raw_href.split('/p/')[1].split('?')[0] if '/p/' in raw_href else title[:25]
                    if is_seen(did): continue

                    loot = {
                        "title": title, "price": f"₹{price:,}", "mrp": f"₹{mrp:,}",
                        "discount": f"{discount}%", "url": url_p, "store": "Flipkart"
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                except Exception:
                    pass

        except Exception as e:
            report_bot_error(bot_name, e)
            logger.exception(f"{bot_name} loop err")
            time.sleep(10)

        for _ in range(random.randint(25, 45)):
            if stop_event and stop_event.is_set():
                return
            time.sleep(1)

def start_fleet_and_sentinel():
    """Starts Telegram Sentinel and 21 Autonomous Hunter Bots via Worker Registry"""
    logger.info("🚀 Starting Telegram Sentinel Daemon...")
    threading.Thread(target=telegram_sentinel_daemon, daemon=True).start()

    logger.info("🚀 Starting Silence Watchdog Daemon...")
    threading.Thread(target=silence_watchdog, daemon=True).start()

    logger.info("🚀 Starting Internal Self-Ping Keep-Alive...")
    threading.Thread(target=self_ping_watchdog, daemon=True).start()

    logger.info("🚀 Launching 21 Autonomous Hunter Bots cleanly...")
    for bot_name in HUNTER_TARGETS.keys():
        start_bot_worker(bot_name)
        time.sleep(0.3)
    logger.info("✅ All 21 Autonomous Bots are hunting in parallel without duplicates!")

# Auto-start engines once on app load with Cross-Platform Lock
_engine_started = False
_engine_lock = threading.Lock()

def _acquire_engine_lock():
    """Ensures only 1 master process runs bot workers (handles multi-worker gunicorn)."""
    try:
        import fcntl
        import atexit
        f = open("/tmp/jarvis_engine.lock", "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atexit.register(lambda: f.close())
        return f
    except (ImportError, ModuleNotFoundError):
        # On Windows development
        return True
    except Exception as e:
        logger.warning(f"Engine lock not acquired: {e}")
        return None

def ensure_engines_started():
    global _engine_started
    with _engine_lock:
        if not _engine_started:
            _engine_started = True
            threading.Thread(target=start_fleet_and_sentinel, daemon=True).start()

_engine_lock_fd = _acquire_engine_lock()
if _engine_lock_fd:
    ensure_engines_started()
else:
    logger.warning("Another worker owns engines — this process serves HTTP only.")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"🌐 [JARVIS DASHBOARD] Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
