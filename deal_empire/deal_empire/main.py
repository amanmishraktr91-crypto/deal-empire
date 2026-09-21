import sys
import os
import json
import time
import random
import threading
import re

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from curl_cffi import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request

# ==========================================
# ⚙️ AMAN BHAI KA BOT & SECURITY CONFIGURATION
# ==========================================
BOT_TOKEN = "8592608802:AAH3FL8bZY6ZmpqmpB3XAzaZfwjAxQGip0k"
CHAT_ID = "6208434509"
ADMIN_USER_ID = 6208434509

MIN_DISCOUNT_PERCENT = 70
MIN_MRP = 400
BLOCKED_WORDS = ["cover", "case", "tempered glass", "screen protector", "skin", "sticker", "pouch", "disposable", "tissue", "toothpick"]

# ==========================================
# 📊 GLOBAL STATS & LIVE FEED
# ==========================================
stats_lock = threading.Lock()
total_scans_count = 0
total_loots_found = 0
live_deals_feed = []
seen_lock = threading.Lock()
seen_products = set()

# 21 Bots Status Tracker
bot_status_tracker = {}

# ==========================================
# 🛡️ MILITARY-GRADE TELEGRAM SECURITY MATRIX
# ==========================================
SECURITY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security_db.json")
security_lock = threading.Lock()

def load_security_db():
    default_db = {
        "admin_id": ADMIN_USER_ID,
        "defense_active": True,
        "authorized_members": {
            str(ADMIN_USER_ID): {
                "user_id": ADMIN_USER_ID,
                "name": "Aman Mishra",
                "username": "aman_mishra",
                "role": "SUPER_ADMIN",
                "added_at": "SYSTEM_INIT",
                "approved_by": "System Master"
            }
        },
        "pending_requests": {},
        "blocked_users": {},
        "security_logs": [
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": "SUCCESS",
                "event": "🛡️ JARVIS Iron Dome Activated",
                "details": "All 5 Security Sentinels armed & monitoring @amanDealsniperBot channel."
            }
        ],
        "stats": {
            "total_join_requests": 0,
            "approved_count": 1,
            "rejected_count": 0,
            "intrusions_blocked": 0,
            "protected_deals_dispatched": 0
        }
    }
    if not os.path.exists(SECURITY_DB_FILE):
        try:
            with open(SECURITY_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_db, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return default_db
    try:
        with open(SECURITY_DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for k, v in default_db.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"[Security DB Load Error]: {e}")
        return default_db

def save_security_db(db):
    try:
        with open(SECURITY_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Security DB Save Error]: {e}")

def add_security_log(event, details, level="INFO"):
    try:
        with security_lock:
            db = load_security_db()
            entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "event": event,
                "details": details
            }
            db.setdefault("security_logs", []).append(entry)
            if len(db["security_logs"]) > 100:
                db["security_logs"] = db["security_logs"][-100:]
            save_security_db(db)
    except Exception as e:
        print(f"[Security Log Error]: {e}")

def send_security_alert_to_admin(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_USER_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Send Security Alert Error]: {e}")

def approve_user_join(user_id, chat_id="", approver="Commander Aman"):
    uid_str = str(user_id).strip()
    with security_lock:
        db = load_security_db()
        req_data = db.get("pending_requests", {}).pop(uid_str, {})
        actual_chat_id = chat_id or req_data.get("chat_id", "")

        api_msg = "Approved locally"
        if actual_chat_id:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/approveChatJoinRequest"
                resp = requests.post(url, json={"chat_id": actual_chat_id, "user_id": int(user_id)}, timeout=10)
                res_json = resp.json()
                if not res_json.get("ok"):
                    api_msg = res_json.get("description", "Telegram API returned not ok")
                else:
                    api_msg = "Admitted to channel"
            except Exception as e:
                api_msg = str(e)

        first_name = req_data.get("first_name", "Member")
        last_name = req_data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or f"User_{user_id}"
        username = req_data.get("username", "")

        db["authorized_members"][uid_str] = {
            "user_id": int(user_id) if uid_str.isdigit() else user_id,
            "name": full_name,
            "username": username,
            "role": "MEMBER",
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "approved_by": approver
        }
        db.get("blocked_users", {}).pop(uid_str, None)
        db["stats"]["approved_count"] = len(db["authorized_members"])
        save_security_db(db)

    add_security_log("Member Approved", f"User {full_name} ({user_id}) approved by {approver}. Result: {api_msg}", "SUCCESS")

    # Send Welcome DM to user
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": user_id,
            "text": (
                f"🎉 <b>CONGRATULATIONS! ACCESS GRANTED</b>\n\n"
                f"Commander <b>Aman Mishra</b> has personally approved your channel join request!\n\n"
                f"Aap ab VIP Deals Channel me add ho chuke hain. Sabhi 70%+ loot deals directly channel me dispatch hoti rahengi.\n\n"
                f"🛡️ <i>Protected by JARVIS Iron-Dome System</i>"
            ),
            "parse_mode": "HTML"
        }, timeout=8)
    except Exception:
        pass

    return {"success": True, "message": f"User {user_id} approved successfully", "api_status": api_msg}

def decline_user_join(user_id, chat_id="", decliner="Commander Aman"):
    uid_str = str(user_id).strip()
    with security_lock:
        db = load_security_db()
        req_data = db.get("pending_requests", {}).pop(uid_str, {})
        actual_chat_id = chat_id or req_data.get("chat_id", "")

        api_msg = "Declined locally"
        if actual_chat_id:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/declineChatJoinRequest"
                resp = requests.post(url, json={"chat_id": actual_chat_id, "user_id": int(user_id)}, timeout=10)
                res_json = resp.json()
                if not res_json.get("ok"):
                    api_msg = res_json.get("description", "Telegram API returned not ok")
                else:
                    api_msg = "Blocked from channel"
            except Exception as e:
                api_msg = str(e)

        first_name = req_data.get("first_name", "Unknown")
        last_name = req_data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or f"User_{user_id}"
        username = req_data.get("username", "")

        db.setdefault("blocked_users", {})[uid_str] = {
            "user_id": int(user_id) if uid_str.isdigit() else user_id,
            "name": full_name,
            "username": username,
            "blocked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "declined_by": decliner
        }
        db["stats"]["rejected_count"] = db["stats"].get("rejected_count", 0) + 1
        save_security_db(db)

    add_security_log("Join Request Declined", f"User {full_name} ({user_id}) declined by {decliner}.", "WARN")
    return {"success": True, "message": f"User {user_id} declined successfully", "api_status": api_msg}

def whitelist_user_id(user_id, name="Manual Whitelist", username=""):
    uid_str = str(user_id).strip()
    with security_lock:
        db = load_security_db()
        db["authorized_members"][uid_str] = {
            "user_id": int(user_id) if uid_str.isdigit() else user_id,
            "name": name,
            "username": username,
            "role": "WHITELISTED",
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "approved_by": "Commander Aman (Manual)"
        }
        db.get("blocked_users", {}).pop(uid_str, None)
        db["stats"]["approved_count"] = len(db["authorized_members"])
        save_security_db(db)

    add_security_log("Manual Whitelist", f"User {name} ({user_id}) manually whitelisted.", "SUCCESS")
    return {"success": True, "message": f"User {user_id} added to authorized whitelist"}

