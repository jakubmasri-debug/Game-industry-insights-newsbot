#!/usr/bin/env python3
"""
Steam pipeline tracking: release dates, wishlist rank, concurrent players.

Why this is a separate module from the news digest:

  * A release date CHANGE is a first-order catalyst. Ubisoft fell 13% on titles
    slipping to FY2028-29, not on reviews. This module exists mainly to catch
    those changes the week they happen.
  * Wishlist RANK is a demand proxy. It matters when a quarter's guidance leans
    on one title, and is noise otherwise.
  * Concurrent players grade a launch after the fact - useful for calibrating
    your own predictions, not for acting on.

Change detection needs memory, so state is persisted to state.json and
committed back to the repo by the workflow.

All endpoints are free and keyless. None are officially supported by Valve;
they can change without notice, so every call fails soft.
"""

import os
import re
import json
import time
import sys

import requests

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "state.json")

UA = {"User-Agent": "Mozilla/5.0 (compatible; weekly-gaming-brief/1.0)"}

STORE_SEARCH = "https://store.steampowered.com/api/storesearch/"
APP_DETAILS = "https://store.steampowered.com/api/appdetails"
WISHLIST_TOP = "https://store.steampowered.com/search/results/"
CURRENT_PLAYERS = ("https://api.steampowered.com/ISteamUserStats/"
                   "GetNumberOfCurrentPlayers/v1/")


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"titles": {}, "wishlist": {}}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception as e:
        print(f"  ! could not save state: {e}", file=sys.stderr)


# --------------------------------------------------------------------------
# Low-level calls (all fail soft)
# --------------------------------------------------------------------------
def _get(url, params=None, timeout=20):
    try:
        r = requests.get(url, params=params, headers=UA, timeout=timeout)
        if r.status_code == 200:
            return r
        print(f"  ! HTTP {r.status_code} {url}", file=sys.stderr)
    except Exception as e:
        print(f"  ! request failed {url}: {e}", file=sys.stderr)
    return None


def resolve_appid(name):
    """Find a Steam appid from a game name. Saves you looking them up by hand."""
    r = _get(STORE_SEARCH, {"term": name, "cc": "US", "l": "en"})
    if not r:
        return None
    try:
        items = r.json().get("items", [])
    except Exception:
        return None
    if not items:
        return None
    # Prefer an exact-ish match; else take the top hit.
    low = name.lower()
    for it in items:
        if it.get("name", "").lower() == low:
            return it.get("id")
    return items[0].get("id")


def get_app_details(appid):
    """Returns dict with name, release date string, coming_soon flag, price."""
    r = _get(APP_DETAILS, {"appids": appid, "cc": "US", "l": "en"})
    if not r:
        return None
    try:
        block = r.json().get(str(appid)) or {}
        if not block.get("success"):
            return None
        d = block.get("data", {})
        rel = d.get("release_date", {}) or {}
        return {
            "name": d.get("name", ""),
            "date": (rel.get("date") or "").strip(),
            "coming_soon": bool(rel.get("coming_soon")),
            "type": d.get("type", ""),
        }
    except Exception as e:
        print(f"  ! parse appdetails {appid}: {e}", file=sys.stderr)
        return None


def get_wishlist_ranking(pages=2, per_page=100):
    """
    Steam's 'Popular Upcoming' list, ordered by wishlist count.

    Valve does not publish raw wishlist numbers anywhere. This ordering is the
    only free public proxy - so treat it as RANK, never as a count. SteamDB has
    richer data but blocks automated access, so it is a manual check, not a
    feed.

    Returns {lowercased name: rank}.
    """
    ranking = {}
    for page in range(pages):
        r = _get(WISHLIST_TOP, {
            "query": "",
            "filter": "popularwishlist",
            "start": page * per_page,
            "count": per_page,
            "json": 1,
        }, timeout=30)
        if not r:
            break
        try:
            items = r.json().get("items", [])
        except Exception:
            break
        if not items:
            break
        for i, it in enumerate(items):
            name = (it.get("name") or "").strip()
            if not name:
                continue
            appid = it.get("gameid")
            if not appid:
                m = re.search(r"/(?:apps|steam/apps)/(\d+)/", it.get("logo", ""))
                appid = m.group(1) if m else None
            rank = page * per_page + i + 1
            ranking[name.lower()] = {"rank": rank, "appid": appid, "name": name}
        time.sleep(1)
    return ranking


def get_concurrent_players(appid):
    r = _get(CURRENT_PLAYERS, {"appid": appid})
    if not r:
        return None
    try:
        resp = r.json().get("response", {})
        if resp.get("result") != 1:
            return None
        return resp.get("player_count")
    except Exception:
        return None


