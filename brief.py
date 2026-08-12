#!/usr/bin/env python3
"""
Weekly gaming-sector brief -> Telegram.

Design principle: financial disclosure moves prices, product news mostly does
not. Everything here is ordered and filtered on that basis.

Runs free on GitHub Actions. No paid API required; the LLM synthesis step is
optional and degrades gracefully to a plain digest if no key is set.
"""

import os
import sys
import html
import time
import json
from datetime import datetime, timedelta, timezone

import requests
import feedparser

import config

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Optional LLM synthesis. Set ONE of these (or none).
# Groq is tried first: free tier, works in the EU, no card required.
GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

UA = {"User-Agent": "weekly-gaming-brief/1.0 (personal research script)"}
# SEC EDGAR requires a real contact address in the User-Agent.
SEC_UA = {"User-Agent": "weekly-gaming-brief personal-research jakubmasri@yahoo.com"}

CUTOFF = datetime.now(timezone.utc) - timedelta(days=config.LOOKBACK_DAYS)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def entry_date(entry):
    """Best-effort published date from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def is_recent(entry):
    d = entry_date(entry)
    return d is None or d >= CUTOFF


def looks_financial(text):
    low = text.lower()
    return any(k.lower() in low for k in config.SIGNAL_KEYWORDS)


def safe_get(url, headers=None, timeout=20):
    try:
        r = requests.get(url, headers=headers or UA, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception as e:
        print(f"  ! fetch failed {url}: {e}", file=sys.stderr)
    return None


def esc(s):
    return html.escape(str(s), quote=False)


# --------------------------------------------------------------------------
# 1. Price / FX data (Yahoo Finance chart endpoint - no key needed)
# --------------------------------------------------------------------------
def get_quote(symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=1mo&interval=1d")
    r = safe_get(url)
    if not r:
        return None
    try:
        res = r.json()["chart"]["result"][0]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c]
        if len(closes) < 2:
            return None
        last = closes[-1]
        week_ago = closes[-6] if len(closes) >= 6 else closes[0]
        month_ago = closes[0]
        return {
            "last": last,
            "w_pct": (last / week_ago - 1) * 100,
            "m_pct": (last / month_ago - 1) * 100,
            "ccy": res["meta"].get("currency", ""),
        }
    except Exception as e:
        print(f"  ! parse failed {symbol}: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------
# 2. SEC filings (US names only) - the primary-disclosure layer
# --------------------------------------------------------------------------
def get_sec_filings(ticker):
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&CIK={ticker}&type=8-K&dateb=&owner=include&count=10&output=atom")
    r = safe_get(url, headers=SEC_UA)
    if not r:
        return []
    feed = feedparser.parse(r.text)
    out = []
    for e in feed.entries:
        if not is_recent(e):
            continue
        out.append({"title": e.get("title", "8-K"), "link": e.get("link", "")})
    return out[:3]


# --------------------------------------------------------------------------
# 3. Company news via Google News RSS (free, no key, stable format)
# --------------------------------------------------------------------------
def get_company_news(phrase):
    q = requests.utils.quote(f'"{phrase}"')
    url = (f"https://news.google.com/rss/search?q={q}+when:7d"
           f"&hl=en-GB&gl=GB&ceid=GB:en")
    r = safe_get(url)
    if not r:
        return []
    feed = feedparser.parse(r.text)
    items, seen = [], set()
    for e in feed.entries:
        title = e.get("title", "")
        if not title or title in seen:
            continue
        # Financial-signal filter: this is what keeps it useful
        if not looks_financial(title):
            continue
        seen.add(title)
        items.append({"title": title, "link": e.get("link", "")})
        if len(items) >= config.MAX_ITEMS_PER_COMPANY:
            break
    return items


# --------------------------------------------------------------------------
# 4. Industry feeds
# --------------------------------------------------------------------------
def get_industry():
    out = []
    for source, url in config.INDUSTRY_FEEDS:
        r = safe_get(url)
        if not r:
            continue
        feed = feedparser.parse(r.text)
        for e in feed.entries:
            if not is_recent(e):
                continue
            title = e.get("title", "")
            if not title or not looks_financial(title):
                continue
            out.append({"source": source, "title": title,
                        "link": e.get("link", "")})
    return out[:config.MAX_INDUSTRY_ITEMS]


# --------------------------------------------------------------------------
# 5. Catalyst calendar
# --------------------------------------------------------------------------
def upcoming_catalysts(horizon_days=120):
    today = datetime.now(timezone.utc).date()
    limit = today + timedelta(days=horizon_days)
    out = []
    for raw, label in config.CATALYSTS:
        try:
            if len(raw) == 7:                      # YYYY-MM
                d = datetime.strptime(raw + "-01", "%Y-%m-%d").date()
                approx = True
            else:
                d = datetime.strptime(raw, "%Y-%m-%d").date()
                approx = False
        except ValueError:
            continue
        if d < today and not approx:
            continue
        if d > limit:
            continue
        days = (d - today).days
        out.append((d, approx, days, label))
    return sorted(out, key=lambda x: x[0])


# --------------------------------------------------------------------------
# 6. Optional LLM synthesis
# --------------------------------------------------------------------------
SYNTH_PROMPT = """You are briefing an investor who tracks the video-game sector broadly -
major publishers across the US, Europe, Japan and Korea.

