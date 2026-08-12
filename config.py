"""
Configuration for the weekly gaming-sector brief.

A broad industry monitor: major publishers across the US, Europe, Japan and
Korea. Titles are tracked automatically (the most-wishlisted upcoming games on
Steam), so you don't hand-pick them. Edit this file to change what's tracked;
everything else can stay untouched.
"""

# ---------------------------------------------------------------------------
# WATCHLIST  (prices, SEC filings, company news)
# ---------------------------------------------------------------------------
# yahoo : Yahoo Finance symbol (price data)
# sec   : SEC ticker for EDGAR 8-K feed (US DOMESTIC filers only, else None)
# news  : search phrase for the Google News RSS query
# ccy   : trading currency
#
# NOTE: verify each Yahoo symbol once at https://finance.yahoo.com/quote/<SYMBOL>
# Symbols drift after restructurings, spin-offs and renamings.

WATCHLIST = [
    # --- North America ---
    {"name": "Take-Two",   "yahoo": "TTWO",   "sec": "TTWO", "ccy": "USD",
     "news": "Take-Two Interactive"},
    {"name": "EA",         "yahoo": "EA",     "sec": "EA",   "ccy": "USD",
     "news": "Electronic Arts"},
    {"name": "Roblox",     "yahoo": "RBLX",   "sec": "RBLX", "ccy": "USD",
     "news": "Roblox Corporation"},
    {"name": "NetEase",    "yahoo": "NTES",   "sec": "NTES", "ccy": "USD",
     "news": "NetEase games"},
    {"name": "Sony",       "yahoo": "SONY",   "sec": None,   "ccy": "USD",
     "news": "Sony PlayStation business"},
    {"name": "Nintendo",   "yahoo": "NTDOY",  "sec": None,   "ccy": "USD",
     "news": "Nintendo"},

    # --- Europe ---
    {"name": "Ubisoft",        "yahoo": "UBI.PA",     "sec": None, "ccy": "EUR",
     "news": "Ubisoft"},
    {"name": "CD Projekt",     "yahoo": "CDR.WA",     "sec": None, "ccy": "PLN",
     "news": "CD Projekt"},
    {"name": "Paradox",        "yahoo": "PDX.ST",     "sec": None, "ccy": "SEK",
     "news": "Paradox Interactive"},
    {"name": "Embracer",       "yahoo": "EMBRACB.ST", "sec": None, "ccy": "SEK",
     "news": "Embracer Group"},
    {"name": "Remedy",         "yahoo": "REMEDY.HE",  "sec": None, "ccy": "EUR",
     "news": "Remedy Entertainment"},
    {"name": "Frontier Dev",   "yahoo": "FDEV.L",     "sec": None, "ccy": "GBP",
     "news": "Frontier Developments"},
    {"name": "Team17",         "yahoo": "TM17.L",     "sec": None, "ccy": "GBP",
     "news": "Team17"},
    {"name": "Devolver",       "yahoo": "DEVO.L",     "sec": None, "ccy": "GBP",
     "news": "Devolver Digital"},

    # --- Japan / Korea ---
    {"name": "Capcom",       "yahoo": "CCOEY",     "sec": None, "ccy": "USD",
     "news": "Capcom"},
    {"name": "Square Enix",  "yahoo": "SQNXF",     "sec": None, "ccy": "USD",
     "news": "Square Enix"},
    {"name": "Krafton",      "yahoo": "259960.KS", "sec": None, "ccy": "KRW",
     "news": "Krafton"},
]

# ---------------------------------------------------------------------------
# INDUSTRY FEEDS  (business/financial coverage first)
# ---------------------------------------------------------------------------
# Verify each URL once - RSS paths change without notice.

INDUSTRY_FEEDS = [
    ("GamesIndustry.biz", "https://www.gamesindustry.biz/feed"),
    ("Game Developer",    "https://www.gamedeveloper.com/rss.xml"),
    ("Naavik",            "https://naavik.co/feed/"),
    ("VGC",               "https://www.videogameschronicle.com/feed/"),
]

# Keywords that mark an item as financially relevant rather than product news.
# This filter is what stops the brief becoming a games-news digest.
SIGNAL_KEYWORDS = [
    "earnings", "results", "guidance", "outlook", "net bookings", "revenue",
    "profit", "loss", "writedown", "impairment", "refinanc", "debt", "bond",
    "equity raise", "placing", "rights issue", "dilut", "cash flow",
    "restructur", "layoff", "redundanc", "studio clos", "cost cut",
    "acquisition", "acquire", "merger", "takeover", "stake", "buyout",
    "take-private", "delist", "IPO", "CEO", "CFO", "resign", "steps down",
    "appoint", "delay", "delayed", "postpone", "cancel", "shelved",
    "downgrade", "upgrade", "price target", "short seller",
    "insider", "director dealing", "share buyback", "dividend",
]

# ---------------------------------------------------------------------------
# CATALYST CALENDAR  (hand-maintained, industry-wide events)
# ---------------------------------------------------------------------------
# The bot cannot build this - it requires reading IR calendars and industry
# schedules. Keep only genuinely market-moving, sector-wide dates here.
# Format: (ISO date or "YYYY-MM" for month-only, label)

CATALYSTS = [
    ("2026-11-19", "Grand Theft Auto VI launch - sector-wide demand event"),
    # Add earnings dates, major launches and industry events as you find them,
    # e.g. ("2026-MM", "<Publisher> Q_ results").
]

# Unscheduled but high-impact - printed as a standing reminder.
WATCH_ITEMS = [
    "M&A: acquisitions, takeovers, take-private deals (large-cap consolidation)",
    "Any equity raise / convertible at a cash-burning studio = dilution trigger",
    "Major refinancing or debt maturity at a leveraged publisher",
    "Index review dates (STOXX / MSCI / FTSE) = mechanical forced selling",
]

# ---------------------------------------------------------------------------
# TITLE TRACKING (Steam pipeline)
# ---------------------------------------------------------------------------
# AUTO_TRACK_TOP_UPCOMING: automatically track the N most-wishlisted UPCOMING
# titles on Steam each week, for release-date changes and wishlist moves. This
# is the "any major title" behaviour - no hand-picking. Set to 0 to disable.
AUTO_TRACK_TOP_UPCOMING = 15

# Optional manual additions on top of the auto list (e.g. a title you care about
# that isn't top-wishlisted yet). Usually leave empty.
# appid    : leave None and the script resolves + caches it in state.json
# released : True = track concurrent players; False = track wishlist rank
#
# Note: console-exclusive titles have no Steam page and can't be tracked here;
# put those in the CATALYSTS calendar instead.
TRACKED_TITLES = [
]

# ---------------------------------------------------------------------------
# HOUSEKEEPING
# ---------------------------------------------------------------------------
LOOKBACK_DAYS = 7          # how far back to scan feeds
MAX_ITEMS_PER_COMPANY = 3  # keep the message readable
MAX_INDUSTRY_ITEMS = 8
BASE_CURRENCY = "CZK"      # for the FX section
FX_PAIRS = ["EURCZK=X", "USDCZK=X", "GBPCZK=X", "SEKCZK=X", "PLNCZK=X"]
