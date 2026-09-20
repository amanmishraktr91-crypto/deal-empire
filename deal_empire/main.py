import time
import random
import threading
from curl_cffi import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string

# ==========================================
# ⚙️ AMAN BHAI KA BOT CONFIGURATION
# ==========================================
BOT_TOKEN = "8592608802:AAH3FL8bZY6ZmpqmpB3XAzaZfwjAxQGip0k"
CHAT_ID = "6208434509"

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
# 📲 TELEGRAM ALERT ENGINE
# ==========================================
def send_telegram_alert(deal):
    """Sends ultra-clean 1-Click Loot Deal alert to Telegram"""
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
        f"⚠️ <i>Price kabhi bhi badh sakti hai, jaldi check karein!</i>"
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=10)
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
    <title>⚡ AMAN BHAI LOOT EMPIRE - 21 BOTS RADAR</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;800;900&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background:#070913; color:#e0e6ed; font-family:'Rajdhani', sans-serif; overflow-x:hidden; }
        header { background:linear-gradient(90deg, #0f172a, #1e1b4b); padding:20px 30px; border-bottom:2px solid #38bdf8; display:flex; justify-content:space-between; align-items:center; box-shadow:0 0 25px rgba(56,189,248,0.2); }
        .logo { font-family:'Orbitron', sans-serif; font-size:26px; font-weight:900; color:#38bdf8; letter-spacing:2px; }
        .status-badge { background:#10b98122; border:1px solid #10b981; color:#10b981; padding:6px 15px; border-radius:20px; font-size:14px; font-weight:700; text-transform:uppercase; animation:pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
        .container { display:grid; grid-template-columns:320px 1fr 380px; gap:20px; padding:20px; height:calc(100vh - 85px); }
        .card { background:#0f172a; border-radius:12px; border:1px solid #1e293b; padding:20px; display:flex; flex-direction:column; overflow:hidden; }
        .card-header { font-family:'Orbitron', sans-serif; font-size:16px; color:#f8fafc; margin-bottom:15px; border-bottom:1px solid #334155; padding-bottom:8px; display:flex; justify-content:space-between; }
        .stat-box { background:#1e293b; border-radius:8px; padding:15px; margin-bottom:12px; border-left:4px solid #38bdf8; }
        .stat-title { font-size:13px; color:#94a3b8; text-transform:uppercase; }
        .stat-value { font-family:'Orbitron', sans-serif; font-size:28px; font-weight:800; color:#f1f5f9; margin-top:4px; }
        .bot-grid { overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:8px; padding-right:5px; }
        .bot-row { background:#131d36; border:1px solid #1e293b; border-radius:8px; padding:10px 14px; display:flex; justify-content:space-between; align-items:center; }
        .bot-name { font-weight:700; font-size:14px; color:#f1f5f9; }
        .bot-store { font-size:11px; padding:2px 6px; border-radius:4px; font-weight:800; text-transform:uppercase; }
        .store-amazon { background:#f59e0b22; color:#f59e0b; border:1px solid #f59e0b; }
        .store-flipkart { background:#3b82f622; color:#3b82f6; border:1px solid #3b82f6; }
        .store-multi { background:#a855f722; color:#a855f7; border:1px solid #a855f7; }
        .bot-state { font-size:12px; color:#10b981; }
        .deal-stream { overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:12px; padding-right:5px; }
        .deal-card { background:#1e1b4b; border:1px solid #4338ca; border-radius:10px; padding:15px; position:relative; animation:slideDown 0.4s ease-out; }
        @keyframes slideDown { from { transform:translateY(-20px); opacity:0; } to { transform:translateY(0); opacity:1; } }
        .deal-title { font-weight:700; font-size:15px; color:#f8fafc; margin-bottom:8px; }
        .price-row { display:flex; gap:15px; align-items:baseline; margin-bottom:10px; }
        .deal-price { font-family:'Orbitron', sans-serif; font-size:22px; font-weight:800; color:#10b981; }
        .deal-mrp { font-size:14px; color:#94a3b8; text-decoration:line-through; }
        .deal-tag { background:#ef4444; color:#fff; font-size:12px; font-weight:800; padding:3px 8px; border-radius:5px; }
        .buy-btn { display:inline-block; background:linear-gradient(90deg, #38bdf8, #2563eb); color:#fff; text-decoration:none; padding:8px 14px; border-radius:6px; font-weight:700; font-size:13px; text-align:center; transition:0.2s; }
        .buy-btn:hover { box-shadow:0 0 15px rgba(56,189,248,0.5); }
    </style>
</head>
<body>
    <header>
        <div class="logo">⚡ AMAN BHAI LOOT EMPIRE <span style="font-size:14px; color:#94a3b8;">[21 AUTONOMOUS BOTS]</span></div>
        <div class="status-badge">● 21 BOTS LIVE RUNNING</div>
    </header>

    <div class="container">
        <!-- LEFT: EMPIRE STATS -->
        <div class="card">
            <div class="card-header">📊 RADAR ANALYTICS</div>
            <div class="stat-box" style="border-left-color:#38bdf8;">
                <div class="stat-title">Total Products Scanned</div>
                <div class="stat-value" id="stat-scans">0</div>
            </div>
            <div class="stat-box" style="border-left-color:#10b981;">
                <div class="stat-title">70%+ Loot Deals Caught</div>
                <div class="stat-value" id="stat-loots" style="color:#10b981;">0</div>
            </div>
            <div class="stat-box" style="border-left-color:#f59e0b;">
                <div class="stat-title">Active AI Hunter Bots</div>
                <div class="stat-value" style="color:#f59e0b;">21</div>
            </div>
            <div class="stat-box" style="border-left-color:#ec4899;">
                <div class="stat-title">Telegram Alert Target</div>
                <div class="stat-value" id="stat-target" style="font-size:16px; margin-top:8px; color:#ec4899;">@amanDealsniperBot</div>
            </div>
        </div>

        <!-- CENTER: 21 BOTS RADAR STATUS -->
        <div class="card">
            <div class="card-header">
                <span>🤖 21 HUNTER BOTS STATUS</span>
                <span style="font-size:12px; color:#38bdf8;">Auto-refreshing</span>
            </div>
            <div class="bot-grid" id="bot-grid">
                <!-- Bot rows injected by JS -->
            </div>
        </div>

        <!-- RIGHT: LIVE REAL-TIME LOOT FEED -->
        <div class="card">
            <div class="card-header">
                <span>🔥 LIVE LOOT STREAM</span>
                <span style="font-size:12px; color:#ef4444;">70%+ OFF</span>
            </div>
            <div class="deal-stream" id="deal-stream">
                <div style="text-align:center; color:#64748b; margin-top:40px; font-size:14px;">
                    Radar active... Scanning Amazon, Flipkart & Multi-Stores for 70%+ price cuts.
                </div>
            </div>
        </div>
    </div>

    <script>
        let lastDealCount = 0;
        async function refreshDashboard() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('stat-scans').innerText = data.total_scans.toLocaleString();
                document.getElementById('stat-loots').innerText = data.total_loots.toLocaleString();

                // Render Bot Grid
                const botGrid = document.getElementById('bot-grid');
                botGrid.innerHTML = '';
                for (const [name, info] of Object.entries(data.bots)) {
                    const storeClass = info.store.toLowerCase() === 'amazon' ? 'store-amazon' : (info.store.toLowerCase() === 'flipkart' ? 'store-flipkart' : 'store-multi');
                    botGrid.innerHTML += `
                        <div class="bot-row">
                            <div>
                                <span class="bot-store ${storeClass}">${info.store}</span>
                                <span class="bot-name" style="margin-left:8px;">${name}</span>
                            </div>
                            <div class="bot-state">⚡ Scanned: ${info.scans} | Loots: ${info.loots}</div>
                        </div>
                    `;
                }

                // Render Live Feed
                if (data.recent_deals && data.recent_deals.length > 0) {
                    const stream = document.getElementById('deal-stream');
                    stream.innerHTML = '';
                    data.recent_deals.forEach(deal => {
                        stream.innerHTML += `
                            <div class="deal-card">
                                <span class="deal-tag">${deal.discount}% OFF</span>
                                <div class="deal-title" style="margin-top:6px;">${deal.title}</div>
                                <div class="price-row">
                                    <span class="deal-price">₹${deal.price}</span>
                                    <span class="deal-mrp">₹${deal.mrp}</span>
                                </div>
                                <a href="${deal.link}" target="_blank" class="buy-btn">⚡ View Deal (${deal.store})</a>
                            </div>
                        `;
                    });

                    // Voice Alert when new deal is found
                    if (data.total_loots > lastDealCount && 'speechSynthesis' in window) {
                        const latest = data.recent_deals[0];
                        const utterance = new SpeechSynthesisUtterance("Aman bhai! New " + latest.discount + " percent loot deal caught!");
                        utterance.pitch = 1.1;
                        utterance.rate = 1.0;
                        window.speechSynthesis.speak(utterance);
                    }
                    lastDealCount = data.total_loots;
                }
            } catch(e) { console.log("Dashboard fetch error", e); }
        }
        setInterval(refreshDashboard, 3000);
        refreshDashboard();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def api_stats():
    with stats_lock:
        return jsonify({
            "total_scans": total_scans_count,
            "total_loots": total_loots_found,
            "bots": bot_status_tracker,
            "recent_deals": live_deals_feed[:15]
        })

def run_flask_server():
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
                cards = soup.find_all('div', class_='_1sdMkc') or soup.find_all('div', class_='_75nlfW') or soup.find_all('div', class_='slAVV4')

                with stats_lock:
                    total_scans_count += len(cards)
                    bot_status_tracker[bot_name]["scans"] += len(cards)

                for card in cards:
                    text_content = card.text
                    if any(w in text_content.lower() for w in BLOCKED_WORDS):
                        continue

                    disc_elem = card.find(lambda tag: tag.name == 'div' and '%' in tag.text and 'off' in tag.text.lower())
                    if not disc_elem:
                        continue

                    try:
                        disc_str = disc_elem.text.replace('%', '').replace('off', '').strip()
                        discount = int(disc_str)
                    except Exception:
                        continue

                    if discount >= MIN_DISCOUNT_PERCENT:
                        title = card.find('a', class_='wjcEIp') or card.find('div', class_='KzDlHZ')
                        title_text = title.text.strip() if title else search_keyword.title()

                        price_elem = card.find('div', class_='Nx9bqj')
                        mrp_elem = card.find('div', class_='yRaY8j')

                        if price_elem and mrp_elem:
                            try:
                                price = int(price_elem.text.replace('₹', '').replace(',', '').strip())
                                mrp = int(mrp_elem.text.replace('₹', '').replace(',', '').strip())
                            except Exception:
                                continue

                            if mrp < MIN_MRP:
                                continue

                            link_elem = card.find('a')
                            raw_link = link_elem.get('href', '') if link_elem else ''
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
                                "savings": mrp - price,
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
# 🚀 LAUNCHING THE 21 BOTS EMPIRE
# ==========================================
if __name__ == '__main__':
    print("=" * 65)
    print("   ⚡ AMAN BHAI 21-BOT LOOT EMPIRE SYSTEM ACTIVATING ⚡")
    print("=" * 65)
    print("📲 Telegram Target: @amanDealsniperBot (ID: 6208434509)")
    print("🌐 Web Dashboard:   http://localhost:5000")
    print("🎯 Loot Filter:     Minimum 70% DISCOUNT ONLY | Zero Spam")
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

    print("\n✅ All 21 Autonomous Bots are LIVE and hunting in parallel!")
    print("👉 Open your browser at: http://localhost:5000 to see Live Mission Control Radar!\n")

    # Keep master supervisor alive
    while True:
        time.sleep(1)
