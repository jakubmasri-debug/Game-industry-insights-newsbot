# Weekly gaming-sector brief → Telegram

A scheduled digest for tracking gaming equities. Runs free on GitHub Actions.

**Design principle:** financial disclosure moves prices, product news mostly
doesn't. Ubisoft shipped the best-reviewed Assassin's Creed in thirteen years,
beat its own guidance, and the stock fell 13% — because major titles slipped to
FY2028-29. Everything here is filtered on that basis. Review scores and launch
hype are deliberately excluded.

---

## What it sends

| Section | Content |
|---|---|
| **What matters** | LLM synthesis via Groq (optional — omitted if no key set) |
| **Prices** | 1-week and 1-month moves for every watchlist name |
| **FX vs CZK** | EUR, USD, GBP, SEK, PLN — your real second position |
| **SEC filings** | 8-Ks from the last 7 days (US-listed names) |
| **Company signal** | News filtered to financial keywords only |
| **Industry** | GamesIndustry.biz, Game Developer, Naavik, VGC |
| **⚠ Release date changes** | Week-on-week diff of announced Steam dates |
| **Announced pipeline** | Upcoming titles with their current dates |
| **Steam wishlist rank** | Position in Popular Upcoming, with w/w movement |
| **Live concurrents** | Player counts for released titles |
| **Catalyst calendar** | Hand-maintained, with days-until countdown |
| **Standing watch** | Unscheduled high-impact events |

---

## The Steam pipeline section

Three different things with three different jobs — worth not conflating them:

**Release date changes — act on these.** A slipped title moves revenue between
fiscal years. This is the mechanism that took Ubisoft down 13% despite a
guidance beat. The script diffs the announced date against last week's and
flags any move. This is the highest-value output in the whole brief.

**Wishlist rank — context only.** Valve publishes no raw wishlist numbers
anywhere, so the script uses Steam's *Popular Upcoming* ordering as a rank
proxy. It matters when a quarter's guidance leans on one title, and is noise
otherwise. SteamDB has better data but blocks automated access — keep that as a
manual monthly check, not a feed.

**Concurrents — for scoring yourself.** Useful for checking after the fact
whether your prediction about a launch was right. Not a trading signal; Black
Flag hit a franchise-record ~105k peak and the stock fell.

### Limits worth knowing

- **Console exclusives have no Steam page.** GTA VI and Marvel's Wolverine can't
  be tracked here at launch. They live in the `CATALYSTS` calendar instead.
- **New-game announcements can't be predicted, only caught fast.** No feed tells
  you a studio is *about* to announce. The date-change detector catches it
  within a week of the Steam page updating.
- **All Steam endpoints are unofficial.** They work reliably today and Valve
  owes nobody stability. Everything fails soft.

### state.json

Change detection needs memory. The workflow commits `state.json` back to the
repo after each run, storing last week's dates, resolved appids and wishlist
ranks. This needs `permissions: contents: write`, which is already in the
workflow.

**The first run produces no change alerts** — there's nothing to compare
against. That's expected, not a fault. Alerts start from run two.

Appids resolve automatically from the title string and then cache. If the
resolver picks the wrong game, fill in `appid` manually in `config.py`.

---

## Setup (about 15 minutes)

### 1. Telegram bot

1. Message **@BotFather** on Telegram → `/newbot` → follow prompts
2. Save the token it gives you
3. Send any message to your new bot
4. Open in a browser, replacing `<TOKEN>`:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Find `"chat":{"id":123456789}` — that number is your chat ID

### 2. Repository

Create a **public** repo (public = unlimited free Actions minutes; private
gives 2,000/month, which is also plenty — this job uses roughly 2 minutes a
week either way). Push these files.

### 3. Secrets

Repo → Settings → Secrets and variables → Actions → *New repository secret*:

