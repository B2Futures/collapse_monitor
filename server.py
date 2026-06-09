# Collapse Monitor - Local Server
# Run: python server.py
# Then open: http://localhost:5000

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, os, re, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone
from ddgs import DDGS

app   = Flask(__name__)
CORS(app)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ARTICLES_FILE      = os.path.join(DATA_DIR, "articles.json")
SETTINGS_FILE      = os.path.join(DATA_DIR, "settings.json")
FAILED_QUERIES_FILE = os.path.join(DATA_DIR, "failed_queries.json")
SOURCES_FILE        = os.path.join(BASE_DIR, "sources.json")  # ships with the app, user-editable
THRESHOLDS_FILE     = os.path.join(DATA_DIR, "thresholds.json")
LOCAL_MONITOR_FILE  = os.path.join(DATA_DIR, "local_monitor.json")
LOCAL_BRIEFING_FILE  = os.path.join(DATA_DIR, "local_briefing.json")
LOCAL_ARTICLES_FILE  = os.path.join(DATA_DIR, "local_articles.json")

# -- Topic-aware query variant templates -----------------------
TOPIC_VARIANTS = {
    "climate":        ["{kw}", "{kw} {yr}", "{kw} record extreme {yr}", "{kw} impacts scientists"],
    "disease":        ["{kw}", "{kw} {yr}", "{kw} outbreak spread {yr}", "{kw} WHO health alert"],
    "manufacturing":  ["{kw}", "{kw} {yr}", "{kw} factory jobs losses {yr}", "{kw} industrial output decline"],
    "trade":          ["{kw}", "{kw} {yr}", "{kw} tariffs sanctions {yr}", "{kw} supply shortage disruption"],
    "food":           ["{kw}", "{kw} {yr}", "{kw} hunger famine {yr}", "{kw} crop supply shortage"],
    "energy":         ["{kw}", "{kw} {yr}", "{kw} blackout shortage {yr}", "{kw} grid failure crisis"],
    "finance":        ["{kw}", "{kw} {yr}", "{kw} bank debt recession {yr}", "{kw} market collapse risk"],
    "infrastructure": ["{kw}", "{kw} {yr}", "{kw} failure breakdown {yr}", "{kw} aging repair neglect"],
    "governance":     ["{kw}", "{kw} {yr}", "{kw} democracy election {yr}", "{kw} authoritarian crackdown"],
    "water":          ["{kw}", "{kw} {yr}", "{kw} shortage depletion {yr}", "{kw} conflict access crisis"],
    "migration":      ["{kw}", "{kw} {yr}", "{kw} refugees displacement {yr}", "{kw} border crisis {yr}"],
    "conflict":       ["{kw}", "{kw} {yr}", "{kw} war sanctions territory {yr}", "{kw} military escalation"],
    "health_systems": ["{kw}", "{kw} {yr}", "{kw} hospital capacity shortage {yr}", "{kw} infrastructure collapse"],
    "tech_ai":        ["{kw}", "{kw} {yr}", "{kw} failure outage risk {yr}", "{kw} cybersecurity energy {yr}"],
    "agriculture":    ["{kw}", "{kw} {yr}", "{kw} soil yield inputs {yr}", "{kw} farming crisis collapse"],
}
DEFAULT_VARIANTS = ["{kw}", "{kw} {yr}", "{kw} latest {yr}", "{kw} crisis risk {yr}"]


def build_variants(kw, tid):
    templates = TOPIC_VARIANTS.get(tid, DEFAULT_VARIANTS)
    yr = str(datetime.now().year)
    return [t.replace("{kw}", kw).replace("{yr}", yr) for t in templates]


# -- GDELT helpers ---------------------------------------------
GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"

def gdelt_timelimit(from_date_str):
    """Return GDELT STARTDATETIME string or None."""
    if not from_date_str:
        return None
    try:
        dt = datetime.strptime(from_date_str, "%Y-%m-%d")
        return dt.strftime("%Y%m%d%H%M%S")
    except Exception:
        return None

# Minimum seconds between GDELT requests to avoid 429s
GDELT_REQUEST_DELAY = 2.0
_gdelt_last_request = 0.0