# --------------------------------------------------------------------------
# Main report
# --------------------------------------------------------------------------
def build_pipeline_report(tracked_titles, auto_top=0):
    """
    tracked_titles: list of dicts from config.TRACKED_TITLES
        {"title": str, "publisher": str, "appid": int|None, "released": bool}
    auto_top: if > 0, also auto-track the N most-wishlisted upcoming titles on
        Steam this week (config.AUTO_TRACK_TOP_UPCOMING). This is the
        "any major title" behaviour - no hand-picking.

    Returns (list_of_lines, raw_strings_for_llm)
    """
    state = load_state()
    titles_state = state.setdefault("titles", {})

    date_changes, upcoming, wishlist_moves, live = [], [], [], []
    raw = []

    print("Fetching Steam wishlist ranking...")
    ranking = get_wishlist_ranking()
    prev_wishlist = state.get("wishlist", {})
    new_wishlist = {}

    # Build the working list: manual titles + auto top-wishlisted upcoming.
    work = list(tracked_titles)
    if auto_top and ranking:
        have = {t["title"].strip().lower() for t in work}
        for it in sorted(ranking.values(), key=lambda x: x["rank"])[:auto_top]:
            nm = (it.get("name") or "").strip()
            if not nm or nm.lower() in have:
                continue
            work.append({"title": nm, "publisher": "",
                         "appid": it.get("appid"), "released": False})
            have.add(nm.lower())
        print(f"Auto-tracking top {auto_top} upcoming titles "
              f"({len(work) - len(tracked_titles)} added).")

    for entry in work:
        title = entry["title"]
        pub = entry.get("publisher", "")
        appid = entry.get("appid")
        key = title.lower()

        # Resolve appid once, then cache it in state so we stop re-searching.
        cached = titles_state.get(key, {})
        if not appid:
            appid = cached.get("appid") or resolve_appid(title)
            time.sleep(0.5)
        if not appid:
            print(f"  ? could not resolve appid for {title}", file=sys.stderr)
            continue

        details = get_app_details(appid)
        time.sleep(0.5)
        if not details:
            continue

        old_date = cached.get("date")
        new_date = details["date"]

        # --- the important bit: did the announced date move? --------------
        if old_date and new_date and old_date != new_date:
            date_changes.append(
                f"• <b>{title}</b> ({pub}): <s>{old_date}</s> → <b>{new_date}</b>")
            raw.append(f"RELEASE DATE CHANGE {title} ({pub}): "
                       f"was {old_date}, now {new_date}")
        elif not old_date and new_date:
            # First time we've seen it - record silently, no alert.
            pass

        if details["coming_soon"] and new_date:
            upcoming.append(f"• {title} ({pub}) — {new_date}")

        # --- wishlist rank ------------------------------------------------
        hit = ranking.get(key)
        if hit:
            rank = hit["rank"]
            new_wishlist[key] = rank
            old_rank = prev_wishlist.get(key)
            if old_rank and old_rank != rank:
                delta = old_rank - rank          # positive = climbing
                direction = "▲" if delta > 0 else "▼"
                wishlist_moves.append(
                    f"• {title}: #{rank} ({direction}{abs(delta)} vs last week)")
                raw.append(f"WISHLIST {title}: rank {rank}, "
                           f"moved {delta:+d} places week-on-week")
            else:
                wishlist_moves.append(f"• {title}: #{rank}")

        # --- concurrents for released titles ------------------------------
        if entry.get("released"):
            players = get_concurrent_players(appid)
            time.sleep(0.4)
            if players is not None:
                prev_players = cached.get("players")
                suffix = ""
                if prev_players:
                    pct = (players / prev_players - 1) * 100
                    suffix = f" ({pct:+.0f}% w/w)"
                live.append(f"• {title}: {players:,} concurrent{suffix}")
                cached["players"] = players

        cached.update({"appid": appid, "date": new_date,
                       "name": details["name"]})
        titles_state[key] = cached

    state["wishlist"] = new_wishlist or prev_wishlist
    save_state(state)

    # --- assemble -------------------------------------------------------
    lines = []
    if date_changes:
        lines.append("<b>⚠ Release date changes</b>\n" + "\n".join(date_changes)
                     + "\n<i>A slipped date is a first-order catalyst. "
                       "Check whether guidance depended on it.</i>")
    if upcoming:
        lines.append("<b>Announced pipeline</b>\n" + "\n".join(upcoming[:12]))
    if wishlist_moves:
        lines.append("<b>Steam wishlist rank</b>\n" + "\n".join(wishlist_moves)
                     + "\n<i>Rank only, not counts. Matters when a quarter "
                       "leans on one title.</i>")
    if live:
        lines.append("<b>Live concurrents</b>\n" + "\n".join(live))

    if not lines:
        lines.append("<b>Pipeline</b>\nNo Steam data returned — check the "
                     "Actions log; endpoints are unofficial.")

    return lines, raw


if __name__ == "__main__":
    import config
    out, _ = build_pipeline_report(
        config.TRACKED_TITLES,
        getattr(config, "AUTO_TRACK_TOP_UPCOMING", 0))
    print("\n\n".join(out))