| Name | Required | Value |
|---|---|---|
| `TELEGRAM_TOKEN` | yes | from BotFather |
| `TELEGRAM_CHAT_ID` | yes | from step 1 |
| `GROQ_KEY` | no | free tier at console.groq.com — no card, works in the EU |
| `GEMINI_API_KEY` | no | free tier at aistudio.google.com (blocked in some EU regions without a card) |
| `ANTHROPIC_API_KEY` | no | paid, but ~$0.01/week at this volume |

The workflow maps `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` onto the variables the
script expects, so it reuses the secrets already in this repo. To send the
gaming brief through a *separate* bot, create one in BotFather, add
`GAMING_TELEGRAM_TOKEN` and `GAMING_TELEGRAM_CHAT_ID` as secrets, and point the
two lines in `weekly-brief.yml` at those instead.

The synthesis step tries Groq, then Gemini, then Anthropic, and uses whichever
key is set. If none is set it silently skips synthesis and sends the plain
digest. Nothing breaks.

### 4. Set your SEC contact email

Open `brief.py` and replace `YOUR_EMAIL@example.com` in `SEC_UA` with your real
address. SEC EDGAR requires a genuine contact and throttles or blocks
placeholders — leave it and the SEC filings section just comes back empty.

### 5. Test

Actions tab → *Weekly gaming brief* → **Run workflow**. Don't wait for Monday
to find out it's misconfigured.

---

## Maintenance — read this bit

Two things need occasional human attention. Ignore them and the brief quietly
becomes wrong rather than obviously broken, which is worse.

### Verify the symbols once

Yahoo symbols drift, especially after restructurings and renamings. Open
`https://finance.yahoo.com/quote/<SYMBOL>` for each entry in `config.py`.
**Embracer in particular** has been through multiple spin-offs and a renaming
process — confirm the current ticker before trusting its line.

Names missing from the price table are usually a bad symbol, not a bad market.

### Verify the SEC contact address

`SEC_UA` in `brief.py` must carry a real email. EDGAR rejects or throttles
placeholder contacts, and the failure mode is a silently empty filings section
rather than an error.

### Verify the RSS URLs once

Feed paths change without notice. Open each URL in `INDUSTRY_FEEDS`; if you get
XML, it works. A dead feed fails silently by design — the script prints a
warning to the Actions log rather than crashing.

### Keep the calendar current

`CATALYSTS` in `config.py` is hand-maintained, and **this is deliberate**. The
calendar is the actual edge — knowing dates weeks ahead while others react on
the day. Building it requires reading IR financial calendars, which no scraper
does reliably.

Add dates as you find them. Ubisoft's next H1 result date, for instance, is
published on their IR site; the entry here is a month-level placeholder until
you confirm it.

---

## Tuning

**Too noisy?** Trim `SIGNAL_KEYWORDS` in `config.py`. The aggressive version
keeps only: `earnings, guidance, refinanc, equity raise, dilut, delay,
restructur, acquisition, CEO, CFO`.

**Too quiet?** A silent week is usually correct — most weeks contain nothing a
shareholder should act on. Resist the urge to loosen the filter until it
produces reading material. A brief that always has something to say has stopped
being a signal.

**Different schedule?** Edit the cron line. `13 6 * * 1` is Monday 06:13 UTC
(08:13 Prague in summer, 07:13 in winter). The odd minute is deliberate:
on-the-hour jobs are the most likely to be delayed or dropped. GitHub cron is
UTC-only with no DST handling, so the Prague time shifts by an hour twice a
year.

**Note on scheduled runs:** GitHub deprioritises cron jobs under load, so
delivery can slip by 10–30 minutes. Fine weekly, would matter if this were
intraday.

---

## What this does not do

Worth being explicit, because the gap is the important part.

It **collects**. It does not **judge**. It cannot tell you whether a refinancing
is on punitive terms, whether a guidance cut is priced in, or whether a 34% drop
is dislocation or decay. Those are the decisions that determine returns, and
they stay manual.

The line at the end of every message is the actual point: write your prediction
— direction, magnitude, probability, and what's already priced in — *before* the
catalyst, then score it afterwards. Automating the inputs is easy and worth
doing. Automating the judgement is the part that doesn't work, and outsourcing
it is how people stop learning.