def fetch_gdelt(query, from_date_str, max_results=250, to_date_str=None):
    """Query GDELT Doc 2.0 ArtList endpoint with rate-limit handling.

    Coverage: Feb 19 2015 to present.
    max_results: up to 250 per query (GDELT hard limit).
    to_date_str: optional end date YYYY-MM-DD for month-range queries.
    Retries up to 4 times with exponential backoff on 429 / 5xx.
    """
    global _gdelt_last_request

    params = {
        "query":      query,
        "mode":       "ArtList",
        "maxrecords": str(min(max_results, 250)),
        "format":     "json",
        "sort":       "DateDesc",
    }
    start = gdelt_timelimit(from_date_str)
    if start:
        params["STARTDATETIME"] = start
    if to_date_str:
        try:
            dt_end = datetime.strptime(to_date_str, "%Y-%m-%d")
            params["ENDDATETIME"] = dt_end.strftime("%Y%m%d235959")
        except Exception:
            pass

    req_url = GDELT_API + "?" + urllib.parse.urlencode(params)

    max_retries = 4
    backoff     = 5.0   # initial backoff seconds; doubles each retry

    for attempt in range(max_retries):
        # Enforce minimum spacing between requests
        elapsed = time.time() - _gdelt_last_request
        if elapsed < GDELT_REQUEST_DELAY:
            time.sleep(GDELT_REQUEST_DELAY - elapsed)

        try:
            req = urllib.request.Request(
                req_url,
                headers={"User-Agent": "CollapseMonitor/1.0"}
            )
            _gdelt_last_request = time.time()
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            _gdelt_last_request = time.time()
            if e.code == 429 or e.code >= 500:
                wait = backoff * (2 ** attempt)
                print(f"GDELT {e.code} on attempt {attempt+1}/{max_retries} "
                      f"for '{query[:60]}' — waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            return [], f"HTTP {e.code}: {e.reason}"

        except Exception as e:
            _gdelt_last_request = time.time()
            if attempt < max_retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"GDELT error attempt {attempt+1}/{max_retries}: {e} — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            return [], str(e)

        # Success — parse articles
        articles = []
        for item in (data.get("articles") or []):
            url_art = item.get("url", "")
            title   = item.get("title", "")
            if not url_art or not title:
                continue
            date_raw = item.get("seendate", "")
            date_str = (date_raw[:4] + "-" + date_raw[4:6] + "-" + date_raw[6:8]
                        if len(date_raw) >= 8
                        else datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            articles.append({
                "url":     url_art,
                "title":   title,
                "source":  item.get("domain", extract_domain(url_art)),
                "date":    date_str,
                "snippet": "",
                "lang":    item.get("language", "English"),
            })
        return articles, None

    # Caller is responsible for recording the failure with record_failed_query()
    return [], f"GDELT exhausted {max_retries} retries (rate-limited) for '{query[:60]}'"


# -- Routes ----------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "collapse-monitor.html")

@app.route("/status")
def status():
    arts = load_articles()
    return jsonify({"ok": True, "articles": len(arts)})

@app.route("/failed-queries")
def get_failed_queries():
    return jsonify({"queries": load_failed_queries()})

@app.route("/retry-failed", methods=["POST"])
def retry_failed():
    """Replay all persisted failed GDELT queries. Clears each one on success."""
    failed = load_failed_queries()
    if not failed:
        return jsonify({"articles": [], "count": 0, "cleared": 0})

    articles  = []
    seen_urls = set()
    still_failed = []

    for fq in failed:
        query     = fq.get("query", "")
        from_date = fq.get("fromDate", "")
        to_date   = fq.get("toDate")
        topic_id  = fq.get("topicId", "climate")
        context   = fq.get("context", "collect")

        max_results = 250 if context == "historical" else 20
        gdelt_arts, err = fetch_gdelt(query, from_date,
                                       max_results=max_results,
                                       to_date_str=to_date)
        if err:
            print(f"Retry still failed: {query[:60]}: {err}")
            still_failed.append(fq)
            continue

        for r in gdelt_arts:
            url = r["url"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if from_date and r["date"] and r["date"] < from_date:
                continue
            articles.append({
                "id":           "gdelt-r-" + str(abs(hash(url)))[-8:],
                "title":        r["title"],
                "url":          url,
                "source":       r["source"],
                "date":         r["date"],
                "snippet":      "",
                "topicId":      topic_id,
                "type":         "news",
                "region":       "global",
                "trusted":      _is_trusted(url),
                "ingestSource": "gdelt",
                "fetchedAt":    datetime.now(timezone.utc).isoformat()
            })

    save_failed_queries(still_failed)
    return jsonify({
        "articles": articles,
        "count":    len(articles),
        "cleared":  len(failed) - len(still_failed),
        "remaining": len(still_failed)
    })


@app.route("/sources", methods=["GET"])
def get_sources():
    """Return sources.json — user-editable source list."""
    try:
        if os.path.exists(SOURCES_FILE):
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception as e:
        print("Sources load error:", e)
    return jsonify({})

@app.route("/sources", methods=["POST"])
def save_sources():
    """Overwrite sources.json with user edits."""
    data = request.get_json() or {}
    try:
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/thresholds", methods=["GET"])
def get_thresholds():
    try:
        if os.path.exists(THRESHOLDS_FILE):
            with open(THRESHOLDS_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})

@app.route("/thresholds", methods=["POST"])
def save_thresholds():
    data = request.get_json() or {}
    try:
        with open(THRESHOLDS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/local-monitor", methods=["GET"])
def get_local_monitor():
    try:
        if os.path.exists(LOCAL_MONITOR_FILE):
            with open(LOCAL_MONITOR_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})

@app.route("/local-monitor", methods=["POST"])
def save_local_monitor():
    data = request.get_json() or {}
    try:
        with open(LOCAL_MONITOR_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500




@app.route("/local-articles", methods=["GET"])
def get_local_articles():
    try:
        if os.path.exists(LOCAL_ARTICLES_FILE):
            with open(LOCAL_ARTICLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify({"articles": data, "count": len(data)})
    except Exception:
        pass
    return jsonify({"articles": [], "count": 0})

@app.route("/local-articles", methods=["POST"])
def save_local_articles():
    data = request.get_json() or {}
    articles = data.get("articles", [])
    try:
        with open(LOCAL_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True, "count": len(articles)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/local-briefing", methods=["GET"])
def get_local_briefing():
    try:
        if os.path.exists(LOCAL_BRIEFING_FILE):
            with open(LOCAL_BRIEFING_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})

@app.route("/local-briefing", methods=["POST"])
def save_local_briefing():
    data = request.get_json() or {}
    try:
        with open(LOCAL_BRIEFING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Local topic keyword map for community-level searches
LOCAL_TOPIC_QUERIES = {
    "climate":        ["flooding","wildfire","drought","extreme weather","storm damage","heat emergency"],
    "disease":        ["outbreak","health alert","disease spread","hospital surge"],
    "manufacturing":  ["factory closing","plant layoffs","industrial jobs","manufacturing"],
    "trade":          ["supply shortage","prices rising","store closures","supply chain"],
    "food":           ["food bank","food insecurity","hunger","grocery shortage","farm"],
    "energy":         ["power outage","blackout","utility rates","electricity grid"],
    "finance":        ["budget deficit","unemployment","housing costs","foreclosure","debt"],
    "infrastructure": ["bridge repair","road failure","water main","sewer overflow","infrastructure"],
    "governance":     ["city council","county government","election","policy","budget cuts"],
    "water":          ["water quality","drought","water supply","reservoir","well"],
    "migration":      ["homelessness","housing shortage","population","displacement"],
    "conflict":       ["crime","violence","protest","civil unrest"],
    "health_systems": ["hospital","clinic","healthcare access","emergency room"],
    "tech_ai":        ["broadband","internet access","technology"],
    "agriculture":    ["crop failure","farm","agriculture","livestock","irrigation"],
}

@app.route("/collect-local", methods=["POST"])
def collect_local():
    """Collect news for a specific city/county/state."""
    data        = request.get_json() or {}
    city        = (data.get("city")     or "").strip()
    county      = (data.get("county")   or "").strip()
    state       = (data.get("state")    or "").strip()
    from_date   = data.get("fromDate",  "")
    topic_ids   = data.get("topics",    [])
    custom_kws  = data.get("keywords",  [])   # [{kw, topicId}, ...]

    if not city and not county and not state:
        return jsonify({"error": "No location specified", "articles": [], "count": 0}), 400

    # Build location strings
    if city and state:
        loc_primary = city + " " + state
        loc_county  = (county + " County " + state) if county else state
    elif county and state:
        loc_primary = county + " County " + state
        loc_county  = loc_primary
    else:
        loc_primary = state
        loc_county  = state

    timelimit = ddg_timelimit(from_date) if from_date else "m"
    print(f"[local] location='{loc_primary}' timelimit='{timelimit}' from='{from_date}'")

    articles  = []
    seen_urls = set()
    SLEEP     = 1.5   # seconds between queries

    def add_result(r, tid):
        url = r.get("url", "")
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        articles.append({
            "id":           "loc-" + str(abs(hash(url)))[-8:],
            "title":        r.get("title", ""),
            "url":          url,
            "source":       r.get("source", extract_domain(url)),
            "date":         parse_date(r.get("date", "")),
            "snippet":      (r.get("body") or "")[:300],
            "topicId":      tid,
            "type":         "news",
            "region":       "local",
            "location":     loc_primary,
            "fetchedAt":    datetime.now(timezone.utc).isoformat(),
            "ingestSource": "ddg",
        })

    def run_query(q, tid):
        """Run one DDG query in its own session to avoid timeout accumulation."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(q, timelimit=timelimit, max_results=10, timeout=10) or [])
            print(f"[local] '{q}' -> {len(results)} results")
            for r in results:
                add_result(r, tid)
        except Exception as e:
            print(f"[local] error '{q}': {e}")
        time.sleep(SLEEP)

    active_tids = topic_ids if topic_ids else list(LOCAL_TOPIC_QUERIES.keys())

    # ── Build query list ──────────────────────────────────────────────────────

    # 1. General local news — broadest signal
    run_query(loc_primary + " news", "governance")
    if loc_county != loc_primary:
        run_query(loc_county + " news", "governance")

    # 2. Custom keywords from Intake — prefix each with location
    for item in custom_kws[:20]:
        kw  = item.get("kw", "") if isinstance(item, dict) else str(item)
        tid = item.get("topicId", "governance") if isinstance(item, dict) else "governance"
        if kw.strip():
            run_query(loc_primary + " " + kw.strip(), tid)

    # 3. Topic keywords — use LOCAL_TOPIC_QUERIES for all active topics
    for tid in active_tids:
        kws = LOCAL_TOPIC_QUERIES.get(tid, [])
        for kw in kws[:3]:   # up to 3 per topic
            run_query(loc_primary + " " + kw, tid)

    # 4. County-level pass for top topics if county differs from primary
    if loc_county != loc_primary:
        HIGH_SIG = {"water", "energy", "infrastructure", "health_systems",
                    "food", "governance", "climate", "finance"}
        for tid in active_tids:
            if tid in HIGH_SIG:
                kws = LOCAL_TOPIC_QUERIES.get(tid, [])
                if kws:
                    run_query(loc_county + " " + kws[0], tid)

    total = len([k for t in active_tids for k in LOCAL_TOPIC_QUERIES.get(t,[])[:3]])
    print(f"[local] done — {len(articles)} articles from ~{2 + len(custom_kws[:20]) + total} queries")
    return jsonify({"articles": articles, "count": len(articles)})



@app.route("/retag-articles", methods=["POST"])
def retag_articles():
    """Re-stamp trusted flag on all articles based on current sources.json."""
    try:
        # Load current sources list to build trusted domains set
        trusted_domains = set()
        if os.path.exists(SOURCES_FILE):
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                srcs = json.load(f)
            # sources.json: {group_name: [{id, domain, ...}, ...]}
            for group in srcs.values():
                if isinstance(group, list):
                    for src in group:
                        if isinstance(src, dict) and src.get("domain"):
                            trusted_domains.add(src["domain"].lower())

        if not trusted_domains:
            return jsonify({"ok": False, "error": "No domains found in sources.json"}), 400

        # Load and retag articles
        articles = load_articles()
        tagged = 0
        for a in articles:
            url = (a.get("url") or "").lower()
            domain = extract_domain(url).lower()
            was = a.get("trusted")
            a["trusted"] = any(d in domain or d in url for d in trusted_domains)
            if a["trusted"] != was:
                tagged += 1

        # Save back
        with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)

        return jsonify({
            "ok": True,
            "total": len(articles),
            "tagged": tagged,
            "trustedDomains": len(trusted_domains),
            "trustedCount": sum(1 for a in articles if a.get("trusted")),
            "untrustedCount": sum(1 for a in articles if not a.get("trusted"))
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/load")
def load():
    return jsonify({"articles": load_articles(), "settings": load_settings()})

@app.route("/save", methods=["POST"])
def save():
    data = request.get_json() or {}
    if "articles" in data:
        save_articles(data["articles"])
    if "settings" in data:
        save_settings(data["settings"])
    if "failedQueries" in data:
        save_failed_queries(data["failedQueries"])
    return jsonify({"ok": True, "saved": len(data.get("articles", []))})

def _load_trusted_domains():
    """Load all trusted domains from sources.json into a set."""
    domains = set()
    try:
        if os.path.exists(SOURCES_FILE):
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                srcs = json.load(f)
            for group in srcs.values():
                if isinstance(group, list):
                    for src in group:
                        if isinstance(src, dict) and src.get("domain"):
                            domains.add(src["domain"].lower())
    except Exception:
        pass
    return domains

def _is_trusted(url):
    """Check if URL belongs to a trusted source domain."""
    if not url:
        return False
    url_lower = url.lower()
    return any(d in url_lower for d in _load_trusted_domains())


@app.route("/collect", methods=["POST"])
def collect():
    data      = request.get_json() or {}
    keywords  = data.get("keywords", [])
    topic_id  = data.get("topicId", "climate")
    topic_map = data.get("topicMap", {})
    from_date = data.get("fromDate", "")
    domains   = data.get("domains", [])
    source    = data.get("source", "ddg")   # "ddg" | "gdelt" | "both"

    articles  = []
    seen_urls = set()
    timelimit = ddg_timelimit(from_date)

    try:
        with DDGS() as ddgs:
            for kw in keywords[:20]:
                tid      = topic_map.get(kw, topic_id)
                variants = build_variants(kw, tid)

                # ---- DDG passes ----
                if source in ("ddg", "both"):
                    for v_idx, base_query in enumerate(variants):
                        passes = [base_query]  # no domain restriction — collect everything

                        got_results = False
                        for query in passes:
                            try:
                                results = list(ddgs.news(query, timelimit=timelimit, max_results=10))
                            except Exception:
                                results = []

                            for r in results:
                                url = r.get("url", "")
                                if not url or url in seen_urls:
                                    continue
                                seen_urls.add(url)
                                date_str = parse_date(r.get("date", ""))
                                if from_date and date_str and date_str < from_date:
                                    continue
                                articles.append({
                                    "id":        "ddg-" + str(abs(hash(url)))[-8:],
                                    "title":     r.get("title", ""),
                                    "url":       url,
                                    "source":    r.get("source", extract_domain(url)),
                                    "date":      date_str,
                                    "snippet":   (r.get("body") or "")[:300],
                                    "topicId":   tid,
                                    "type":      "news",
                                    "region":    "global",
                                    "trusted":   _is_trusted(url),
                                    "ingestSource": "ddg",
                                    "fetchedAt": datetime.now(timezone.utc).isoformat()
                                })
                            if results:
                                got_results = True
                                break
                        if v_idx > 0 and not got_results:
                            break

                # ---- GDELT passes ----
                if source in ("gdelt", "both"):
                    for base_query in variants[:2]:   # GDELT: base + year variant only (more precise)
                        gdelt_arts, err = fetch_gdelt(base_query, from_date, max_results=20)
                        if err:
                            print(f"GDELT error for '{base_query}': {err}")
                            if "exhausted" in err or "rate-limited" in err:
                                record_failed_query(base_query, from_date, tid, context="collect")
                            continue
                        for r in gdelt_arts:
                            url = r["url"]
                            if not url or url in seen_urls:
                                continue
                            seen_urls.add(url)
                            if from_date and r["date"] and r["date"] < from_date:
                                continue
                            articles.append({
                                "id":        "gdelt-" + str(abs(hash(url)))[-8:],
                                "title":     r["title"],
                                "url":       url,
                                "source":    r["source"],
                                "date":      r["date"],
                                "snippet":   "",
                                "topicId":   tid,
                                "type":      "news",
                                "region":    "global",
                                "ingestSource": "gdelt",
                                "fetchedAt": datetime.now(timezone.utc).isoformat()
                            })

    except Exception as e:
        return jsonify({"error": str(e), "articles": [], "count": 0}), 500

    return jsonify({"articles": articles, "count": len(articles)})


# -- Historical GDELT month-range collection --------------------------

@app.route("/collect-historical", methods=["POST"])
def collect_historical():
    """Collect a specific calendar month from GDELT.
    
    Body: { year: int, month: int, keywords: [...], topicMap: {...}, topicId: str }
    Returns articles deduplicated against the provided existing_urls set.
    """
    data       = request.get_json() or {}
    year       = int(data.get("year",  datetime.now().year))
    month      = int(data.get("month", datetime.now().month))
    keywords   = data.get("keywords", [])
    topic_id   = data.get("topicId", "climate")
    topic_map  = data.get("topicMap", {})
    known_urls = set(data.get("existingUrls", []))

    # Build exact month window
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{year:04d}-{month:02d}-01"
    to_date   = f"{year:04d}-{month:02d}-{last_day:02d}"

    articles  = []
    seen_urls = set(known_urls)  # seed with already-collected URLs

    try:
        for kw in keywords[:20]:
            tid      = topic_map.get(kw, topic_id)
            variants = build_variants(kw, tid)

            for base_query in variants[:2]:   # base + year-tagged only for archive
                gdelt_arts, err = fetch_gdelt(
                    base_query, from_date,
                    max_results=250,
                    to_date_str=to_date
                )
                if err:
                    print(f"GDELT historical error '{base_query}': {err}")
                    if "exhausted" in err or "rate-limited" in err:
                        record_failed_query(base_query, from_date, tid,
                                            to_date=to_date, context="historical")
                    continue
                for r in gdelt_arts:
                    url = r["url"]
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    articles.append({
                        "id":           "gdelt-h-" + str(abs(hash(url)))[-8:],
                        "title":        r["title"],
                        "url":          url,
                        "source":       r["source"],
                        "date":         r["date"],
                        "snippet":      "",
                        "topicId":      tid,
                        "type":         "news",
                        "region":       "global",
                        "ingestSource": "gdelt",
                        "fetchedAt":    datetime.now(timezone.utc).isoformat()
                    })
    except Exception as e:
        return jsonify({"error": str(e), "articles": [], "count": 0}), 500

    return jsonify({
        "articles": articles,
        "count":    len(articles),
        "window":   f"{from_date} → {to_date}"
    })


# -- Journal collection ----------------------------------------

JOURNAL_SITES = "(site:nature.com OR site:thelancet.com OR site:science.org OR site:nejm.org OR site:pnas.org)"

JOURNAL_VARIANTS = [
    "{kw_sample} " + JOURNAL_SITES,
    "{kw_sample} research findings {yr} " + JOURNAL_SITES,
    "{kw_sample} study published {yr} " + JOURNAL_SITES,
    "{kw_sample} peer reviewed warning {yr} " + JOURNAL_SITES,
]

@app.route("/collect-journals", methods=["POST"])
def collect_journals():
    data      = request.get_json() or {}
    keywords  = data.get("keywords", [])
    from_date = data.get("fromDate", "")
    timelimit = ddg_timelimit(from_date)
    yr        = str(datetime.now().year)
    source    = data.get("source", "ddg")

    articles  = []
    seen_urls = set()
    kw_sample = " OR ".join(keywords[:6])

    try:
        with DDGS() as ddgs:
            for template in JOURNAL_VARIANTS:
                query = template.replace("{kw_sample}", kw_sample).replace("{yr}", yr)
                try:
                    results = list(ddgs.news(query, timelimit=timelimit, max_results=10))
                except Exception:
                    results = []

                got_new = False
                for r in results:
                    url = r.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    got_new = True
                    date_str = parse_date(r.get("date", ""))
                    if from_date and date_str and date_str < from_date:
                        continue
                    articles.append({
                        "id":        "journal-" + str(abs(hash(url)))[-8:],
                        "title":     r.get("title", ""),
                        "url":       url,
                        "source":    r.get("source", extract_domain(url)),
                        "date":      date_str,
                        "snippet":   (r.get("body") or "")[:300],
                        "topicId":   "climate",
                        "type":      "journal",
                        "region":    "global",
                        "ingestSource": "ddg",
                        "fetchedAt": datetime.now(timezone.utc).isoformat()
                    })
                if not got_new:
                    break

        # GDELT journal pass
        if source in ("gdelt", "both"):
            gdelt_query = kw_sample + " " + JOURNAL_SITES
            gdelt_arts, _ = fetch_gdelt(gdelt_query, from_date, max_results=15)
            for r in gdelt_arts:
                url = r["url"]
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                if from_date and r["date"] and r["date"] < from_date:
                    continue
                articles.append({
                    "id":        "gdelt-j-" + str(abs(hash(url)))[-8:],
                    "title":     r["title"],
                    "url":       url,
                    "source":    r["source"],
                    "date":      r["date"],
                    "snippet":   "",
                    "topicId":   "climate",
                    "type":      "journal",
                    "region":    "global",
                    "ingestSource": "gdelt",
                    "fetchedAt": datetime.now(timezone.utc).isoformat()
                })

    except Exception as e:
        return jsonify({"error": str(e), "articles": [], "count": 0}), 500

    return jsonify({"articles": articles, "count": len(articles)})


# -- Helpers ---------------------------------------------------

def ddg_timelimit(from_date_str):
    if not from_date_str:
        return "m"
    try:
        days_ago = (datetime.now() - datetime.strptime(from_date_str, "%Y-%m-%d")).days
        if days_ago <= 7:   return "d"
        if days_ago <= 31:  return "m"
        return "y"
    except Exception:
        return "m"

def parse_date(pub_str):
    if not pub_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(pub_str))
    if m:
        return m.group(1)
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
        try:
            return datetime.strptime(pub_str[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def load_failed_queries():
    try:
        if os.path.exists(FAILED_QUERIES_FILE):
            with open(FAILED_QUERIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_failed_queries(queries):
    with open(FAILED_QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(queries, f, indent=2)

def record_failed_query(query, from_date, topic_id, to_date=None, context="collect"):
    """Append a failed GDELT query to the persistent failed list (deduped by query+dates)."""
    failed = load_failed_queries()
    key = f"{query}|{from_date}|{to_date or ''}|{context}"
    if not any(f.get("key") == key for f in failed):
        failed.append({
            "key":       key,
            "query":     query,
            "fromDate":  from_date,
            "toDate":    to_date,
            "topicId":   topic_id,
            "context":   context,
            "failedAt":  datetime.now(timezone.utc).isoformat(),
        })
        save_failed_queries(failed)
        print(f"Recorded failed query: {query[:60]} [{context}]")


def extract_domain(url):
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else url[:40]

def load_articles():
    try:
        if os.path.exists(ARTICLES_FILE):
            with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("Load error:", e)
    return []

def save_articles(articles):
    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

# -- Entry -----------------------------------------------------

if __name__ == "__main__":
    print("")
    print("  Collapse Monitor Server")
    print("  Running at: http://localhost:5000")
    print("  Data folder: " + DATA_DIR)
    print("  Press Ctrl+C to stop.")
    print("")
    app.run(host="127.0.0.1", port=5000, debug=False)