Framework: financial disclosure moves prices; product news usually does not.
Prioritise balance sheets, cash burn, refinancing, dilution, guidance changes,
M&A and forced-seller dynamics.

Treat a RELEASE DATE CHANGE as high priority - a slipped major title moves
revenue between fiscal years and is one of the strongest catalysts in this
sector. Treat wishlist rank as relevant mainly where a quarter's guidance leans
on one title. IGNORE review scores and launch hype: a record-reviewed launch
once coincided with a double-digit stock fall, because the pipeline mattered
more.

Below is this week's raw material across the sector. Write at most 6 short
bullets covering ONLY what an investor would act on, and name the company each
point concerns. If nothing material happened, say so plainly in one line - do
not manufacture significance. No preamble, no sign-off.

RAW MATERIAL:
{payload}"""


def synthesise(payload):
    if GROQ_KEY:
        return _groq(payload)
    if GEMINI_KEY:
        return _gemini(payload)
    if ANTHROPIC_KEY:
        return _anthropic(payload)
    return None


def _groq(payload):
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "openai/gpt-oss-120b",
                  "reasoning_effort": "medium",
                  "temperature": 0.4,
                  "messages": [{"role": "user",
                                "content": SYNTH_PROMPT.format(
                                    payload=payload[:12000])}]},
            timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  ! groq failed: {e}", file=sys.stderr)
        return None


def _gemini(payload):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}")
    body = {"contents": [{"parts": [
        {"text": SYNTH_PROMPT.format(payload=payload[:12000])}]}]}
    try:
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  ! gemini failed: {e}", file=sys.stderr)
        return None


def _anthropic(payload):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6",
                  "max_tokens": 700,
                  "messages": [{"role": "user",
                                "content": SYNTH_PROMPT.format(
                                    payload=payload[:12000])}]},
            timeout=60)
        r.raise_for_status()
        blocks = r.json().get("content", [])
        return "\n".join(b.get("text", "") for b in blocks
                         if b.get("type") == "text").strip()
    except Exception as e:
        print(f"  ! anthropic failed: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------
def send(text):
    if not TG_TOKEN or not TG_CHAT:
        print("No Telegram credentials set - printing instead:\n")
        print(text)
        return
    # Telegram hard limit is 4096 chars; split on blank lines.
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > 3800:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)

    for i, chunk in enumerate(chunks):
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": chunk,
                  "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=30)
        if r.status_code != 200:
            print(f"Telegram error {r.status_code}: {r.text}", file=sys.stderr)
        if i < len(chunks) - 1:
            time.sleep(1)


# --------------------------------------------------------------------------
# Build the brief
# --------------------------------------------------------------------------
def main():
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    L = [f"<b>Gaming sector brief - {today}</b>"]

    raw_for_llm = []

    # --- Prices -----------------------------------------------------------
    print("Fetching prices...")
    price_lines = []
    for c in config.WATCHLIST:
        q = get_quote(c["yahoo"])
        if not q:
            continue
        arrow = "+" if q["w_pct"] >= 0 else ""
        price_lines.append(
            f"{esc(c['name']):<18} {q['last']:>8.2f} {q['ccy']}  "
            f"1w {arrow}{q['w_pct']:.1f}%  1m {q['m_pct']:+.1f}%")
        raw_for_llm.append(
            f"PRICE {c['name']}: {q['last']:.2f} {q['ccy']}, "
            f"1w {q['w_pct']:+.1f}%, 1m {q['m_pct']:+.1f}%")
        time.sleep(0.3)

    if price_lines:
        L.append("<b>Prices</b>\n<pre>" + "\n".join(price_lines) + "</pre>")

    # --- FX ---------------------------------------------------------------
    fx_lines = []
    for pair in config.FX_PAIRS:
        q = get_quote(pair)
        if q:
            fx_lines.append(f"{pair.replace('=X',''):<8} {q['last']:>7.3f}  "
                            f"1w {q['w_pct']:+.1f}%")
            time.sleep(0.3)
    if fx_lines:
        L.append(f"<b>FX vs {config.BASE_CURRENCY}</b>\n<pre>"
                 + "\n".join(fx_lines) + "</pre>")

    # --- Primary disclosure ----------------------------------------------
    print("Fetching SEC filings...")
    sec_lines = []
    for c in config.WATCHLIST:
        if not c["sec"]:
            continue
        for f in get_sec_filings(c["sec"]):
            sec_lines.append(
                f"• <b>{esc(c['name'])}</b>: <a href=\"{f['link']}\">"
                f"{esc(f['title'][:110])}</a>")
            raw_for_llm.append(f"SEC FILING {c['name']}: {f['title']}")
        time.sleep(0.4)
    if sec_lines:
        L.append("<b>SEC filings (7d)</b>\n" + "\n".join(sec_lines))

    # --- Company news, financially filtered ------------------------------
    print("Fetching company news...")
    news_blocks = []
    for c in config.WATCHLIST:
        items = get_company_news(c["news"])
        if not items:
            continue
        block = [f"<b>{esc(c['name'])}</b>"]
        for it in items:
            block.append(f"• <a href=\"{it['link']}\">{esc(it['title'][:130])}</a>")
            raw_for_llm.append(f"NEWS {c['name']}: {it['title']}")
        news_blocks.append("\n".join(block))
        time.sleep(0.4)
    if news_blocks:
        L.append("<b>Company signal (7d)</b>\n\n" + "\n\n".join(news_blocks))
    else:
        L.append("<b>Company signal (7d)</b>\nNothing financially material picked up.")

    # --- Industry ---------------------------------------------------------
    print("Fetching industry feeds...")
    ind = get_industry()
    if ind:
        lines = [f"• [{esc(i['source'])}] <a href=\"{i['link']}\">"
                 f"{esc(i['title'][:130])}</a>" for i in ind]
        L.append("<b>Industry</b>\n" + "\n".join(lines))
        raw_for_llm += [f"INDUSTRY {i['source']}: {i['title']}" for i in ind]

    # --- Steam pipeline: dates, wishlists, concurrents --------------------
    print("Building pipeline report...")
    try:
        import pipeline
        pipe_lines, pipe_raw = pipeline.build_pipeline_report(
            config.TRACKED_TITLES,
            getattr(config, "AUTO_TRACK_TOP_UPCOMING", 0))
        L += pipe_lines
        raw_for_llm += pipe_raw
    except Exception as e:
        print(f"  ! pipeline module failed: {e}", file=sys.stderr)

    # --- Catalysts --------------------------------------------------------
    cats = upcoming_catalysts()
    if cats:
        lines = []
        for d, approx, days, label in cats:
            when = d.strftime("%b %Y") if approx else d.strftime("%d %b")
            tag = "~" if approx else ""
            lines.append(f"• {tag}{when} (T-{days}d) - {esc(label)}")
        L.append("<b>Catalyst calendar</b>\n" + "\n".join(lines))

    L.append("<b>Standing watch</b>\n"
             + "\n".join(f"• {esc(w)}" for w in config.WATCH_ITEMS))

    # --- Optional synthesis ----------------------------------------------
    if raw_for_llm:
        print("Synthesising...")
        s = synthesise("\n".join(raw_for_llm))
        if s:
            L.insert(1, f"<b>What matters</b>\n{esc(s)}")

    # --- The manual part -------------------------------------------------
    L.append("<i>Prediction log: write direction, magnitude, probability and "
             "what is already priced in — before the next catalyst. The bot "
             "cannot do this part.</i>")

    send("\n\n".join(L))
    print("Done.")


if __name__ == "__main__":
    main()