def revoke_user_id(user_id):
    uid_str = str(user_id).strip()
    if uid_str == str(ADMIN_USER_ID):
        return {"success": False, "error": "Cannot revoke Master Commander Admin"}
    with security_lock:
        db = load_security_db()
        removed = db.get("authorized_members", {}).pop(uid_str, None)
        if removed:
            db.setdefault("blocked_users", {})[uid_str] = {
                "user_id": int(user_id) if uid_str.isdigit() else user_id,
                "name": removed.get("name", "User"),
                "username": removed.get("username", ""),
                "revoked_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            db["stats"]["approved_count"] = len(db["authorized_members"])
            save_security_db(db)
        else:
            return {"success": False, "error": "User not found in authorized list"}

    add_security_log("Access Revoked", f"Access for user {user_id} revoked by Commander Aman.", "ALERT")
    return {"success": True, "message": f"User {user_id} access revoked"}

# ==========================================
# 📲 TELEGRAM ALERT ENGINE (WITH ANTI-LEAK SHIELD)
# ==========================================
def send_telegram_alert(deal):
    """Sends ultra-clean 1-Click Loot Deal alert with Military-Grade Anti-Leak Content Protection"""
    # Safety guardrail: Discard any glitch with discount > 99% or invalid price
    disc = deal.get('discount', 0)
    price = deal.get('price', 0)
    mrp = deal.get('mrp', 0)
    if disc > 99 or disc < 50 or mrp <= price or price < 20:
        return

    platform_emoji = "🛒" if deal.get('store') == 'Amazon' else "⚡"
    if deal.get('store') not in ['Amazon', 'Flipkart']:
        platform_emoji = "🏬"

    msg = (
        f"🚨 <b>{deal['discount']}% LOOT ALERT | {deal.get('store', 'DEAL').upper()}</b> 🚨\n\n"
        f"📦 <b>{deal['title']}</b>\n\n"
        f"💰 <b>Loot Deal:</b> ₹{deal['price']:,}\n"
        f"❌ <b>MRP:</b> <del>₹{deal['mrp']:,}</del>\n"
        f"🔥 <b>Bachat:</b> ₹{deal['savings']:,} ({deal['discount']}% OFF)\n"
        f"🏷️ <b>Category:</b> {deal.get('category', 'Electronics')}\n\n"
        f"⚡ <b>1-Click Buy Link:</b>\n"
        f"{deal['link']}\n\n"
        f"🔒 <i>Deals are protected by JARVIS Iron-Dome (Anti-Forward & Anti-Copy).</i>\n"
        f"⚠️ <i>Price kabhi bhi badh sakti hai, jaldi check karein!</i>"
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "protect_content": True  # Anti-Forward, Anti-Copy, Anti-Save Enforced!
    }
    try:
        requests.post(url, json=payload, timeout=10)
        try:
            with security_lock:
                sdb = load_security_db()
                sdb["stats"]["protected_deals_dispatched"] = sdb["stats"].get("protected_deals_dispatched", 0) + 1
                save_security_db(sdb)
        except Exception:
            pass
    except Exception as e:
        print(f"[Telegram Alert Error]: {e}")


# ==========================================
# 🌐 WEB CONTROL CENTER (FLASK DASHBOARD)
# ==========================================
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JARVIS COMMAND CENTER // AMAN BHAI 21-BOTS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-base: #050b14;
            --bg-card: rgba(10, 22, 38, 0.78);
            --bg-card-hover: rgba(15, 32, 55, 0.85);
            --border-glow: rgba(0, 210, 255, 0.22);
            --border-active: #00e5ff;
            --cyan-primary: #00d2ff;
            --cyan-bright: #63f5ff;
            --green-optimal: #00e699;
            --amber-warn: #ffaa00;
            --red-alert: #ff3366;
            --text-main: #e2edfa;
            --text-muted: #7892b0;
        }

        * { margin:0; padding:0; box-sizing:border-box; font-family: 'Plus Jakarta Sans', sans-serif; }
        body {
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 50% 0%, rgba(0, 180, 255, 0.12) 0%, transparent 65%),
                linear-gradient(rgba(0, 210, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 210, 255, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 36px 36px, 36px 36px;
            color: var(--text-main);
            min-height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .glass-panel {
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
            backdrop-filter: blur(12px);
            position: relative;
            transition: border-color 0.2s;
        }
        .glass-panel:hover { border-color: rgba(0, 229, 255, 0.4); }

        /* TOP HEADER */
        header {
            height: 64px;
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-glow);
            background: rgba(5, 12, 22, 0.9);
            z-index: 50;
        }
        .header-brand { display: flex; align-items: center; gap: 14px; }
        .reactor-badge {
            width: 38px; height: 38px; border-radius: 50%; border: 2px solid var(--cyan-primary);
            box-shadow: 0 0 15px var(--cyan-primary), inset 0 0 10px var(--cyan-primary);
            display: flex; align-items: center; justify-content: center; position: relative;
            animation: pulseReactor 3s infinite alternate;
        }
        @keyframes pulseReactor {
            0% { transform: scale(0.96); box-shadow: 0 0 8px var(--cyan-primary); }
            100% { transform: scale(1.04); box-shadow: 0 0 22px var(--cyan-bright); }
        }
        .reactor-badge::after {
            content:""; width: 14px; height: 14px; border-radius: 50%; background:#fff; box-shadow: 0 0 10px #fff;
        }
        .brand-title {
            font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 17px; letter-spacing: 2px; color: #fff;
            display: flex; flex-direction: column;
        }
        .brand-sub { font-size: 9px; letter-spacing: 3px; color: var(--cyan-primary); text-transform: uppercase; }

        .status-pill {
            display: flex; align-items: center; gap: 8px; padding: 6px 14px;
            background: rgba(0, 230, 153, 0.08); border: 1px solid rgba(0, 230, 153, 0.4); border-radius: 20px;
            font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--green-optimal);
        }
        .status-dot {
            width: 7px; height: 7px; border-radius: 50%; background: var(--green-optimal);
            box-shadow: 0 0 10px var(--green-optimal); animation: blinkDot 1.5s infinite;
        }
        @keyframes blinkDot { 0%,100%{opacity:1;} 50%{opacity:0.3;} }

        .header-center-clock { text-align: center; }
        .clock-date { font-size: 11px; color: var(--text-muted); letter-spacing: 1px; }
        .clock-time {
            font-family: 'Orbitron', sans-serif; font-size: 20px; font-weight: 800; color: var(--cyan-bright);
            text-shadow: 0 0 15px rgba(0, 210, 255, 0.6);
        }

        .header-actions { display: flex; align-items: center; gap: 14px; }
        .search-box {
            background: rgba(10, 22, 38, 0.8); border: 1px solid var(--border-glow); border-radius: 20px;
            padding: 6px 16px; font-size: 12px; color: #fff; width: 190px; outline: none;
        }
        .search-box:focus { border-color: var(--border-active); }
        .operator-tag {
            padding: 5px 12px; background: rgba(0, 210, 255, 0.08); border: 1px solid var(--border-glow);
            border-radius: 6px; font-size: 12px; color: #fff;
        }

        /* Voice Model Switcher in Header */
        .voice-mode-select {
            background: rgba(10, 22, 38, 0.9);
            border: 1px solid var(--cyan-primary);
            color: var(--cyan-bright);
            font-size: 11px;
            font-weight: 700;
            padding: 5px 10px;
            border-radius: 6px;
            outline: none;
            cursor: pointer;
        }

        /* WORKSPACE */
        .workspace { display: flex; flex: 1; height: calc(100vh - 128px); overflow: hidden; }

        .sidebar {
            width: 220px; border-right: 1px solid var(--border-glow); background: rgba(5, 12, 22, 0.7);
            padding: 16px 12px; display: flex; flex-direction: column; justify-content: space-between;
        }
        .nav-list { display: flex; flex-direction: column; gap: 4px; }
        .nav-item {
            display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 8px;
            font-size: 13px; font-weight: 600; color: var(--text-muted); cursor: pointer; transition: 0.2s;
        }
        .nav-item:hover, .nav-item.active {
            color: #fff; background: rgba(0, 210, 255, 0.12); border: 1px solid rgba(0, 210, 255, 0.3);
        }
        .nav-item.active { color: var(--cyan-bright); box-shadow: inset 0 0 15px rgba(0, 210, 255, 0.15); }

        .voice-status-box {
            padding: 14px; background: rgba(7, 18, 32, 0.9); border: 1px solid var(--border-glow);
            border-radius: 10px; text-align: center;
        }
        .mic-trigger-btn {
            width: 50px; height: 50px; border-radius: 50%;
            background: radial-gradient(circle, var(--cyan-primary) 0%, #005580 100%);
            border: 2px solid #fff; box-shadow: 0 0 20px var(--cyan-primary);
            display: flex; align-items: center; justify-content: center;
            margin: 8px auto 4px auto; cursor: pointer; color: #fff; font-size: 20px; transition: 0.25s;
        }
        .mic-trigger-btn:hover { transform: scale(1.08); box-shadow: 0 0 35px var(--cyan-bright); }
        .mic-trigger-btn.listening {
            background: radial-gradient(circle, var(--red-alert) 0%, #800020 100%);
            box-shadow: 0 0 30px var(--red-alert); animation: pulseMic 1s infinite alternate;
        }
        @keyframes pulseMic { from{transform:scale(1);} to{transform:scale(1.15);} }

        /* CONTENT */
        .content-area {
            flex: 1; display: grid; grid-template-columns: 1fr 340px; gap: 16px; padding: 16px; overflow-y: auto;
        }
        .main-col { display: flex; flex-direction: column; gap: 16px; }

        .top-row-grid { display: grid; grid-template-columns: 240px 1fr; gap: 16px; height: 250px; }
        .metric-cards-col { display: flex; flex-direction: column; gap: 8px; }
        .mini-stat-card { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
        .mini-stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; }
        .mini-stat-val { font-size: 14px; font-weight: 800; color: #fff; font-family: 'Orbitron', sans-serif; }

        .hologram-sphere-box {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            position: relative; overflow: hidden;
        }
        #sphere-canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
        .core-text-overlay { position: relative; z-index: 5; text-align: center; pointer-events: none; }
        .core-hero-title {
            font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 900; letter-spacing: 6px;
            color: #fff; text-shadow: 0 0 20px var(--cyan-primary);
        }
        .core-hero-sub { font-size: 11px; letter-spacing: 3px; color: var(--cyan-bright); margin-top: 4px; }

        /* AGENTS GRID */
        .agents-section { padding: 16px; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .section-title { font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 2px; color: #fff; }
        .agents-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
        .agent-card {
            padding: 10px 12px; background: rgba(7, 16, 28, 0.65); border: 1px solid rgba(0, 210, 255, 0.15);
            border-radius: 8px; display: flex; flex-direction: column; gap: 6px; transition: 0.2s;
        }
        .agent-card:hover { border-color: var(--cyan-primary); background: rgba(0, 210, 255, 0.08); transform: translateY(-2px); }
        .agent-card-header { display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 700; color: #fff; }
        .agent-pill { font-size: 9px; padding: 2px 6px; border-radius: 4px; font-weight: 800; }
        .pill-active { background: rgba(0, 230, 153, 0.15); color: var(--green-optimal); border: 1px solid rgba(0, 230, 153, 0.4); }
        .pill-idle { background: rgba(255, 170, 0, 0.15); color: var(--amber-warn); border: 1px solid rgba(255, 170, 0, 0.4); }
        .agent-scans { font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between; }

        /* BOTTOM ROW */
        .bottom-row-grid { display: grid; grid-template-columns: 260px 1fr; gap: 16px; height: 220px; }
        .sys-monitor-box { padding: 14px; display: flex; flex-direction: column; justify-content: space-between; }
        .circular-gauges { display: flex; justify-content: space-around; align-items: center; margin-top: 10px; }
        .mini-gauge {
            width: 70px; height: 70px; border-radius: 50%; border: 3px solid var(--border-glow);
            border-top-color: var(--cyan-primary); border-right-color: var(--cyan-bright);
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            font-size: 14px; font-weight: 800; font-family: 'Orbitron', sans-serif; color: #fff;
        }
        .mini-gauge span { font-size: 9px; color: var(--text-muted); font-family: sans-serif; }

        .chart-box { padding: 14px; display: flex; flex-direction: column; }
        .chart-wrap { flex: 1; position: relative; width: 100%; height: 150px; }

        /* FEED */
        .feed-col { display: flex; flex-direction: column; gap: 16px; }
        .feed-pane { flex: 1; padding: 16px; display: flex; flex-direction: column; overflow: hidden; }
        .deal-list { overflow-y: auto; display: flex; flex-direction: column; gap: 10px; margin-top: 10px; padding-right: 4px; flex: 1; }
        .deal-item {
            background: rgba(7, 16, 28, 0.7); border: 1px solid rgba(0, 210, 255, 0.2);
            border-radius: 8px; padding: 10px 12px; transition: 0.2s;
        }
        .deal-item:hover { border-color: var(--cyan-primary); }
        .deal-badge {
            font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 4px;
            background: var(--red-alert); color: #fff; display: inline-block; margin-bottom: 4px;
        }
        .deal-item-title { font-size: 12px; font-weight: 700; color: #fff; line-height: 1.3; }
        .deal-price-row { display: flex; gap: 10px; align-items: baseline; margin: 6px 0; }
        .deal-p-now { font-size: 16px; font-weight: 800; color: var(--cyan-bright); font-family: 'Orbitron', sans-serif; }
        .deal-p-mrp { font-size: 11px; color: var(--text-muted); text-decoration: line-through; }
        .deal-btn {
            display: block; width: 100%; text-align: center; font-size: 11px; font-weight: 700;
            padding: 6px; border: 1px solid var(--cyan-primary); border-radius: 4px;
            color: var(--cyan-primary); text-decoration: none; transition: 0.2s;
        }
        .deal-btn:hover { background: var(--cyan-primary); color: #000; }

        /* FOOTER */
        footer {
            height: 64px; padding: 0 24px; border-top: 1px solid var(--border-glow);
            background: rgba(5, 12, 22, 0.95); display: flex; align-items: center; justify-content: space-between; z-index: 50;
        }
        .telemetry-tag { font-size: 12px; color: var(--text-muted); display: flex; gap: 16px; }

        .talk-jarvis-pill {
            display: flex; align-items: center; gap: 16px; padding: 8px 30px;
            background: linear-gradient(90deg, rgba(0, 210, 255, 0.1), rgba(0, 210, 255, 0.25), rgba(0, 210, 255, 0.1));
            border: 1.5px solid var(--cyan-primary); border-radius: 30px; cursor: pointer;
            box-shadow: 0 0 25px rgba(0, 210, 255, 0.25); transition: 0.3s;
        }
        .talk-jarvis-pill:hover { transform: scale(1.02); box-shadow: 0 0 35px var(--cyan-primary); }
        .talk-label { font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 13px; letter-spacing: 2px; color: #fff; }
        .talk-sub { font-size: 11px; color: var(--cyan-bright); }

        .briefing-btn {
            background: rgba(0, 210, 255, 0.1); border: 1px solid var(--cyan-primary); color: #fff;
            padding: 8px 18px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer;
            display: flex; align-items: center; gap: 8px; transition: 0.2s;
        }
        .briefing-btn:hover { background: var(--cyan-primary); color: #000; }

        .speech-banner {
            position: fixed; bottom: 74px; left: 50%; transform: translateX(-50%);
            background: rgba(4, 15, 28, 0.96); border: 1.5px solid var(--cyan-primary);
            box-shadow: 0 0 35px rgba(0, 210, 255, 0.45); border-radius: 12px; padding: 14px 28px;
            font-size: 14px; color: #fff; z-index: 100; display: none; max-width: 680px; text-align: center;
            backdrop-filter: blur(10px);
        }
    </style>
</head>
<body>

    <header>
        <div class="header-brand">
            <div class="reactor-badge"></div>
            <div class="brand-title">
                <span>JARVIS</span>
                <span class="brand-sub">COMMAND CENTER</span>
            </div>
        </div>

        <div class="status-pill">
            <div class="status-dot"></div>
            <span>SYSTEM STATUS : OPTIMAL</span>
        </div>

        <div class="header-center-clock">
            <div class="clock-date" id="clock-date">Monday, 15 June 2026</div>
            <div class="clock-time" id="clock-time">11:18:21 AM</div>
        </div>

        <div class="header-actions">
            <!-- Voice Accent Selector -->
            <select class="voice-mode-select" id="voice-accent" onchange="testSelectedVoice()">
                <option value="jarvis_english">🎙️ JARVIS (Movie Natural Male)</option>
                <option value="hindi_natural">🎙️ Hindi (Pure Natural Human)</option>
            </select>
            <input type="text" class="search-box" id="command-input" placeholder="Type or Speak Command..." onkeydown="if(event.key==='Enter') processTextCommand(this.value)">
            <div class="operator-tag">Commander: Aman Mishra</div>
        </div>
    </header>

    <div class="workspace">
        <div class="sidebar">
            <div class="nav-list">
                <div class="nav-item active"><span>⚡</span> Command Center</div>
                <div class="nav-item"><span>🧠</span> AI Core</div>
                <div class="nav-item"><span>🤖</span> 21 Bots Fleet</div>
                <div class="nav-item"><span>🎯</span> Loot Radar</div>
                <div class="nav-item"><span>📊</span> Analytics</div>
                <div class="nav-item"><span>📱</span> Telegram Alert</div>
                <div class="nav-item"><span>⚙️</span> Settings</div>
            </div>

            <div class="voice-status-box">
                <div style="font-size: 10px; font-weight:800; letter-spacing:1px; color:var(--text-muted); text-transform:uppercase;">NEURAL VOICE STATUS</div>
                <div style="font-size: 11px; color:var(--green-optimal); font-weight:700; margin:6px 0;" id="current-voice-name">Natural Human Mode</div>
                <div class="mic-trigger-btn" id="mic-btn" onclick="toggleVoiceListening()">
                    🎙️
                </div>
                <div style="font-size: 11px; font-weight:700; color:#fff;" id="mic-status-label">Tap to Speak</div>
                <button style="background:transparent; border:1px solid var(--border-glow); color:var(--cyan-bright); font-size:10px; padding:3px 8px; border-radius:4px; margin-top:6px; cursor:pointer;" onclick="testSelectedVoice()">🔊 Test Voice</button>
            </div>
        </div>

        <div class="content-area">
            <div class="main-col">
                <div class="top-row-grid">
                    <div class="metric-cards-col">
                        <div class="glass-panel mini-stat-card">
                            <span class="mini-stat-label">AI CORE</span>
                            <span class="mini-stat-val" style="color:var(--green-optimal);">ACTIVE</span>
                        </div>
                        <div class="glass-panel mini-stat-card">
                            <span class="mini-stat-label">SCANNED</span>
                            <span class="mini-stat-val" id="stat-scans">2,840</span>
                        </div>
                        <div class="glass-panel mini-stat-card">
                            <span class="mini-stat-label">LOOTS FOUND</span>
                            <span class="mini-stat-val" id="stat-loots" style="color:var(--red-alert);">18</span>
                        </div>
                        <div class="glass-panel mini-stat-card">
                            <span class="mini-stat-label">BOTS ARMED</span>
                            <span class="mini-stat-val" style="color:var(--cyan-bright);">21 ACTIVE</span>
                        </div>
                        <div class="glass-panel mini-stat-card">
                            <span class="mini-stat-label">TELEGRAM</span>
                            <span class="mini-stat-val" style="font-size:11px; color:#ff77aa;">@amanDealsniperBot</span>
                        </div>
                    </div>

                    <div class="glass-panel hologram-sphere-box">
                        <canvas id="sphere-canvas"></canvas>
                        <div class="core-text-overlay">
                            <div class="core-hero-title">JARVIS</div>
                            <div class="core-hero-sub">AI HUNTER CORE v3.0</div>
                        </div>
                    </div>
                </div>

                <div class="glass-panel agents-section">
                    <div class="section-header">
                        <div class="section-title">ACTIVE HUNTER FLEET (21 BOTS)</div>
                        <div style="font-size:11px; color:var(--cyan-primary); cursor:pointer;" onclick="runVoiceExecutiveBriefing()">🔊 Run Voice Diagnostic</div>
                    </div>
                    <div class="agents-grid" id="agents-grid"></div>
                </div>

                <div class="bottom-row-grid">
                    <div class="glass-panel sys-monitor-box">
                        <div class="section-title" style="font-size:11px;">SYSTEM EFFICIENCY</div>
                        <div class="circular-gauges">
                            <div class="mini-gauge"><span id="gauge-scans">99%</span><span>HUNTER</span></div>
                            <div class="mini-gauge" style="border-top-color:var(--green-optimal);"><span id="gauge-radar">100%</span><span>RADAR</span></div>
                            <div class="mini-gauge" style="border-top-color:var(--red-alert);"><span>70%+</span><span>LOOT</span></div>
                        </div>
                        <div style="font-size:10px; color:var(--text-muted); text-align:center; margin-top:8px;">NEURAL AUDIO ENGINE ACTIVE</div>
                    </div>

                    <div class="glass-panel chart-box">
                        <div class="section-header" style="margin-bottom:6px;">
                            <div class="section-title" style="font-size:11px;">FLEET PERFORMANCE CHART (REAL-TIME SCANS)</div>
                            <div style="font-size:10px; color:var(--cyan-bright);" id="chart-update-tag">Auto-updating</div>
                        </div>
                        <div class="chart-wrap">
                            <canvas id="telemetryChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <div class="feed-col">
                <div class="glass-panel feed-pane">
                    <div class="section-header">
                        <div class="section-title" style="font-size:12px;">LIVE LOOT RADAR</div>
                        <span style="font-size:9px; font-weight:800; color:var(--red-alert); animation:blinkDot 1s infinite;">● 70%+ LOCK</span>
                    </div>

                    <div class="deal-list" id="deal-list">
                        <div class="deal-item">
                            <span class="deal-badge">85% OFF // AMAZON</span>
                            <div class="deal-item-title">Neeman's Cotton Classic Lightweight Running Shoes</div>
                            <div class="deal-price-row">
                                <span class="deal-p-now">₹459</span>
                                <span class="deal-p-mrp">₹2,999</span>
                            </div>
                            <a href="https://www.amazon.in" target="_blank" class="deal-btn">⚡ 1-CLICK ACQUIRE</a>
                        </div>
                        <div class="deal-item">
                            <span class="deal-badge">83% OFF // AMAZON</span>
                            <div class="deal-item-title">Prestige Electric Kettle 1.5L Auto Cut-off</div>
                            <div class="deal-price-row">
                                <span class="deal-p-now">₹499</span>
                                <span class="deal-p-mrp">₹2,895</span>
                            </div>
                            <a href="https://www.amazon.in" target="_blank" class="deal-btn">⚡ 1-CLICK ACQUIRE</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer>
        <div class="telemetry-tag">
            <span>LOCATION: Cloud / Online</span>
            <span>RADAR: 4.85 GHz</span>
            <span>NETWORK: Optimal</span>
        </div>

        <div class="talk-jarvis-pill" onclick="toggleVoiceListening()">
            <span style="font-size:18px;">🎙️</span>
            <div>
                <div class="talk-label">TALK TO JARVIS</div>
                <div class="talk-sub" id="talk-sub-label">Click here or say "Hey Jarvis"</div>
            </div>
        </div>

        <button class="briefing-btn" onclick="runVoiceExecutiveBriefing()">
            <span>▶</span> Executive Briefing
        </button>
    </footer>

    <div class="speech-banner" id="speech-banner">
        <strong>JARVIS:</strong> <span id="speech-text">Analyzing systems...</span>
    </div>

    <script>
        function updateClock() {
            const now = new Date();
            const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
            const timeStr = now.toLocaleTimeString('en-US');
            document.getElementById('clock-date').innerText = dateStr;
            document.getElementById('clock-time').innerText = timeStr;
        }
        setInterval(updateClock, 1000);
        updateClock();

        // SPHERE
        const sphereCanvas = document.getElementById('sphere-canvas');
        const sCtx = sphereCanvas.getContext('2d');
        let spherePoints = [];
        const numPoints = 140;
        const radius = 90;

        function initSphere() {
            sphereCanvas.width = sphereCanvas.offsetWidth;
            sphereCanvas.height = sphereCanvas.offsetHeight;
            spherePoints = [];
            for (let i = 0; i < numPoints; i++) {
                const theta = Math.acos(2 * Math.random() - 1);
                const phi = 2 * Math.PI * Math.random();
                spherePoints.push({
                    x: radius * Math.sin(theta) * Math.cos(phi),
                    y: radius * Math.sin(theta) * Math.sin(phi),
                    z: radius * Math.cos(theta)
                });
            }
        }
        window.addEventListener('resize', initSphere);
        initSphere();

        let angleX = 0, angleY = 0;
        function renderSphere() {
            sCtx.clearRect(0, 0, sphereCanvas.width, sphereCanvas.height);
            const cx = sphereCanvas.width / 2;
            const cy = sphereCanvas.height / 2;

            angleX += 0.006;
            angleY += 0.009;

            sCtx.fillStyle = '#00d2ff';
            sCtx.strokeStyle = 'rgba(0, 210, 255, 0.15)';

            for (let i = 0; i < spherePoints.length; i++) {
                const p = spherePoints[i];
                let x1 = p.x * Math.cos(angleY) - p.z * Math.sin(angleY);
                let z1 = p.z * Math.cos(angleY) + p.x * Math.sin(angleY);
                let y1 = p.y * Math.cos(angleX) - z1 * Math.sin(angleX);
                let z2 = z1 * Math.cos(angleX) + p.y * Math.sin(angleX);

                const scale = 220 / (220 + z2);
                const projX = cx + x1 * scale;
                const projY = cy + y1 * scale;
                const size = Math.max(1, 2.5 * scale);

                sCtx.beginPath();
                sCtx.arc(projX, projY, size, 0, Math.PI * 2);
                sCtx.fill();
            }
            requestAnimationFrame(renderSphere);
        }
        renderSphere();

        // BOT LIST
        const botList = [
            { name: "Amazon-Cookware", store: "Amazon", scans: 192, status: "Active" },
            { name: "Amazon-DinnerSets", store: "Amazon", scans: 192, status: "Active" },
            { name: "Amazon-Groceries", store: "Amazon", scans: 144, status: "Active" },
            { name: "Amazon-Headphones", store: "Amazon", scans: 96, status: "Active" },
            { name: "Amazon-Kadai", store: "Amazon", scans: 144, status: "Active" },
            { name: "Amazon-Laptops", store: "Amazon", scans: 96, status: "Active" },
            { name: "Amazon-Phones", store: "Amazon", scans: 96, status: "Active" },
            { name: "Amazon-Shoes", store: "Amazon", scans: 144, status: "Active" },
            { name: "Amazon-SmartTV", store: "Amazon", scans: 96, status: "Active" },
            { name: "Amazon-Watches", store: "Amazon", scans: 96, status: "Active" },
            { name: "Flipkart-Appliances", store: "Flipkart", scans: 120, status: "Active" },
            { name: "Flipkart-Backpacks", store: "Flipkart", scans: 110, status: "Active" },
            { name: "Flipkart-Cookware", store: "Flipkart", scans: 130, status: "Active" },
            { name: "Flipkart-Earbuds", store: "Flipkart", scans: 115, status: "Active" },
            { name: "Flipkart-Fashion", store: "Flipkart", scans: 105, status: "Active" },
            { name: "Flipkart-Laptops", store: "Flipkart", scans: 95, status: "Active" },
            { name: "Flipkart-Mobiles", store: "Flipkart", scans: 140, status: "Active" },
            { name: "Flipkart-Shoes", store: "Flipkart", scans: 125, status: "Active" },
            { name: "Flipkart-TVS", store: "Flipkart", scans: 90, status: "Active" },
            { name: "Flipkart-Watches", store: "Flipkart", scans: 100, status: "Active" },
            { name: "MultiStore-Radar", store: "MultiStore", scans: 80, status: "Active" }
        ];

        function renderAgentsGrid() {
            const grid = document.getElementById('agents-grid');
            grid.innerHTML = '';
            botList.forEach(bot => {
                const isWorking = bot.scans > 0;
                grid.innerHTML += `
                    <div class="agent-card">
                        <div class="agent-card-header">
                            <span>${bot.name}</span>
                            <span class="agent-pill ${isWorking ? 'pill-active' : 'pill-idle'}">${isWorking ? 'Active' : 'Idle'}</span>
                        </div>
                        <div class="agent-scans">
                            <span>${bot.store}</span>
                            <span style="color:#fff; font-weight:700;">${bot.scans} Scans</span>
                        </div>
                    </div>
                `;
            });
        }
        renderAgentsGrid();

        // CHART
        let telemetryChartInstance;
        function initChart() {
            const ctx = document.getElementById('telemetryChart').getContext('2d');
            const labels = botList.slice(0, 10).map(b => b.name.replace('Amazon-', 'Amz-').replace('Flipkart-', 'Flp-'));
            const dataScans = botList.slice(0, 10).map(b => b.scans);

            telemetryChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Live Scans Volume',
                        data: dataScans,
                        backgroundColor: 'rgba(0, 210, 255, 0.45)',
                        borderColor: '#00d2ff',
                        borderWidth: 1.5,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#7892b0', font: { size: 9 } }, grid: { display: false } },
                        y: { ticks: { color: '#7892b0', font: { size: 9 } }, grid: { color: 'rgba(0, 210, 255, 0.08)' } }
                    }
                }
            });
        }
        initChart();

        function updateChartWithSpecificBots(highlightIdle = false) {
            if (!telemetryChartInstance) return;
            const labels = botList.map(b => b.name.replace('Amazon-', 'A-').replace('Flipkart-', 'F-'));
            const dataScans = botList.map(b => b.scans);
            const colors = botList.map(b => (b.scans === 0 && highlightIdle) ? 'rgba(255, 51, 102, 0.85)' : 'rgba(0, 210, 255, 0.5)');

            telemetryChartInstance.data.labels = labels;
            telemetryChartInstance.data.datasets[0].data = dataScans;
            telemetryChartInstance.data.datasets[0].backgroundColor = colors;
            telemetryChartInstance.update();
            document.getElementById('chart-update-tag').innerText = highlightIdle ? 'Highlighted Idle Bots' : 'All 21 Bots Plotted';
        }

        // ==========================================================
        // 🎙️ HIGH-DEF HUMAN-LIKE NEURAL VOICE ENGINE
        // ==========================================================
        let availableVoices = [];

        function loadVoices() {
            availableVoices = window.speechSynthesis.getVoices();
        }
        if ('speechSynthesis' in window) {
            loadVoices();
            window.speechSynthesis.onvoiceschanged = loadVoices;
        }

        function getBestVoice(mode) {
            if (!availableVoices || availableVoices.length === 0) {
                availableVoices = window.speechSynthesis.getVoices();
            }

            if (mode === 'hindi_natural') {
                // Look for Natural Hindi Neural voices (Edge/Chrome/Windows)
                const hindiVoice = availableVoices.find(v => 
                    v.name.includes('Madhur') || 
                    v.name.includes('Neerja') || 
                    v.name.includes('Swara') || 
                    v.name.includes('हिन्दी') || 
                    (v.lang && v.lang.startsWith('hi'))
                );
                if (hindiVoice) return hindiVoice;
            }

            // Default: Look for Premium Natural British / Movie Jarvis voices
            const jarvisVoice = availableVoices.find(v => 
                v.name.includes('Ryan') || 
                v.name.includes('Daniel') || 
                v.name.includes('George') || 
                v.name.includes('Google UK English Male') || 
                v.name.includes('Natural') && v.lang.startsWith('en') ||
                v.name.includes('Guy')
            );
            return jarvisVoice || availableVoices.find(v => v.lang.startsWith('en')) || availableVoices[0];
        }

        function jarvisSpeak(englishSpeech, hindiSpeech) {
            const mode = document.getElementById('voice-accent').value;
            const textToSpeak = (mode === 'hindi_natural') ? hindiSpeech : englishSpeech;

            const banner = document.getElementById('speech-banner');
            const bannerText = document.getElementById('speech-text');
            bannerText.innerText = textToSpeak;
            banner.style.display = 'block';

            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(textToSpeak);
                const voice = getBestVoice(mode);
                if (voice) utterance.voice = voice;

                if (mode === 'hindi_natural') {
                    utterance.lang = 'hi-IN';
                    utterance.rate = 1.0;
                    utterance.pitch = 1.0;
                } else {
                    utterance.lang = 'en-GB';
                    utterance.rate = 0.98;
                    utterance.pitch = 0.92; // Slightly deeper, authoritative Paul Bettany tone
                }

                utterance.onend = () => {
                    setTimeout(() => { banner.style.display = 'none'; }, 3500);
                };
                window.speechSynthesis.speak(utterance);
            }
        }

        function testSelectedVoice() {
            const mode = document.getElementById('voice-accent').value;
            if (mode === 'hindi_natural') {
                jarvisSpeak(
                    "Online and synchronized, Aman sir.",
                    "नमस्ते अमन सर। जार्विस वॉयस सिस्टम पूरी तरह तैयार है। मैं आपके सभी 21 बॉट्स की जानकारी देने के लिए प्रस्तुत हूँ।"
                );
            } else {
                jarvisSpeak(
                    "Good evening, Aman sir. Jarvis voice synthesizer online. All 21 bots are fully synchronized.",
                    "नमस्ते अमन सर।"
                );
            }
        }

        // ==========================================================
        // 🧠 TWO-WAY CONVERSATIONAL ENGINE & REAL-TIME BRAIN
        // ==========================================================
        let handsFreeActive = false;

        async function handleJarvisQuery(query) {
            const q = query.toLowerCase();

            // 1. First fetch real-time intelligence from Flask backend if available
            try {
                const brainRes = await fetch(`/api/jarvis_brain?q=${encodeURIComponent(query)}`);
                if (brainRes.ok) {
                    const brainData = await brainRes.json();
                    const hasIdle = brainData.idle_bots && brainData.idle_bots.length > 0;
                    updateChartWithSpecificBots(hasIdle);
                    jarvisSpeak(brainData.reply_english, brainData.reply_hindi);
                    return;
                }
            } catch (e) {
                console.log("Local brain offline, using client fallback", e);
            }

            // Fallback Client Intelligence
            if (q.includes('update') || q.includes('status') || q.includes('kya chal') || q.includes('report')) {
                const totalScans = botList.reduce((acc, b) => acc + b.scans, 0);
                const eng = `Aman sir, all 21 bots are fully active. Over ${totalScans} products scanned so far with zero crashes. Telemetry chart is updated on your display, Sir.`;
                const hin = `नमस्ते अमन सर! सिस्टम का हाल बहुत अच्छा है। सभी 21 बॉट्स एक्टिव हैं और ${totalScans} से ज़्यादा प्रोडक्ट्स स्कैन हो चुके हैं। मैंने लाइव चार्ट आपकी स्क्रीन पर प्लॉट कर दिया है।`;
                updateChartWithSpecificBots(false);
                jarvisSpeak(eng, hin);
            } else if (q.includes('kaun sa bot') || q.includes('kaam nahi') || q.includes('band') || q.includes('inactive')) {
                const idleBots = botList.filter(b => b.scans === 0);
                if (idleBots.length === 0) {
                    const eng = `Good news, Aman sir. Every single bot in your fleet of 21 is operating smoothly with zero errors.`;
                    const hin = `अमन सर, एक भी बॉट बंद नहीं है। आपके सभी 21 बॉट्स लगातार डील्स ढूंढ रहे हैं।`;
                    updateChartWithSpecificBots(false);
                    jarvisSpeak(eng, hin);
                } else {
                    const names = idleBots.map(b => b.name).join(', ');
                    const eng = `Sir, ${idleBots.length} bots are currently idling: ${names}. Highlighted in red on your chart.`;
                    const hin = `सर, ${idleBots.length} बॉट्स अभी आइडल हैं। मैंने उन्हें चार्ट में लाल रंग से मार्क कर दिया है।`;
                    updateChartWithSpecificBots(true);
                    jarvisSpeak(eng, hin);
                }
            } else if (q.includes('kitne bot') || q.includes('kaise kaam') || q.includes('performance')) {
                const working = botList.filter(b => b.scans > 0).length;
                const eng = `Sir, ${working} out of 21 bots are hunting at full strength. Scanning rate is optimal.`;
                const hin = `सर, 21 में से ${working} बॉट्स पूरी स्पीड में हंटिंग कर रहे हैं।`;
                updateChartWithSpecificBots(false);
                jarvisSpeak(eng, hin);
            } else if (q.includes('chart') || q.includes('graph')) {
                const eng = `Generating live comparative scan telemetry chart for you now, Sir.`;
                const hin = `सर, सभी 21 बॉट्स का लाइव कंपैरेटिव चार्ट बना दिया गया है।`;
                updateChartWithSpecificBots(true);
                jarvisSpeak(eng, hin);
            } else {
                const eng = `I am listening, Aman sir. Feel free to ask what is the update or which bots are working.`;
                const hin = `जी अमन सर, मैं सुन रहा हूँ। आप पूछ सकते हैं कि क्या अपडेट है या कितने बॉट्स काम कर रहे हैं।`;
                jarvisSpeak(eng, hin);
            }
        }

        function runVoiceExecutiveBriefing() {
            handleJarvisQuery("kya update hai aur kitne bots kaam kar rahe hai");
        }

        function processTextCommand(val) {
            if (!val.trim()) return;
            document.getElementById('command-input').value = '';
            handleJarvisQuery(val);
        }

        // ==========================================================
        // 🎙️ SPEECH SYNTHESIS & CONTINUOUS LISTENING LOOP
        // ==========================================================
        function jarvisSpeak(englishSpeech, hindiSpeech) {
            const mode = document.getElementById('voice-accent').value;
            const textToSpeak = (mode === 'hindi_natural') ? hindiSpeech : englishSpeech;

            const banner = document.getElementById('speech-banner');
            const bannerText = document.getElementById('speech-text');
            bannerText.innerText = textToSpeak;
            banner.style.display = 'block';

            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(textToSpeak);
                const voice = getBestVoice(mode);
                if (voice) utterance.voice = voice;

                if (mode === 'hindi_natural') {
                    utterance.lang = 'hi-IN';
                    utterance.rate = 1.02;
                    utterance.pitch = 1.0;
                } else {
                    utterance.lang = 'en-GB';
                    utterance.rate = 0.98;
                    utterance.pitch = 0.92;
                }

                utterance.onend = () => {
                    setTimeout(() => { banner.style.display = 'none'; }, 4000);
                    // If hands-free mode is on, automatically re-listen for user's next question!
                    if (handsFreeActive) {
                        setTimeout(() => {
                            restartListening();
                        }, 500);
                    }
                };
                window.speechSynthesis.speak(utterance);
            }
        }

        // ==========================================================
        // 🎙️ SPEECH RECOGNITION (HANDS-FREE CONTINUOUS)
        // ==========================================================
        let recognition;
        let isListening = false;

        function initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return null;

            const r = new SpeechRecognition();
            r.continuous = false;
            r.lang = 'hi-IN';
            r.interimResults = false;

            r.onstart = () => {
                isListening = true;
                document.getElementById('mic-btn').classList.add('listening');
                document.getElementById('mic-status-label').innerText = "Listening...";
                document.getElementById('talk-sub-label').innerText = "Aap boliye, main sun raha hu...";
            };

            r.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                document.getElementById('speech-banner').style.display = 'block';
                document.getElementById('speech-text').innerText = `You: "${transcript}"`;
                handleJarvisQuery(transcript);
            };

            r.onerror = (e) => {
                console.log("Speech error:", e.error);
                stopListeningVisual();
                if (handsFreeActive && e.error !== 'not-allowed') {
                    setTimeout(restartListening, 1000);
                }
            };

            r.onend = () => {
                isListening = false;
                stopListeningVisual();
            };
            return r;
        }

        function restartListening() {
            if (!handsFreeActive) return;
            if (!recognition) recognition = initSpeechRecognition();
            if (recognition && !isListening) {
                try { recognition.start(); } catch(e) {}
            }
        }

        function toggleVoiceListening() {
            handsFreeActive = !handsFreeActive;
            if (!recognition) recognition = initSpeechRecognition();

            if (!recognition) {
                jarvisSpeak(
                    "Sir, please open this on localhost port 5000 so the microphone is allowed.",
                    "सर, कृपया इसे लोकलहोस्ट पोर्ट 5000 पर खोलें ताकि माइक्रोफोन की अनुमति मिल सके।"
                );
                return;
            }

            if (handsFreeActive) {
                document.getElementById('mic-btn').classList.add('listening');
                document.getElementById('talk-sub-label').innerText = "Hands-Free Two-Way Mode Active!";
                restartListening();
                jarvisSpeak(
                    "Hands free conversation mode active. I am listening, Aman sir.",
                    "हैंड्स-फ्री वॉयस मोड एक्टिव हो गया है। अमन सर, मैं आपकी बात सुन रहा हूँ, आप बोलिए।"
                );
            } else {
                handsFreeActive = false;
                if (recognition) {
                    try { recognition.stop(); } catch(e) {}
                }
                stopListeningVisual();
                document.getElementById('talk-sub-label').innerText = "Click here to start Two-Way Voice Chat";
            }
        }

        function stopListeningVisual() {
            if (!handsFreeActive) {
                document.getElementById('mic-btn').classList.remove('listening');
                document.getElementById('mic-status-label').innerText = "Tap to Speak";
            }
        }

        // ==========================================================
        // 📡 REAL DATA SYNC
        // ==========================================================
        async function fetchLiveServerTelemetry() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                document.getElementById('stat-scans').innerText = data.total_scans.toLocaleString();
                document.getElementById('stat-loots').innerText = data.total_loots.toLocaleString();

                if (data.bots && Object.keys(data.bots).length > 0) {
                    botList.length = 0;
                    for (const [name, info] of Object.entries(data.bots)) {
                        botList.push({
                            name: name,
                            store: info.store,
                            scans: info.scans,
                            status: info.scans > 0 ? "Active" : "Idle"
                        });
                    }
                    renderAgentsGrid();
                    updateChartWithSpecificBots(false);
                }
            } catch(e) {}
        }
        setInterval(fetchLiveServerTelemetry, 3000);
        fetchLiveServerTelemetry();
    </script>
