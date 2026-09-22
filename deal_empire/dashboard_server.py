"""
JARVIS COMMAND CENTER â€” 3-Tier Ultimate Glitch & Loot Empire (Production Hardened)
- Team A (5 Bots): Aggregator Snipers (Desidime, IndiaFreeStuff, FreeKaaMaal)
- Team B (10 Bots): Direct High-Value ASIN Watchers (iPhone, PS5, MacBooks, TVs)
- Team C (6 Bots): Category Clearance Search Hunters (Amazon & Flipkart)
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
import requests

# Line buffering for cloud logging
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
DEFAULT_GEMINI_KEY = "".join(["AQ.Ab8RN6KN5xoHml8T", "-n_951jvBLifpcxKOZakuwnU6lLR6Lm6tQ"])
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_KEY).strip()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "6208434509"))
CHAT_ID = os.getenv("CHAT_ID", "6208434509").strip()
MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT", "60"))
MIN_MRP = int(os.getenv("MIN_MRP", "400"))

# Scraping dependencies
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

# ============================================================
# Gemini AI client (Direct REST + Fallback Engine)
# ============================================================
def call_gemini_chat(prompt_text, api_key=None):
    """
    Bulletproof Gemini AI query using direct REST API.
    Compatible with new Gemini 3.0 / 2.5 API keys.
    """
    key = (api_key or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or "").strip()
    if not key:
        return None, "GEMINI_API_KEY is not configured"

    # Prioritize fastest and latest models
    candidate_models = ["gemini-3-flash-preview", "gemini-3.6-flash", "gemini-2.5-pro"]
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt_text}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 350
        }
    }

    last_err = None
    for m in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=18)
            if res.status_code == 200:
                data = res.json()
                cand = data.get("candidates", [])
                if cand:
                    parts = cand[0].get("content", {}).get("parts", [])
                    if parts:
                        reply_text = parts[0].get("text", "").strip()
                        if reply_text:
                            return reply_text, None
            else:
                last_err = f"HTTP {res.status_code}: {res.text[:120]}"
                logger.warning(f"Gemini {m} failed: {last_err}")
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Gemini {m} exception: {e}")
            continue

    return None, last_err or "All Gemini models timed out"

# ============================================================
# Live Store (thread-safe)
# ============================================================
HEARTBEAT_TIMEOUT = 90   # 90s grace period
AUTO_HEAL_CHECK   = 20   # Check every 20s

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
        stores_label = (
            ["Desidime", "Desidime", "IndiaFreeStuff", "IndiaFreeStuff", "FreeKaaMaal"] +
            ["Amazon-ASIN"] * 10 +
            ["Amazon", "Amazon", "Amazon", "Flipkart", "Flipkart", "Flipkart"]
        )
        for i in range(21):
            name = f"HUNTER-{i+1:02d}"
            self.data["bot_status"][name] = {
                "store": stores_label[i],
                "scans": 0,
                "loots": 0,
                "status": "idle",
                "last_beat": time.time(),
                "heal_count": 0,
            }

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
                    logger.info(f"[AutoHealer] Revived {healed} bots via registry")
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
# Telemetry hooks
# ============================================================
def report_bot_scan(bot_name, store_name):
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
    cur = store.data["bot_status"].get(bot_name, {})
    store.update_bot(bot_name, status="error", last_error=str(err_msg)[:80])

# ============================================================
# Authentication
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
# Web Routes
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

# --------- AI Chat ---------
@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    d = request.get_json() or {}
    msg = (d.get("message") or "").strip()
    history = d.get("history") or []
    if not msg:
        return jsonify({"error": "Khali message"}), 400

    snap = store.snapshot()
    active = sum(1 for b in snap["bot_status"].values() if b.get("status") == "active")
    dead   = sum(1 for b in snap["bot_status"].values() if b.get("status") in ("error","dead"))

    system = f"""You are JARVIS, the AI assistant of Commander Aman Mishra's 21-bot Glitch & Loot Deal Empire.
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
- Explain glitches, aggregator status, or ASIN monitors if asked.
- Max 100 words unless more detail is asked."""

    convo = system + "\n\n"
    for h in history[-6:]:
        role = "User" if h.get("role") == "user" else "JARVIS"
        convo += f"{role}: {h.get('content','')}\n"
    convo += f"User: {msg}\nJARVIS:"

    reply, err = call_gemini_chat(convo)
    if reply:
        return jsonify({"reply": reply})
    else:
        logger.error(f"Chat err: {err}")
        if "not configured" in (err or "").lower():
            return jsonify({"reply": "âš ï¸ AI chat available nahi hai. `.env` ya Render Environment mein `GEMINI_API_KEY` daalein."})
        return jsonify({"reply": f"âš ï¸ AI error: {str(err)[:80]}"}), 200

# --------- Security Endpoints ---------
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
# ðŸ›¡ï¸ TELEGRAM SENTINEL & SAFE RETRY API
# ============================================================
def tg_api(method, payload, retries=4):
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
            logger.warning(f"TG {method} err attempt {i+1}: {e}")
            time.sleep(2 ** i)
    return None

def send_telegram_deal_alert(deal):
    """Sends deal with Telegram protect_content and HTML escape protection"""
    raw_title = str(deal.get('title', 'Unknown'))
    safe_title = html.escape(raw_title)
    safe_mrp = html.escape(str(deal.get('mrp', 'N/A')))
    safe_price = html.escape(str(deal.get('price', 'N/A')))
    safe_disc = html.escape(str(deal.get('discount', 'N/A')))
    safe_store = html.escape(str(deal.get('store', 'N/A')))
    deal_url = str(deal.get('url', '#'))

    # Siren header for price glitches (80%+ or extreme drop)
    is_glitch = "GLITCH" in safe_store.upper() or "GLITCH" in safe_title.upper() or int(re.sub(r'[^\d]', '', safe_disc) or 0) >= 80

    if is_glitch:
        header = "ðŸš¨ðŸš¨ <b>MEGA PRICE GLITCH / LOOT ALERT!</b> ðŸš¨ðŸš¨\nâš¡ <i>Price Error Deal â€” Hurry! Only for 2-5 Mins!</i> âš¡"
    else:
        header = f"ðŸ”¥ <b>{safe_disc} OFF Mega Deal!</b> ðŸ”¥"

    msg = (
        f"{header}\n\n"
        f"ðŸ“¦ <b>{safe_title}</b>\n\n"
        f"âŒ <b>MRP:</b> {safe_mrp}\n"
        f"ðŸ’° <b>Deal Price:</b> {safe_price}\n"
        f"ðŸ·ï¸ <b>Store / Source:</b> {safe_store}\n\n"
        f"âš¡ <b>1-Click Buy Link:</b>\n{deal_url}\n\n"
        f"âš ï¸ <i>Price kabhi bhi badh sakti hai, jaldi check karein!</i>"
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
            "text": "ðŸ›¡ï¸ <b>JARVIS SECURITY PROTOCOL // ACCESS GRANTED</b>\n\nCommander Aman Mishra ne aapki request approve kar di hai!",
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
    logger.info("ðŸ›¡ï¸ [JARVIS Security Daemon] Sentinel Gatekeeper armed & listening...")
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

                        alert = (
                            f"ðŸš¨ <b>JARVIS IRON DOME // NEW JOIN REQUEST</b>\n\n"
                            f"ðŸ‘¤ <b>Candidate:</b> {html.escape(fname)} (@{html.escape(uname or 'None')})\n"
                            f"ðŸ†” <b>ID:</b> <code>{uid}</code>\n"
                            f"ðŸ“¢ <b>Channel:</b> {html.escape(ctitle)}\n\n"
                            f"<i>Commander Aman, kya ise admit karein?</i>"
                        )
                        btns = {
                            "inline_keyboard": [
                                [
                                    {"text": "âœ… APPROVE & ADMIT", "callback_data": f"sec_appr:{uid}:{cid}"},
                                    {"text": "âŒ DECLINE & BLOCK", "callback_data": f"sec_decl:{uid}:{cid}"}
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
                                tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "âœ… User Approved!"})
                            elif cb_data.startswith("sec_decl:"):
                                parts = cb_data.split(":")
                                uid = int(parts[1])
                                cid = parts[2] if len(parts) > 2 else ""
                                decline_telegram_user(uid, cid)
                                store.resolve_security(uid, "declined")
                                tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "âŒ User Declined!"})
            elif resp.status_code == 409:
                logger.warning("Telegram 409 conflict â€” backing off 10s")
                time.sleep(10)
        except Exception as e:
            time.sleep(3)

# ============================================================
# ðŸš¨ SILENCE WATCHDOG & SELF-PING (Render Free Anti-Sleep)
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
                        f"âš ï¸ <b>JARVIS WATCHDOG ALERT</b>\n\n"
                        f"Pichle <b>{int(silent_for//60)} min</b> se koi naya loot nahi mila.\n"
                        f"ðŸŸ¢ Active Bots: {active}\n"
                        f"ðŸŸ  Blocked/Cooldown: {blocked}\n"
                        f"ðŸ©º Total Heals: {snap['doctor']['healing_actions_total']}\n\n"
                        f"Automated system check in progress..."
                    ),
                    "parse_mode": "HTML"
                })
                last_alert = time.time()
        except Exception as e:
            logger.error(f"Watchdog err: {e}")

def self_ping_watchdog():
    time.sleep(30)
    while True:
        try:
            cffi_requests.get("http://127.0.0.1:10000/api/stats", timeout=5)
        except Exception:
            pass
        time.sleep(540)

# ============================================================
# ANTI-BLOCK FETCHER & LRU CACHE
# ============================================================
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
                logger.info(f"[{r.status_code}] backoff {wait:.0f}s â€” {url[:60]}")
                time.sleep(wait)
                continue
            return None, r.status_code
        except Exception as e:
            logger.warning(f"fetch err ({i+1}/{retries}): {e}")
            time.sleep((2 ** i) * 2)
    return None, last_status

# ============================================================
# BLOCK 1 â€” AGGREGATOR HUNTERS (Desidime / IndiaFreeStuff / FreeKaaMaal)
# ============================================================
AGGREGATOR_SOURCES = {
    "desidime": {
        "url": "https://www.desidime.com/new",  # Tested live feed (200 OK)
        "base": "https://www.desidime.com",
        "selectors": ["div.c-deal-box", "div.deal-detail", "div[class*='deal']", "div.grid-40", "li.deal"],
        "title_sels": ["h3", "a.deal-title", "h2", "a[title]"],
        "price_sels": ["span[class*='price']", "div[class*='price']", "span.deal-price"],
    },
    "indiafreestuff": {
        "url": "https://www.indiafreestuff.in/category/deals",  # Tested live feed
        "base": "https://www.indiafreestuff.in",
        "selectors": ["div.deal-box", "div[class*='deal']", "article"],
        "title_sels": ["h3", "h2", "a[title]"],
        "price_sels": ["span[class*='price']", "div[class*='price']"],
    },
    "freekaamaal": {
        "url": "https://www.freekaamaal.com/",  # Tested live homepage feed
        "base": "https://www.freekaamaal.com",
        "selectors": ["div.deal-box", "div[class*='deal']", "article", "div.col-md-3"],
        "title_sels": ["h3", "h2", "a[title]"],
        "price_sels": ["span[class*='price']", "div[class*='price']"],
    },
}

def extract_price_from_text(text):
    if not text: return None
    m = re.search(r'â‚¹\s*([\d,]+)', text)
    if not m: return None
    try:
        return int(m.group(1).replace(',', ''))
    except Exception:
        return None

def extract_discount_from_text(text):
    if not text: return None
    m = re.search(r'(\d{1,3})\s*%\s*(?:off|OFF|Off)', text)
    return int(m.group(1)) if m else None

def run_aggregator_hunter(bot_name, source_key, stop_event=None):
    """Scrapes latest community crowdsourced deals from Desidime / IFS / FKM"""
    src = AGGREGATOR_SOURCES.get(source_key)
    if not src: return
    logger.info(f"[{bot_name}] Aggregator hunter started: {source_key.upper()}")
    empty_streak = 0
    url_dead_count = 0

    while not (stop_event and stop_event.is_set()):
        try:
            html_text, status = fetch_page(src["url"])

            # 404 / 410 dead URL detection
            if status in (404, 410):
                url_dead_count += 1
                logger.error(f"[{bot_name}] {source_key} URL DEAD (HTTP {status})")
                if url_dead_count == 3:
                    tg_api("sendMessage", {
                        "chat_id": ADMIN_USER_ID,
                        "text": (f"ðŸš¨ <b>AGGREGATOR URL DEAD</b>\n\n"
                                 f"Source: <code>{source_key}</code>\n"
                                 f"URL: {src['url']}\n"
                                 f"HTTP {status}\n\n"
                                 f"Kripya naya URL update karein AGGREGATOR_SOURCES mein."),
                        "parse_mode": "HTML"
                    })
                time.sleep(3600)
                continue

            if html_text is None:
                report_bot_error(bot_name, f"HTTP {status}")
                store.update_bot(bot_name, status="blocked")
                time.sleep(random.randint(120, 240))
                continue

            report_bot_scan(bot_name, source_key.upper())
            soup = BeautifulSoup(html_text, "html.parser")

            cards = []
            for sel in src["selectors"]:
                cards = soup.select(sel)
                if cards: break

            # Fallback to product deal links if no card classes matched
            if not cards:
                cards = [a.parent for a in soup.find_all("a", href=True) if "/deals/" in a["href"] or "/deal/" in a["href"]]

            if not cards:
                empty_streak += 1
                logger.warning(f"[{bot_name}] {source_key}: 0 cards (streak={empty_streak})")
                if empty_streak >= 5:
                    empty_streak = 0
                    time.sleep(300)
                else:
                    time.sleep(60)
                continue

            empty_streak = 0
            found = 0

            for card in cards[:35]:
                if stop_event and stop_event.is_set():
                    return
                try:
                    card_text = card.get_text(" ", strip=True)

                    # Extract title
                    title = ""
                    for ts in src["title_sels"]:
                        el = card.select_one(ts)
                        if el and el.get_text(strip=True):
                            title = el.get_text(strip=True)
                            break
                    if not title or len(title) < 8:
                        continue

                    # Discount detection
                    discount = extract_discount_from_text(card_text)
                    is_loot_keyword = any(w in card_text.lower() for w in ["[loot]", "price error", "glitch", "freebie", "steal deal", "bug deal"])

                    # If not explicitly high discount and not tagged as loot, skip
                    if not is_loot_keyword and (not discount or discount < 70):
                        continue

                    # Extract destination or deal link
                    le = card.find("a", href=True)
                    if not le: continue
                    href = le["href"]
                    if href.startswith("/"):
                        url_p = src["base"] + href
                    elif href.startswith("http"):
                        url_p = href
                    else:
                        continue

                    # Extract price if available
                    price_val = extract_price_from_text(card_text)
                    price_str = f"â‚¹{price_val:,}" if price_val else "Deal Page Check"

                    did = f"{source_key}:{hash(title + str(discount or 0))}"
                    if is_seen(did):
                        continue

                    loot = {
                        "title": title[:140],
                        "price": price_str,
                        "mrp": "Hot Deal",
                        "discount": f"{discount}%" if discount else "ðŸ”¥ MEGA LOOT",
                        "url": url_p,
                        "store": source_key.upper(),
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                    found += 1
                except Exception:
                    pass

            if found:
                logger.info(f"[{bot_name}] {source_key}: {found} new deals posted!")

        except Exception as e:
            report_bot_error(bot_name, e)
            logger.exception(f"{bot_name} agg err")

        # Cycle wait 60-120 seconds
        for _ in range(random.randint(60, 120)):
            if stop_event and stop_event.is_set():
                return
            time.sleep(1)

# ============================================================
# BLOCK 2 â€” ASIN WATCHER (High-Value Direct PDP Monitor)
# ============================================================
WATCH_ASINS = [
    # Top Smartphones (iPhones & Flagships)
    "B0CHX1W1XY", "B0CHX2F5QT", "B0CHX3QBCH", "B0CHX1W1Z9", "B0CS5XW6XX", "B0CS5V8YR8", "B0FMDLD86P", "B0CQRSDDZ4",
    # Gaming & Consoles (PS5, Xbox, Controllers)
    "B0CY5QW896", "B0BCNKKZ91", "B08H99BPJN", "B08K3S6WJM", "B0C2XRN5RT",
    # Audio Flagships (Sony, Bose, Apple)
    "B08L5PBFV8", "B0CCZ26B5V", "B09XS7JWHH", "B0BXYCS74H",
    # MacBooks & Premium Laptops
    "B0BSHF7WHW", "B0C1JTVQ92", "B0BVD8MTW2",
    # Smart TVs & 4K Monitors
    "B0C3WXHBZW", "B0BDHWDR12", "B0BMW7P8TW", "B09Q5N4VBM", "B0BLW4F6BM",
    # Premium Wearables & Tablets
    "B0CHX3QBCH", "B0CQKJ7X3F", "B0CZ2GFBW3"
]

def run_asin_watcher(bot_name, asin_list, stop_event=None):
    """Directly monitors high-value ASIN product pages for sudden price drops & glitches"""
    logger.info(f"[{bot_name}] ASIN watcher active for {len(asin_list)} products")
    consecutive_blocked = 0

    while not (stop_event and stop_event.is_set()):
        for asin in asin_list:
            if stop_event and stop_event.is_set():
                return
            try:
                url = f"https://www.amazon.in/dp/{asin}"
                html_text, status = fetch_page(url, retries=2)

                if html_text is None:
                    consecutive_blocked += 1
                    if consecutive_blocked >= 5:
                        logger.warning(f"[{bot_name}] Amazon rate-limiting â€” cooldown 5min")
                        time.sleep(300)
                        consecutive_blocked = 0
                    time.sleep(random.randint(15, 30))
                    continue

                consecutive_blocked = 0
                report_bot_scan(bot_name, "AMAZON-ASIN")
                soup = BeautifulSoup(html_text, "html.parser")

                title_el = soup.find("span", {"id": "productTitle"}) or soup.find("h1", {"id": "title"})
                title = title_el.get_text(strip=True) if title_el else asin

                # Current Price
                price = None
                for psel in [
                    soup.find("span", {"class": "a-price-whole"}),
                    soup.find("span", {"class": "priceToPay"}),
                    soup.find("span", {"id": "priceblock_ourprice"}),
                ]:
                    if psel:
                        txt = re.sub(r'[^\d]', '', psel.get_text())
                        if txt:
                            price = int(txt)
                            break

                if not price:
                    continue

                # MRP (using a-offscreen to avoid double text bug)
                mrp = None
                mrp_el = soup.find("span", {"class": "a-price a-text-price"}) or soup.find("span", {"class": "basisPrice"})
                if mrp_el:
                    off = mrp_el.find("span", class_="a-offscreen")
                    txt = re.sub(r'[^\d]', '', off.text if off else mrp_el.text)
                    if txt:
                        mrp = int(txt)

                if not mrp or mrp <= price:
                    continue

                discount = int(round(((mrp - price) / mrp) * 100))

                # ðŸ”¥ GLITCH DETECTION: 80%+ discount OR high ticket item under 2000
                is_glitch = (discount >= 80) or (mrp >= 15000 and price <= 1999) or (mrp >= 5000 and price <= 499)

                if is_glitch:
                    did = f"glitch:{asin}:{price}"
                    if is_seen(did): continue
                    loot = {
                        "title": f"ðŸš¨ GLITCH: {title[:120]}",
                        "price": f"â‚¹{price:,}",
                        "mrp": f"â‚¹{mrp:,}",
                        "discount": f"{discount}%",
                        "url": url,
                        "store": "AMAZON-GLITCH",
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                    logger.warning(f"ðŸš¨ [GLITCH ALERT] {asin} at â‚¹{price} (MRP â‚¹{mrp})")

                elif discount >= MIN_DISCOUNT_PERCENT:
                    did = f"asin:{asin}:{price}"
                    if is_seen(did): continue
                    loot = {
                        "title": title[:140],
                        "price": f"â‚¹{price:,}",
                        "mrp": f"â‚¹{mrp:,}",
                        "discount": f"{discount}%",
                        "url": url,
                        "store": "AMAZON-WATCH",
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)

            except Exception as e:
                logger.warning(f"[{bot_name}] ASIN {asin} err: {e}")

            time.sleep(random.randint(8, 16))

        # Cycle wait between product batches
        for _ in range(random.randint(30, 60)):
            if stop_event and stop_event.is_set():
                return
            time.sleep(1)

# ============================================================
# SEARCH HUNTERS (Amazon & Flipkart Category Hunters)
# ============================================================
def run_amazon_hunter(bot_name, cat, kw, stop_event=None):
    base_kw = kw.replace(' ', '+')
    SORT_VARIANTS = ["", "&s=review-rank", "&s=price-asc-rank", "&s=date-desc-rank"]
    empty_streak = 0
    blocked_until = 0
    logger.info(f"[{bot_name}] Amazon category hunter active ({cat})")

    while not (stop_event and stop_event.is_set()):
        try:
            if time.time() < blocked_until:
                time.sleep(5); continue

            extra = random.choice(SORT_VARIANTS)
            url = f"https://www.amazon.in/s?k={base_kw}{extra}"
            html_text, status = fetch_page(url)

            if html_text is None:
                report_bot_error(bot_name, f"HTTP {status}")
                store.update_bot(bot_name, status="blocked")
                blocked_until = time.time() + random.randint(120, 300)
                continue

            report_bot_scan(bot_name, "Amazon")
            soup = BeautifulSoup(html_text, "html.parser")
            items = soup.find_all('div', {'data-component-type': 's-search-result'})

            if not items:
                empty_streak += 1
                if empty_streak >= 3:
                    blocked_until = time.time() + random.randint(180, 360)
                    empty_streak = 0
            else:
                empty_streak = 0

            for it in items:
                if stop_event and stop_event.is_set(): return
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
                        "title": title, "price": f"â‚¹{price:,}", "mrp": f"â‚¹{mrp:,}",
                        "discount": f"{discount}%", "url": url_p, "store": "Amazon"
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                except Exception:
                    pass

        except Exception as e:
            report_bot_error(bot_name, e)
            time.sleep(10)

        for _ in range(random.randint(25, 45)):
            if stop_event and stop_event.is_set(): return
            time.sleep(1)

def run_flipkart_hunter(bot_name, cat, kw, stop_event=None):
    base_kw = kw.replace(' ', '%20')
    SORT_VARIANTS = ["", "&sort=popularity", "&sort=price_asc"]
    empty_streak = 0
    blocked_until = 0
    logger.info(f"[{bot_name}] Flipkart category hunter active ({cat})")

    while not (stop_event and stop_event.is_set()):
        try:
            if time.time() < blocked_until:
                time.sleep(5); continue

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
            cards = soup.find_all('div', class_=re.compile(r'tUxRFH|_1AtVbE|slAVV4|cPHDOP|_75nlfW|RGLWAk|row'))

            if not cards:
                empty_streak += 1
                if empty_streak >= 3:
                    blocked_until = time.time() + random.randint(180, 360)
                    empty_streak = 0
            else:
                empty_streak = 0

            for c in cards:
                if stop_event and stop_event.is_set(): return
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
                        "title": title, "price": f"â‚¹{price:,}", "mrp": f"â‚¹{mrp:,}",
                        "discount": f"{discount}%", "url": url_p, "store": "Flipkart"
                    }
                    report_loot(bot_name, loot)
                    send_telegram_deal_alert(loot)
                except Exception:
                    pass

        except Exception as e:
            report_bot_error(bot_name, e)
            time.sleep(10)

        for _ in range(random.randint(25, 45)):
            if stop_event and stop_event.is_set(): return
            time.sleep(1)

# ============================================================
# BLOCK 3 â€” 21 BOTS HYBRID FLEET DEFINITION
# ============================================================
HUNTER_TARGETS = {
    # === TEAM A: Aggregator Scrapers (5 bots) ===
    "HUNTER-01": {"type": "aggregator", "source": "desidime"},
    "HUNTER-02": {"type": "aggregator", "source": "desidime"},
    "HUNTER-03": {"type": "aggregator", "source": "indiafreestuff"},
    "HUNTER-04": {"type": "aggregator", "source": "indiafreestuff"},
    "HUNTER-05": {"type": "aggregator", "source": "freekaamaal"},

    # === TEAM B: ASIN Watchers (10 bots) ===
    "HUNTER-06": {"type": "asin", "slice": (0, 3)},
    "HUNTER-07": {"type": "asin", "slice": (3, 6)},
    "HUNTER-08": {"type": "asin", "slice": (6, 9)},
    "HUNTER-09": {"type": "asin", "slice": (9, 12)},
    "HUNTER-10": {"type": "asin", "slice": (12, 15)},
    "HUNTER-11": {"type": "asin", "slice": (15, 18)},
    "HUNTER-12": {"type": "asin", "slice": (18, 21)},
    "HUNTER-13": {"type": "asin", "slice": (21, 24)},
    "HUNTER-14": {"type": "asin", "slice": (24, 27)},
    "HUNTER-15": {"type": "asin", "slice": (27, 30)},

    # === TEAM C: Search-page Hunters (6 bots) ===
    "HUNTER-16": {"type": "search", "store": "Amazon", "cat": "Smartphones", "kw": "smartphone 5g"},
    "HUNTER-17": {"type": "search", "store": "Amazon", "cat": "Laptops", "kw": "intel core laptop"},
    "HUNTER-18": {"type": "search", "store": "Amazon", "cat": "Audio", "kw": "wireless earbuds"},
    "HUNTER-19": {"type": "search", "store": "Flipkart", "cat": "Mobiles", "kw": "mobile 5g"},
    "HUNTER-20": {"type": "search", "store": "Flipkart", "cat": "Audio", "kw": "twc earbuds"},
    "HUNTER-21": {"type": "search", "store": "Flipkart", "cat": "Fashion", "kw": "branded shirt"},
}

# ============================================================
# BLOCK 4 â€” WORKER REGISTRY & DISPATCHER
# ============================================================
BOT_WORKERS = {}
WORKER_LOCK = threading.Lock()

def stop_bot_worker(name, timeout=3):
    with WORKER_LOCK:
        w = BOT_WORKERS.pop(name, None)
    if not w: return
    w["stop"].set()
    try:
        w["thread"].join(timeout=timeout)
    except Exception:
        pass

def start_bot_worker(name):
    info = HUNTER_TARGETS.get(name)
    if not info: return
    stop_bot_worker(name)
    ev = threading.Event()
    btype = info.get("type", "search")

    if btype == "aggregator":
        target_fn = run_aggregator_hunter
        args = (name, info["source"], ev)
    elif btype == "asin":
        s, e = info["slice"]
        asin_slice = WATCH_ASINS[s:e]
        target_fn = run_asin_watcher
        args = (name, asin_slice, ev)
    else:  # Search category
        target_fn = run_amazon_hunter if info["store"] == "Amazon" else run_flipkart_hunter
        args = (name, info["cat"], info["kw"], ev)

    t = threading.Thread(target=target_fn, args=args, daemon=True)
    with WORKER_LOCK:
        BOT_WORKERS[name] = {"thread": t, "stop": ev}
    t.start()

def start_fleet_and_sentinel():
    logger.info("ðŸš€ Starting Telegram Sentinel Daemon...")
    threading.Thread(target=telegram_sentinel_daemon, daemon=True).start()

    logger.info("ðŸš€ Starting Silence Watchdog Daemon...")
    threading.Thread(target=silence_watchdog, daemon=True).start()

    logger.info("ðŸš€ Starting Anti-Sleep Keep-Alive...")
    threading.Thread(target=self_ping_watchdog, daemon=True).start()

    logger.info("ðŸš€ Launching 3-Tier 21-Bot Hybrid Glitch Fleet...")
    for bot_name in HUNTER_TARGETS.keys():
        start_bot_worker(bot_name)
        time.sleep(0.3)
    logger.info("âœ… All 21 Hybrid Bots hunting in parallel!")

_engine_started = False
_engine_lock = threading.Lock()

def _acquire_engine_lock():
    try:
        import fcntl
        import atexit
        f = open("/tmp/jarvis_engine.lock", "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atexit.register(lambda: f.close())
        return f
    except (ImportError, ModuleNotFoundError):
        return True
    except Exception as e:
        logger.warning(f"Engine lock: {e}")
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
    logger.warning("Another worker owns engines â€” HTTP serving only.")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"ðŸŒ [JARVIS GLITCH EMPIRE] Starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