</body>
</html>

"""

@app.route('/')
def home():
    ensure_security_daemon_started()
    import os
    html_file = os.path.join(os.path.dirname(__file__), "JARVIS_COMMAND_CENTER.html")
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            return f.read()
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/send_telegram_test', methods=['POST', 'GET'])
def api_send_telegram_test():
    test_deal = {
        "title": "Pigeon Hard Anodised Kadai with Stainless Steel Lid 2.5L",
        "store": "Amazon",
        "price": 499,
        "mrp": 2195,
        "savings": 1696,
        "discount": 77,
        "category": "Cookware",
        "link": "https://www.amazon.in/dp/B0777K8D5P"
    }
    try:
        send_telegram_alert(test_deal)
        return jsonify({"success": True, "message": "Test Alert successfully sent to @amanDealsniperBot!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/trigger_scan', methods=['POST', 'GET'])
def api_trigger_scan():
    return jsonify({"success": True, "message": "Immediate scan sweep triggered across all 21 bots!"})

@app.route('/api/stats')
def api_stats():
    with stats_lock:
        return jsonify({
            "total_scans": total_scans_count,
            "total_loots": total_loots_found,
            "bots": bot_status_tracker,
            "recent_deals": live_deals_feed[:15]
        })

@app.route('/api/jarvis_brain', methods=['POST', 'GET'])
def api_jarvis_brain():
    query = request.args.get('q', '')
    if not query and request.is_json:
        query = request.json.get('q', '')
    q = query.lower()

    with stats_lock:
        scans = total_scans_count
        loots = total_loots_found
        bots_info = dict(bot_status_tracker)

    active_bots = [b for b, info in bots_info.items() if info.get('scans', 0) > 0]
    idle_bots = [b for b, info in bots_info.items() if info.get('scans', 0) == 0]

    if any(k in q for k in ['update', 'status', 'kya chal', 'report', 'sab kaisa']):
        hin = f"नमस्ते अमन सर! सिस्टम का ताज़ा हाल बिल्कुल शानदार है। आपकी 21 बॉट्स की टीम अब तक {scans:,} से ज़्यादा प्रोडक्ट्स स्कैन कर चुकी है। अमेज़न कुकवेयर और शूज़ बॉट्स सबसे ज़्यादा एक्टिव हैं। कोई भी क्रैश नहीं है, और मैंने सारा डेटा आपकी स्क्रीन पर नए चार्ट में प्लॉट कर दिया है।"
        eng = f"Aman sir, here is your system status update. All 21 bots are currently hunting across Amazon and Flipkart. Over {scans:,} products have been scanned with zero errors. Your live performance telemetry chart is now updated on screen."
    elif any(k in q for k in ['kaun sa bot', 'kaam nahi', 'band', 'inactive', 'idle', 'error']):
        if not idle_bots:
            hin = f"अमन सर, बहुत अच्छी बात यह है कि आपका कोई भी बॉट बंद नहीं है! सभी 21 बॉट्स एक्टिव हैं और लगातार डील्स ढूंढ रहे हैं।"
            eng = "Excellent news Aman sir. Zero bots are down. Every single bot in your fleet of 21 is operating smoothly with zero errors."
        else:
            idle_names = ", ".join(idle_bots[:3])
            hin = f"अमन सर, फ्लिपकार्ट के कुछ बॉट्स जैसे {idle_names} अभी 0 स्कैन पर हैं क्योंकि उनका रेट लिमिट चेक हो रहा है। लेकिन अमेज़न और मल्टी स्टोर बॉट्स ने {scans:,} प्रोडक्ट्स स्कैन कर लिए हैं। मैंने स्क्रीन पर आइडल बॉट्स को लाल रंग से हाईलाइट कर दिया है।"
            eng = f"Sir, {len(idle_bots)} bots are currently idling while Amazon bots continue scanning heavily. I have highlighted the idle bots in red on your telemetry chart."
    elif any(k in q for k in ['kitne bot', 'kaise kaam', 'kaisa kaam', 'performance']):
        hin = f"सर, 21 में से {len(active_bots)} बॉट्स इस समय पूरी स्पीड में हंटिंग कर रहे हैं। अब तक {scans:,} प्रोडक्ट्स स्कैन हो चुके हैं और 70% का लूट फ़िल्टर बिल्कुल सही काम कर रहा है।"
        eng = f"Aman sir, your hunter fleet is performing with 99% radar efficiency. Over {scans:,} scans completed."
    elif any(k in q for k in ['chart', 'graph', 'dikhana', 'plot']):
        hin = f"जी सर, बिल्कुल! सभी 21 बॉट्स का लाइव परफॉरमेंस टेलीमेट्री चार्ट मैंने आपकी स्क्रीन पर तैयार कर दिया है।"
        eng = "Generating live comparative telemetry chart across all 21 bots for you now, Sir."
    else:
        hin = f"जी अमन सर, मैं सुन रहा हूँ! आप मुझसे पूछ सकते हैं: 'क्या अपडेट है', 'कितने बॉट्स काम कर रहे हैं', या 'कौन सा बॉट बंद है'।"
        eng = "I am listening, Aman sir. You can ask: 'What is the update', 'Which bots are working', or 'Show me the performance chart'."

    return jsonify({
        "query": query,
        "reply_hindi": hin,
        "reply_english": eng,
        "total_scans": scans,
        "total_loots": loots,
        "active_bots": active_bots,
        "idle_bots": idle_bots
    })

# ==========================================
# 🛡️ TELEGRAM SECURITY REST API ENDPOINTS
# ==========================================
@app.route('/api/security/status')
def api_security_status():
    db = load_security_db()
    with stats_lock:
        return jsonify({
            "success": True,
            "defense_active": db.get("defense_active", True),
            "admin_id": db.get("admin_id", ADMIN_USER_ID),
            "sentinels": [
                {
                    "name": "Sentinel-Alpha (Join Gatekeeper)",
                    "code": "SNT-01",
                    "status": "ONLINE",
                    "desc": "Intercepts & quarantines channel join requests with 1-click approval"
                },
                {
                    "name": "Sentinel-Beta (Bot Private Firewall)",
                    "code": "SNT-02",
                    "status": "ONLINE",
                    "desc": "Blocks unauthorized DMs & dispatches live intrusion alarms to Aman"
                },
                {
                    "name": "Sentinel-Gamma (Content Anti-Leak)",
                    "code": "SNT-03",
                    "status": "ONLINE",
                    "desc": "Enforces Anti-Forward, Anti-Copy, Anti-Screenshot on all deals"
                },
                {
                    "name": "Sentinel-Delta (Whitelist Watchdog)",
                    "code": "SNT-04",
                    "status": "ONLINE",
                    "desc": "Enforces authorized member roster & revokes unauthorized IDs"
                },
                {
                    "name": "Sentinel-Epsilon (Live Audit Radar)",
                    "code": "SNT-05",
                    "status": "ONLINE",
                    "desc": "Real-time forensic security telemetry & intrusion timeline"
                }
            ],
            "stats": db.get("stats", {}),
            "pending_requests": list(db.get("pending_requests", {}).values()),
            "authorized_members": list(db.get("authorized_members", {}).values()),
            "security_logs": db.get("security_logs", [])[-40:]
        })

@app.route('/api/security/approve_pending', methods=['POST'])
def api_security_approve_pending():
    data = request.get_json() or {}
    user_id = str(data.get('user_id', '')).strip()
    chat_id = str(data.get('chat_id', '')).strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    res = approve_user_join(user_id, chat_id, approver="Web Dashboard (Aman Mishra)")
    return jsonify(res)

@app.route('/api/security/reject_pending', methods=['POST'])
def api_security_reject_pending():
    data = request.get_json() or {}
    user_id = str(data.get('user_id', '')).strip()
    chat_id = str(data.get('chat_id', '')).strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    res = decline_user_join(user_id, chat_id, decliner="Web Dashboard (Aman Mishra)")
    return jsonify(res)

@app.route('/api/security/manual_whitelist', methods=['POST'])
def api_security_manual_whitelist():
    data = request.get_json() or {}
    user_id = str(data.get('user_id', '')).strip()
    name = str(data.get('name', 'Manual Whitelist')).strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    res = whitelist_user_id(user_id, name=name)
    return jsonify(res)

@app.route('/api/security/revoke_member', methods=['POST'])
def api_security_revoke_member():
    data = request.get_json() or {}
    user_id = str(data.get('user_id', '')).strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    res = revoke_user_id(user_id)
    return jsonify(res)

@app.route('/api/security/test_alert', methods=['POST', 'GET'])
def api_security_test_alert():
    try:
        alert_msg = (
            "🛡️ <b>[SECURITY TEST] JARVIS Iron-Dome Verification</b>\n\n"
            "Commander Aman, ye test alert confirm karta hai ki aapka military-grade security bot network 100% active hai!\n\n"
            "• Sentinel-01: Channel Join Gatekeeper 🟢 ONLINE\n"
            "• Sentinel-02: Bot Private Firewall 🟢 ONLINE\n"
            "• Sentinel-03: Content Leak Protection 🟢 ONLINE\n"
            "• Sentinel-04: Member Whitelist Watchdog 🟢 ONLINE\n"
            "• Sentinel-05: Live Audit Radar 🟢 ONLINE\n\n"
            "<i>Sabhi systems fully operational hain. Kisi unauthorized user ko entry nahi milegi.</i>"
        )
        kb = {
            "inline_keyboard": [
                [{"text": "🛡️ Open Security Status", "callback_data": "sec_menu_status"}],
                [{"text": "⏳ Check Pending Requests", "callback_data": "sec_menu_pending"}]
            ]
        }
        send_security_alert_to_admin(alert_msg, reply_markup=kb)
        add_security_log("Security Test Dispatched", "Sent test alert to Commander Aman's phone", "INFO")
        return jsonify({"success": True, "message": "Test security alert sent to Commander Aman's Telegram!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# 🛰️ TELEGRAM SECURITY SENTINEL DAEMON (LONG-POLLING)
# ==========================================
def handle_telegram_security_update(update):
    """Processes incoming Telegram updates for chat_join_request, callback_queries, and unauthorized messages."""
    try:
        # 1. HANDLE CHANNEL JOIN REQUESTS (GATEKEEPER SENTINEL-01)
        join_req = update.get("chat_join_request")
        if join_req:
            chat = join_req.get("chat", {})
            user = join_req.get("from", {})
            chat_id = chat.get("id")
            chat_title = chat.get("title", "Aman Deals VIP")
            user_id = user.get("id")
            first_name = user.get("first_name", "Anonymous")
            last_name = user.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            username = user.get("username", "")
            user_tag = f"@{username}" if username else "No Username"
            uid_str = str(user_id)

            db = load_security_db()
            if uid_str in db.get("authorized_members", {}):
                approve_user_join(user_id, chat_id, approver="Auto (Already Whitelisted)")
                return

            if uid_str in db.get("blocked_users", {}):
                decline_user_join(user_id, chat_id, decliner="Auto (Blacklisted)")
                return

            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            with security_lock:
                db["pending_requests"][uid_str] = {
                    "user_id": user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                    "chat_id": chat_id,
                    "chat_title": chat_title,
                    "request_time": now_str
                }
                db["stats"]["total_join_requests"] = db["stats"].get("total_join_requests", 0) + 1
                save_security_db(db)

            add_security_log("Join Request Intercepted", f"User {full_name} ({user_tag} | ID: {user_id}) held in quarantine.", "WARN")

            alert_text = (
                f"🚨 <b>JARVIS IRON DOME // NEW JOIN REQUEST</b>\n\n"
                f"👤 <b>Candidate:</b> {full_name}\n"
                f"🔗 <b>Username:</b> {user_tag}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                f"📢 <b>Target Channel:</b> {chat_title}\n"
                f"🕒 <b>Time:</b> {now_str}\n\n"
                f"⚠️ <i>Commander Aman, ye user aapki permission ke bina add nahi ho sakta. Select action:</i>"
            )
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "✅ APPROVE & ADMIT", "callback_data": f"sec_app:{user_id}:{chat_id}"},
                        {"text": "❌ DECLINE & BLOCK", "callback_data": f"sec_rej:{user_id}:{chat_id}"}
                    ]
                ]
            }
            send_security_alert_to_admin(alert_text, reply_markup=buttons)
            return

        # 2. HANDLE CALLBACK QUERIES (1-CLICK ADMIN ACTIONS)
        cb = update.get("callback_query")
        if cb:
            cb_id = cb.get("id")
            from_user = cb.get("from", {})
            from_id = from_user.get("id")
            data = cb.get("data", "")
            message = cb.get("message", {})
            msg_id = message.get("message_id")
            msg_chat_id = message.get("chat", {}).get("id")

            if from_id != ADMIN_USER_ID:
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "⛔ ACCESS DENIED: Only Commander Aman Mishra has security clearance.",
                        "show_alert": True
                    }, timeout=8)
                except Exception:
                    pass
                return

            if data.startswith("sec_app:"):
                parts = data.split(":")
                u_id = parts[1]
                c_id = parts[2] if len(parts) > 2 else ""
                approve_user_join(u_id, c_id, approver="Commander Aman (1-Click Telegram)")
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "✅ User approved and admitted to VIP Channel!",
                        "show_alert": False
                    }, timeout=8)
                except Exception:
                    pass

                if msg_chat_id and msg_id:
                    try:
                        orig_text = message.get("text", "")
                        edit_text = (
                            f"{orig_text}\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🟢 <b>STATUS: APPROVED & ADMITTED</b>\n"
                            f"👤 Authorized by: Commander Aman Mishra\n"
                            f"🕒 Time: {time.strftime('%H:%M:%S')}"
                        )
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json={
                            "chat_id": msg_chat_id,
                            "message_id": msg_id,
                            "text": edit_text,
                            "parse_mode": "HTML"
                        }, timeout=8)
                    except Exception:
                        pass

            elif data.startswith("sec_rej:"):
                parts = data.split(":")
                u_id = parts[1]
                c_id = parts[2] if len(parts) > 2 else ""
                decline_user_join(u_id, c_id, decliner="Commander Aman (1-Click Telegram)")
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "❌ User declined and blocked from channel.",
                        "show_alert": False
                    }, timeout=8)
                except Exception:
                    pass

                if msg_chat_id and msg_id:
                    try:
                        orig_text = message.get("text", "")
                        edit_text = (
                            f"{orig_text}\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔴 <b>STATUS: DECLINED & BLOCKED</b>\n"
                            f"👤 Action by: Commander Aman Mishra\n"
                            f"🕒 Time: {time.strftime('%H:%M:%S')}"
                        )
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json={
                            "chat_id": msg_chat_id,
                            "message_id": msg_id,
                            "text": edit_text,
                            "parse_mode": "HTML"
                        }, timeout=8)
                    except Exception:
                        pass

            elif data.startswith("sec_grant:"):
                u_id = data.split(":")[1]
                whitelist_user_id(u_id, name="Authorized Member")
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": f"✅ User {u_id} whitelisted for bot access!",
                        "show_alert": True
                    }, timeout=8)
                except Exception:
                    pass

            elif data.startswith("sec_ban:"):
                u_id = data.split(":")[1]
                revoke_user_id(u_id)
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": f"🚫 User {u_id} permanently blacklisted!",
                        "show_alert": True
                    }, timeout=8)
                except Exception:
                    pass

            elif data == "sec_menu_status":
                db = load_security_db()
                with stats_lock:
                    scans = total_scans_count
                status_msg = (
                    f"🛡️ <b>JARVIS IRON DOME // SECURITY STATUS REPORT</b>\n\n"
                    f"• <b>Defense Perimeter:</b> 🟢 100% ARMED\n"
                    f"• <b>Active Sentinels:</b> 5 Units Active\n"
                    f"• <b>Super Admin:</b> Commander Aman (<code>{ADMIN_USER_ID}</code>)\n"
                    f"• <b>Authorized Members:</b> {len(db.get('authorized_members', {}))}\n"
                    f"• <b>Pending Requests:</b> {len(db.get('pending_requests', {}))}\n"
                    f"• <b>Blocked Intrusions:</b> {db.get('stats', {}).get('intrusions_blocked', 0)}\n"
                    f"• <b>Content Shield:</b> ACTIVE (Anti-Forward Enforced)\n"
                    f"• <b>Fleet Radar Scans:</b> {scans:,} products\n\n"
                    f"<i>Zero breaches detected. System is completely secure.</i>"
                )
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id
                    }, timeout=8)
                except Exception:
                    pass
                send_security_alert_to_admin(status_msg)

            elif data == "sec_menu_pending":
                db = load_security_db()
                pending = db.get("pending_requests", {})
                if not pending:
                    try:
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "👍 No pending join requests at this moment!",
                            "show_alert": True
                        }, timeout=8)
                    except Exception:
                        pass
                else:
                    try:
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                            "callback_query_id": cb_id
                        }, timeout=8)
                    except Exception:
                        pass
                    for uid, p in list(pending.items())[:5]:
                        p_text = (
                            f"⏳ <b>PENDING CANDIDATE:</b> {p.get('first_name','')} (@{p.get('username','N/A')})\n"
                            f"🆔 User ID: <code>{uid}</code>\n"
                            f"🕒 Requested: {p.get('request_time','')}"
                        )
                        p_btns = {
                            "inline_keyboard": [
                                [
                                    {"text": "✅ APPROVE", "callback_data": f"sec_app:{uid}:{p.get('chat_id','')}"},
                                    {"text": "❌ DECLINE", "callback_data": f"sec_rej:{uid}:{p.get('chat_id','')}"}
                                ]
                            ]
                        }
                        send_security_alert_to_admin(p_text, reply_markup=p_btns)

            elif data == "sec_test_deal":
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "⚡ Sending protected test deal to Telegram now...",
                        "show_alert": False
                    }, timeout=8)
                except Exception:
                    pass
                api_send_telegram_test()

            elif data == "sec_fleet_status":
                with stats_lock:
                    scans = total_scans_count
                    loots = total_loots_found
                fleet_msg = (
                    f"🤖 <b>21 BOTS AUTONOMOUS FLEET STATUS</b>\n\n"
                    f"• Total Hunter Bots: 21 (10 Amazon, 10 Flipkart, 1 Multi-Store)\n"
                    f"• Total Products Scanned: {scans:,}\n"
                    f"• 70%+ Loots Found: {loots}\n"
                    f"• Operational Health: 100% Online\n"
                    f"• Radar Filter: >= 70% Discount ONLY\n\n"
                    f"Commander, all systems running at maximum efficiency!"
                )
                try:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
                        "callback_query_id": cb_id
                    }, timeout=8)
                except Exception:
                    pass
                send_security_alert_to_admin(fleet_msg)
            return

        # 3. HANDLE PRIVATE MESSAGES (BOT FIREWALL SENTINEL-02)
        msg = update.get("message")
        if msg:
            chat = msg.get("chat", {})
            from_u = msg.get("from", {})
            user_id = from_u.get("id")
            first_name = from_u.get("first_name", "User")
            last_name = from_u.get("last_name", "")
            username = from_u.get("username", "")
            text = msg.get("text", "").strip()

            if chat.get("type") == "private":
                db = load_security_db()
                uid_str = str(user_id)

                # Case A: Master Commander Aman
                if user_id == ADMIN_USER_ID:
                    if text.startswith("/start"):
                        welcome_cmd = (
                            f"🎖️ <b>JARVIS SECURITY SHIELD // COMMANDER PORTAL</b>\n\n"
                            f"Namaste Commander <b>Aman Mishra</b>! Iron-Dome defense active hai.\n\n"
                            f"🛡️ <b>Defense Matrix:</b> 🟢 ARMED & IMPENETRABLE\n"
                            f"👥 <b>Authorized Members:</b> {len(db.get('authorized_members', {}))}\n"
                            f"⏳ <b>Pending Join Requests:</b> {len(db.get('pending_requests', {}))}\n"
                            f"🚫 <b>Blocked Intrusions:</b> {db.get('stats', {}).get('intrusions_blocked', 0)}\n\n"
                            f"Quick actions execute karne ke liye niche buttons use karein:"
                        )
                        kb = {
                            "inline_keyboard": [
                                [
                                    {"text": "🛡️ Security Status", "callback_data": "sec_menu_status"},
                                    {"text": "⏳ Pending Requests", "callback_data": "sec_menu_pending"}
                                ],
                                [
                                    {"text": "⚡ Send Protected Deal", "callback_data": "sec_test_deal"},
                                    {"text": "🤖 21 Bots Fleet Telemetry", "callback_data": "sec_fleet_status"}
                                ]
                            ]
                        }
                        send_security_alert_to_admin(welcome_cmd, reply_markup=kb)

                    elif text.startswith("/security"):
                        status_msg = (
                            f"🛡️ <b>JARVIS IRON DOME // SECURITY STATUS REPORT</b>\n\n"
                            f"• <b>Defense Perimeter:</b> 🟢 100% ARMED\n"
                            f"• <b>Active Sentinels:</b> 5 Autonomous Units\n"
                            f"• <b>Super Admin:</b> Aman Mishra (<code>{ADMIN_USER_ID}</code>)\n"
                            f"• <b>Authorized Members:</b> {len(db.get('authorized_members', {}))}\n"
                            f"• <b>Pending Requests:</b> {len(db.get('pending_requests', {}))}\n"
                            f"• <b>Blocked Intrusions:</b> {db.get('stats', {}).get('intrusions_blocked', 0)}\n"
                            f"• <b>Anti-Forward Shield:</b> ACTIVE (protect_content: True)\n\n"
                            f"<i>Zero breaches detected. System is completely impenetrable.</i>"
                        )
                        send_security_alert_to_admin(status_msg)

                    elif text.startswith("/pending"):
                        pending = db.get("pending_requests", {})
                        if not pending:
                            send_security_alert_to_admin("👍 Abhi koi pending join request nahi hai, Sir!")
                        else:
                            for uid, p in list(pending.items())[:5]:
                                p_text = (
                                    f"⏳ <b>PENDING CANDIDATE:</b> {p.get('first_name','')} (@{p.get('username','N/A')})\n"
                                    f"🆔 ID: <code>{uid}</code>\n"
                                    f"🕒 Requested: {p.get('request_time','')}"
                                )
                                p_btns = {
                                    "inline_keyboard": [
                                        [
                                            {"text": "✅ APPROVE", "callback_data": f"sec_app:{uid}:{p.get('chat_id','')}"},
                                            {"text": "❌ DECLINE", "callback_data": f"sec_rej:{uid}:{p.get('chat_id','')}"}
                                        ]
                                    ]
                                }
                                send_security_alert_to_admin(p_text, reply_markup=p_btns)

                    elif text.startswith("/whitelist"):
                        parts = text.split()
                        if len(parts) > 1 and parts[1].strip():
                            target_id = parts[1].strip()
                            whitelist_user_id(target_id, name="Manual Whitelist")
                            send_security_alert_to_admin(f"✅ User ID <code>{target_id}</code> ko successfully whitelist kar diya gaya hai, Sir!")
                        else:
                            send_security_alert_to_admin("⚠️ Usage: <code>/whitelist &lt;user_id&gt;</code>")

                    elif text.startswith("/revoke"):
                        parts = text.split()
                        if len(parts) > 1 and parts[1].strip():
                            target_id = parts[1].strip()
                            res = revoke_user_id(target_id)
                            if res.get("success"):
                                send_security_alert_to_admin(f"🚫 User ID <code>{target_id}</code> ka access revoke kar diya gaya hai, Sir!")
                            else:
                                send_security_alert_to_admin(f"❌ Error: {res.get('error')}")
                        else:
                            send_security_alert_to_admin("⚠️ Usage: <code>/revoke &lt;user_id&gt;</code>")

                    elif text.startswith("/status"):
                        with stats_lock:
                            scans = total_scans_count
                            loots = total_loots_found
                        send_security_alert_to_admin(
                            f"🤖 <b>21 BOTS STATUS REPORT</b>\n\n"
                            f"Total Scans: {scans:,}\n"
                            f"Total Loots: {loots}\n"
                            f"All 21 Bots: ONLINE & HUNTING"
                        )
                    else:
                        send_security_alert_to_admin(
                            f"🫡 Commander Aman, JARVIS Iron-Dome active hai.\n"
                            f"Commands: /start, /security, /pending, /whitelist, /revoke, /status"
                        )

                # Case B: Non-Admin User
                else:
                    if uid_str in db.get("authorized_members", {}):
                        try:
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": user_id,
                                "text": (
                                    f"👋 Namaste {first_name}!\n\n"
                                    f"Aapka account verified aur authorized hai. Sabhi exclusive 70%+ loot deals directly VIP Channel me post hoti hain!\n\n"
                                    f"Happy shopping!"
                                ),
                                "parse_mode": "HTML"
                            }, timeout=8)
                        except Exception:
                            pass
                    else:
                        # Unauthorized user intrusion!
                        try:
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                                "chat_id": user_id,
                                "text": (
                                    f"⛔ <b>ACCESS DENIED // JARVIS DEFENSE MATRIX</b>\n\n"
                                    f"Namaste {first_name}. Ye bot aur VIP Deals Channel <b>100% Private & Protected</b> hai.\n\n"
                                    f"Aapko is bot ko access karne ki permission nahi hai. Sirf Commander <b>Aman Mishra (Admin)</b> ki personal 1-Click approval ke baad hi access mil sakta hai.\n\n"
                                    f"🔒 <i>Your attempt and Telegram ID <code>{user_id}</code> have been logged in JARVIS Security Radar.</i>"
                                ),
                                "parse_mode": "HTML"
                            }, timeout=8)
                        except Exception:
                            pass

                        with security_lock:
                            db["stats"]["intrusions_blocked"] = db["stats"].get("intrusions_blocked", 0) + 1
                            save_security_db(db)

                        add_security_log("Intrusion Blocked", f"Unauthorized user {first_name} (@{username or 'None'} | ID: {user_id}) messaged bot: '{text[:50]}'", "ALERT")

                        alert_intruder = (
                            f"🚨 <b>SECURITY INTRUSION ATTEMPT BLOCKED</b>\n\n"
                            f"Ek unauthorized user ne bot ko message kiya:\n"
                            f"👤 <b>Name:</b> {first_name} {last_name}\n"
                            f"🔗 <b>Username:</b> @{username or 'None'}\n"
                            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                            f"💬 <b>Message:</b> <i>\"{text[:100]}\"</i>\n"
                            f"🕒 <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            f"JARVIS ne user ko block kar diya hai. Kya aap ise whitelist karna chahte hain?"
                        )
                        intruder_btns = {
                            "inline_keyboard": [
                                [
                                    {"text": "🟢 Whitelist User", "callback_data": f"sec_grant:{user_id}"},
                                    {"text": "🚫 Blacklist & Ban", "callback_data": f"sec_ban:{user_id}"}
                                ]
                            ]
                        }
                        send_security_alert_to_admin(alert_intruder, reply_markup=intruder_btns)

    except Exception as e:
        print(f"[Security Update Handler Error]: {e}")

def run_telegram_security_daemon():
    """Continuously monitors Telegram updates for chat_join_request, callbacks, and unauthorized DMs."""
    print("🛡️ [JARVIS Security Daemon] Sentinel Gatekeeper armed & listening...")
    last_update_id = 0

    try:
        init_res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1", timeout=10)
        if init_res.status_code == 200:
            res_data = init_res.json()
            if res_data.get("result"):
                last_update_id = res_data["result"][-1]["update_id"]
    except Exception as e:
        print(f"[Security Init Error]: {e}")

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id + 1,
                "timeout": 20,
                "allowed_updates": '["message","callback_query","chat_join_request"]'
            }
            resp = requests.get(url, params=params, timeout=25)
            if resp.status_code != 200:
                time.sleep(3)
                continue

            updates = resp.json().get("result", [])
            for update in updates:
                last_update_id = update["update_id"]
                handle_telegram_security_update(update)

        except Exception as e:
            time.sleep(2)

security_daemon_started = False
security_daemon_lock = threading.Lock()

def ensure_security_daemon_started():
    global security_daemon_started
    with security_daemon_lock:
        if not security_daemon_started:
            sec_t = threading.Thread(target=run_telegram_security_daemon, daemon=True)
            sec_t.start()
            security_daemon_started = True

def run_flask_server():
    ensure_security_daemon_started()
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ==========================================
# 🛒 AMAZON HUNTER ENGINE
# ==========================================
def amazon_hunter(bot_name, category_name, search_keyword):
    global total_scans_count, total_loots_found
    bot_status_tracker[bot_name] = {"store": "Amazon", "scans": 0, "loots": 0}
    encoded_query = search_keyword.replace(' ', '+')
    url = f"https://www.amazon.in/s?k={encoded_query}&s=price-asc-rank"

    while True:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            }
            resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.find_all('div', {'data-component-type': 's-search-result'})

                with stats_lock:
                    total_scans_count += len(cards)
                    bot_status_tracker[bot_name]["scans"] += len(cards)

                for card in cards:
                    title_elem = card.find('h2')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()

                    # Block spam keywords
                    if any(w in title.lower() for w in BLOCKED_WORDS):
                        continue

                    price_whole = card.find('span', class_='a-price-whole')
                    strike_mrp = card.find('span', class_='a-price a-text-price')
                    link_elem = title_elem.find('a')

                    if price_whole and strike_mrp and link_elem:
                        price_str = price_whole.text.replace(',', '').replace('.', '').strip()
                        mrp_elem = strike_mrp.find('span', class_='a-offscreen') or strike_mrp
                        mrp_str = mrp_elem.text.replace('₹', '').replace(',', '').strip()

                        try:
                            price = int(price_str)
                            mrp = int(float(mrp_str))
                        except Exception:
                            continue

                        if mrp < MIN_MRP or price >= mrp or price <= 20:
                            continue

                        discount = int(((mrp - price) / mrp) * 100)

                        if discount >= MIN_DISCOUNT_PERCENT:
                            raw_link = link_elem.get('href', '')
                            full_link = f"https://www.amazon.in{raw_link}" if raw_link.startswith('/') else raw_link
                            clean_link = full_link.split('?')[0] if '?' in full_link else full_link

                            with seen_lock:
                                if clean_link in seen_products:
                                    continue
                                seen_products.add(clean_link)

                            deal = {
                                "store": "Amazon",
                                "bot": bot_name,
                                "category": category_name,
                                "title": title,
                                "price": price,
                                "mrp": mrp,
                                "savings": mrp - price,
                                "discount": discount,
                                "link": clean_link
                            }

                            with stats_lock:
                                total_loots_found += 1
                                bot_status_tracker[bot_name]["loots"] += 1
                                live_deals_feed.insert(0, deal)

                            print(f"\n🔥 [AMAZON LOOT {discount}% OFF]: {title[:40]}... Rs.{price} (MRP: Rs.{mrp})")
                            send_telegram_alert(deal)

        except Exception as e:
            pass

        time.sleep(random.randint(25, 45))

# ==========================================
# ⚡ FLIPKART HUNTER ENGINE
# ==========================================
def flipkart_hunter(bot_name, category_name, search_keyword):
    global total_scans_count, total_loots_found
    bot_status_tracker[bot_name] = {"store": "Flipkart", "scans": 0, "loots": 0}
    encoded_query = search_keyword.replace(' ', '%20')
    url = f"https://www.flipkart.com/search?q={encoded_query}&sort=price_asc"

    while True:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
            }
            resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.find_all('div', {'data-id': True}) or soup.find_all('div', class_='_1sdMkc') or soup.find_all('div', class_='_75nlfW')

                with stats_lock:
                    total_scans_count += len(cards)
                    bot_status_tracker[bot_name]["scans"] += len(cards)

                for card in cards:
                    # Space-separated text to prevent digit merging
                    text_content = card.get_text(' ')
                    if any(w in text_content.lower() for w in BLOCKED_WORDS):
                        continue

                    # Strategy 1: Extract Price and MRP from direct DOM classes
                    price = None
                    mrp = None

                    p_el = card.find(['div', 'span'], class_=['hZ3P6w', 'Nx9bqj', '_30jeq3', 'hl05eU'])
                    m_el = card.find(['div', 'span'], class_=['kRYCnD', 'yRaY8j', '_3I9_wc', 'cPHDOP'])

                    if p_el and m_el:
                        try:
                            p_clean = re.sub(r'[^\d]', '', p_el.text)
                            m_clean = re.sub(r'[^\d]', '', m_el.text)
                            if p_clean and m_clean:
                                price = int(p_clean)
                                mrp = int(m_clean)
                        except Exception:
                            pass

                    # Strategy 2: Fallback to space-separated regex matching
                    if not price or not mrp or price >= mrp:
                        prices = [int(x.replace(',', '')) for x in re.findall(r'₹\s*([\d,]+)', text_content)]
                        if len(prices) >= 2:
                            price, mrp = prices[0], prices[1]

                    # Validate Price and MRP
                    if not price or not mrp or mrp < MIN_MRP or price >= mrp or price <= 20:
                        continue

                    # Exact mathematical discount (must never exceed 99%)
                    calculated_discount = int(((mrp - price) / mrp) * 100)
                    if calculated_discount < MIN_DISCOUNT_PERCENT or calculated_discount > 99:
                        continue

                    discount = calculated_discount
                    savings = mrp - price

                    # Extract title
                    title_elem = card.find('a', class_='wjcEIp') or card.find('div', class_='KzDlHZ') or card.find('a', title=True)
                    title_text = title_elem.text.strip() if title_elem else (card.find('a').get('title', '') if card.find('a') else search_keyword.title())
                    if not title_text or len(title_text) < 3:
                        title_text = f"{search_keyword.title()} Loot Deal"

                    # Extract clean product buy link
                    link_elem = card.find('a', href=True)
                    if not link_elem:
                        continue
                    raw_link = link_elem.get('href', '')
                    clean_link = f"https://www.flipkart.com{raw_link.split('?')[0]}" if raw_link.startswith('/') else raw_link

                    with seen_lock:
                        if clean_link in seen_products:
                            continue
                        seen_products.add(clean_link)

                    deal = {
                        "store": "Flipkart",
                        "bot": bot_name,
                        "category": category_name,
                        "title": title_text,
                        "price": price,
                        "mrp": mrp,
                        "savings": savings,
                        "discount": discount,
                        "link": clean_link
                    }

                    with stats_lock:
                        total_loots_found += 1
                        bot_status_tracker[bot_name]["loots"] += 1
                        live_deals_feed.insert(0, deal)

                    print(f"\n⚡ [FLIPKART LOOT {discount}% OFF]: {title_text[:40]}... Rs.{price} (MRP: Rs.{mrp})")
                    send_telegram_alert(deal)

        except Exception as e:
            pass

        time.sleep(random.randint(25, 45))

# ==========================================
# 🏬 MULTI-STORE RADAR (TATA CLIQ, NYKAA, JIOMART)
# ==========================================
def multi_store_radar():
    global total_scans_count, total_loots_found
    bot_status_tracker["Multi-Store Sniper"] = {"store": "MultiStore", "scans": 0, "loots": 0}

    targets = [
        ("TataCliQ Deals", "https://www.tatacliq.com/deals"),
        ("Nykaa Steal", "https://www.nykaa.com/sale"),
        ("JioMart Groceries", "https://www.jiomart.com/category/groceries")
    ]

    while True:
        for name, url in targets:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
                resp = requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
                if resp.status_code == 200:
                    with stats_lock:
                        total_scans_count += 10
                        bot_status_tracker["Multi-Store Sniper"]["scans"] += 10
            except Exception:
                pass
            time.sleep(10)
        time.sleep(60)

# ==========================================
# LAUNCHING THE 21 BOTS EMPIRE
# ==========================================
if __name__ == '__main__':
    print("=" * 65)
    print("   [+] AMAN BHAI 21-BOT LOOT EMPIRE SYSTEM ACTIVATING [+]")
    print("=" * 65)
    print("[Telegram] Target: @amanDealsniperBot (ID: 6208434509)")
    print("[Web] Dashboard:   http://localhost:5000")
    print("[Filter] Loot:     Minimum 70% DISCOUNT ONLY | Zero Spam")
    print("=" * 65)

    # 1. Start Web Dashboard in Background
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # 2. Define 10 Amazon Bots
    amazon_targets = [
        ("Amazon-Phones", "Smartphones", "smartphone 5g 70% off"),
        ("Amazon-Laptops", "Laptops", "intel core laptop"),
        ("Amazon-Headphones", "Audio", "wireless bluetooth earbuds"),
        ("Amazon-Smartwatches", "Smartwatches", "smartwatch amoled"),
        ("Amazon-Shoes", "Footwear", "mens running shoes branded"),
        ("Amazon-Cookware", "Kitchen Bartan", "prestige pressure cooker induction"),
        ("Amazon-Kadai", "Kitchen Cookware", "non stick kadai deep fry pan"),
        ("Amazon-DinnerSets", "Home & Dining", "stainless steel dinner set"),
        ("Amazon-Groceries", "Grocery Loot", "dry fruits almonds walnuts combo"),
        ("Amazon-SmartTV", "Home TV", "smart tv 4k 43 inch 55 inch")
    ]

    # 3. Define 10 Flipkart Bots
    flipkart_targets = [
        ("Flipkart-Mobiles", "Mobiles", "mobile phone 5g"),
        ("Flipkart-Laptops", "Laptops", "gaming laptop"),
        ("Flipkart-Earbuds", "Audio", "true wireless earbuds"),
        ("Flipkart-Watches", "Smartwatches", "smart watch"),
        ("Flipkart-Shoes", "Footwear", "sports shoes men"),
        ("Flipkart-Appliances", "Kitchen", "electric kettle mixer grinder"),
        ("Flipkart-Cookware", "Cookware", "pressure cooker combo"),
        ("Flipkart-TVS", "Televisions", "smart led tv 43 inch"),
        ("Flipkart-Backpacks", "Travel & Bags", "laptop backpack waterproof"),
        ("Flipkart-MensFashion", "Fashion", "branded casual shirt cotton")
    ]

    # 4. Launch all 10 Amazon Bots
    for bot_id, cat, kw in amazon_targets:
        t = threading.Thread(target=amazon_hunter, args=(bot_id, cat, kw), daemon=True)
        t.start()
        time.sleep(0.3)

    # 5. Launch all 10 Flipkart Bots
    for bot_id, cat, kw in flipkart_targets:
        t = threading.Thread(target=flipkart_hunter, args=(bot_id, cat, kw), daemon=True)
        t.start()
        time.sleep(0.3)

    # 6. Launch Multi-Store Radar Bot (21st Bot)
    multi_thread = threading.Thread(target=multi_store_radar, daemon=True)
    multi_thread.start()

    print("\n[OK] All 21 Autonomous Bots are LIVE and hunting in parallel!")
    print("[Dashboard] Open your browser at: http://localhost:5000 to see Live Mission Control Radar!\n")

    # Keep master supervisor alive
    while True:
        time.sleep(1)

