# Collapse Monitor - Local Server
# Run: python server.py
# Then open: http://localhost:5000

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, os, re, time, urllib.request, urllib.parse, urllib.error, csv, io, statistics, threading, difflib
from datetime import datetime, timezone
from ddgs import DDGS

app   = Flask(__name__)
CORS(app)

# Restore scheduler on startup if previously configured
def _restore_scheduler():
    try:
        saved = load_settings()
        interval = saved.get("schedulerInterval")
        if interval and float(interval) >= 1:
            import urllib.request as _ur
            import threading as _th, time as _t
            _t.sleep(2)  # wait for server to start
            req = _ur.Request("http://localhost:5000/scheduler/start",
                data=__import__("json").dumps({"intervalHours": interval}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try: _ur.urlopen(req, timeout=5)
            except Exception: pass
    except Exception: pass
_rt = __import__("threading").Thread(target=_restore_scheduler, daemon=True)
_rt.start()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ARTICLES_FILE      = os.path.join(DATA_DIR, "articles.json")
SETTINGS_FILE      = os.path.join(DATA_DIR, "settings.json")
FAILED_QUERIES_FILE = os.path.join(DATA_DIR, "failed_queries.json")
SOURCES_FILE        = os.path.join(BASE_DIR, "sources.json")  # ships with the app, user-editable
THRESHOLDS_FILE     = os.path.join(DATA_DIR, "thresholds.json")
LOCAL_MONITOR_FILE  = os.path.join(DATA_DIR, "local_monitor.json")
RESILIENCE_FILE     = os.path.join(DATA_DIR, "resilience.json")
FASCISM_FILE        = os.path.join(DATA_DIR, "fascism.json")
EVENTS_FILE         = os.path.join(DATA_DIR, "events.json")
FRED_FILE           = os.path.join(DATA_DIR, "fred_cache.json")
HISTORY_FILE        = os.path.join(DATA_DIR, "analysis_history.json")
VELOCITY_FILE       = os.path.join(DATA_DIR, "velocity_cache.json")
CONVERGENCE_FILE    = os.path.join(DATA_DIR, "convergence_cache.json")
NOAA_FILE           = os.path.join(DATA_DIR, "noaa_cache.json")
AIS_FILE            = os.path.join(DATA_DIR, "ais_cache.json")
API_KEYS_FILE       = os.path.join(DATA_DIR, "api_keys.json")
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




# ── API KEYS ──────────────────────────────────────────────────────────────────

@app.route("/api-keys", methods=["GET", "POST"])
def api_keys():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            existing = {}
            if os.path.exists(API_KEYS_FILE):
                with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.update(data)
            with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    else:
        try:
            if os.path.exists(API_KEYS_FILE):
                with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
        return jsonify({})


def load_api_keys():
    """Load API keys from disk."""
    try:
        if os.path.exists(API_KEYS_FILE):
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}



# ── NOAA NCDC ─────────────────────────────────────────────────────────────────

STATE_FIPS = {'alabama': '01', 'alaska': '02', 'arizona': '04', 'arkansas': '05', 'california': '06', 'colorado': '08', 'connecticut': '09', 'delaware': '10', 'florida': '12', 'georgia': '13', 'hawaii': '15', 'idaho': '16', 'illinois': '17', 'indiana': '18', 'iowa': '19', 'kansas': '20', 'kentucky': '21', 'louisiana': '22', 'maine': '23', 'maryland': '24', 'massachusetts': '25', 'michigan': '26', 'minnesota': '27', 'mississippi': '28', 'missouri': '29', 'montana': '30', 'nebraska': '31', 'nevada': '32', 'new hampshire': '33', 'new jersey': '34', 'new mexico': '35', 'new york': '36', 'north carolina': '37', 'north dakota': '38', 'ohio': '39', 'oklahoma': '40', 'oregon': '41', 'pennsylvania': '42', 'rhode island': '44', 'south carolina': '45', 'south dakota': '46', 'tennessee': '47', 'texas': '48', 'utah': '49', 'vermont': '50', 'virginia': '51', 'washington': '53', 'west virginia': '54', 'wisconsin': '55', 'wyoming': '56'}

def noaa_request(path, token, params=None):
    """Make a NOAA CDO API request."""
    base = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"token": token, "User-Agent": "CollapseMonitor/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


@app.route("/noaa-data", methods=["GET"])
def noaa_data():
    """Fetch NOAA climate data for user location. Cached 24h."""
    try:
        # Check cache
        if os.path.exists(NOAA_FILE):
            with open(NOAA_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age_h = (time.time() - cached.get("fetchedAt", 0)) / 3600
            if age_h < 24:
                return jsonify(cached)

        keys = load_api_keys()
        token = keys.get("noaa", "")
        if not token:
            return jsonify({"error": "No NOAA API key set. Add it on the Intake page."})

        settings = load_settings()
        state_name = (settings.get("localState") or "").lower().strip()
        fips = STATE_FIPS.get(state_name)
        if not fips:
            return jsonify({"error": f"Cannot find FIPS for state: {state_name}. Set your state on the Intake page."})

        # Find stations in this state with temperature data
        stations_resp = noaa_request("/stations", token, {
            "locationid": f"FIPS:{fips}",
            "datatypeid":  "TMAX",
            "limit":       10,
            "sortfield":   "maxdate",
            "sortorder":   "desc"
        })
        stations = stations_resp.get("results", [])
        if not stations:
            return jsonify({"error": f"No NOAA stations found for state FIPS {fips}"})

        station = stations[0]  # Most recently active station
        station_id = station["id"]

        # Fetch last 365 days of TMAX, TMIN, PRCP
        from datetime import timedelta
        end_date   = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        data_resp = noaa_request("/data", token, {
            "datasetid":  "GHCND",
            "stationid":  station_id,
            "startdate":  start_date,
            "enddate":    end_date,
            "datatypeid": "TMAX,TMIN,PRCP",
            "limit":      1000,
            "units":      "standard"
        })
        records = data_resp.get("results", [])

        # Organise by type
        by_type = {"TMAX": [], "TMIN": [], "PRCP": []}
        for r in records:
            dt = r.get("datatype")
            if dt in by_type:
                by_type[dt].append({"date": r["date"][:10], "value": r["value"]})

        # Compute anomalies: current month vs same-month historical
        def month_anomaly(series, n_baseline=6):
            """Compare last month's mean to prior n_baseline months."""
            if len(series) < 30:
                return None, None, None
            vals = [x["value"] for x in series]
            recent  = statistics.mean(vals[-30:])   # last 30 obs
            baseline_vals = vals[:-30]
            if not baseline_vals:
                return round(recent, 1), None, None
            baseline = statistics.mean(baseline_vals)
            try:
                sd = statistics.stdev(baseline_vals)
            except Exception:
                sd = 0
            z = (recent - baseline) / sd if sd > 0 else 0.0
            return round(recent, 1), round(z, 2), round(baseline, 1)

        tmax_cur, tmax_z, tmax_base = month_anomaly(by_type["TMAX"])
        tmin_cur, tmin_z, tmin_base = month_anomaly(by_type["TMIN"])
        prcp_cur, prcp_z, prcp_base = month_anomaly(by_type["PRCP"])

        def z_to_signal(z, invert=False):
            if z is None: return "unknown"
            v = z if not invert else -z
            if v > 2.5: return "critical"
            if v > 1.5: return "elevated"
            if v > 0.5: return "moderate"
            return "low"

        payload = {
            "station":   {"id": station_id, "name": station.get("name",""), "state": state_name.title()},
            "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "fetchedAt": time.time(),
            "indicators": [
                {
                    "id": "TMAX", "label": "Max Temperature",
                    "current": tmax_cur, "baseline": tmax_base, "zscore": tmax_z,
                    "unit": "°F", "signal": z_to_signal(tmax_z, invert=True),
                    "trend": by_type["TMAX"][-30:]
                },
                {
                    "id": "TMIN", "label": "Min Temperature",
                    "current": tmin_cur, "baseline": tmin_base, "zscore": tmin_z,
                    "unit": "°F", "signal": z_to_signal(tmin_z, invert=True),
                    "trend": by_type["TMIN"][-30:]
                },
                {
                    "id": "PRCP", "label": "Precipitation",
                    "current": prcp_cur, "baseline": prcp_base, "zscore": prcp_z,
                    "unit": "in", "signal": z_to_signal(prcp_z),
                    "trend": by_type["PRCP"][-30:]
                }
            ]
        }
        with open(NOAA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/noaa-refresh", methods=["POST"])
def noaa_refresh():
    if os.path.exists(NOAA_FILE):
        os.remove(NOAA_FILE)
    return noaa_data()



# ── AISSTREAM.IO ──────────────────────────────────────────────────────────────

MAJOR_PORTS = [
    {"name": "Singapore",      "bbox": [[1.1, 103.6], [1.5, 104.1]]},
    {"name": "Shanghai",       "bbox": [[30.5, 121.0], [31.5, 122.0]]},
    {"name": "Rotterdam",      "bbox": [[51.8, 3.9], [52.1, 4.7]]},
    {"name": "Los Angeles",    "bbox": [[33.5, -118.5], [34.0, -118.0]]},
    {"name": "Houston",        "bbox": [[29.5, -95.5], [29.9, -94.8]]},
    {"name": "Hamburg",        "bbox": [[53.4, 9.7], [53.7, 10.2]]},
    {"name": "Dubai",          "bbox": [[25.0, 55.0], [25.4, 55.5]]},
    {"name": "New York",       "bbox": [[40.4, -74.2], [40.8, -73.8]]},
]


@app.route("/ais-data", methods=["GET"])
def ais_data():
    """Fetch AIS vessel snapshot near major ports. Cached 6h."""
    try:
        if os.path.exists(AIS_FILE):
            with open(AIS_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age_h = (time.time() - cached.get("fetchedAt", 0)) / 3600
            if age_h < 6:
                return jsonify(cached)

        keys = load_api_keys()
        api_key = keys.get("aisstream", "")
        if not api_key:
            return jsonify({"error": "No AISStream API key set. Add it on the Intake page."})

        # Check websocket-client is available, try to install if not
        try:
            import websocket
        except ImportError:
            import subprocess, sys
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                       "websocket-client", "--quiet",
                                       "--break-system-packages"],
                                      timeout=60)
                import websocket
            except Exception as install_err:
                return jsonify({"error":
                    "websocket-client not installed and auto-install failed. "
                    "Run manually: pip install websocket-client. "
                    f"Detail: {install_err}"})

        import threading
        vessel_counts = {p["name"]: 0 for p in MAJOR_PORTS}
        vessel_details = []
        done_event = threading.Event()
        lock = threading.Lock()

        def on_message(ws, msg):
            try:
                data = json.loads(msg)
                meta = data.get("MetaData", {})
                lat  = meta.get("latitude_deg")
                lng  = meta.get("longitude_deg")
                mmsi = meta.get("MMSI")
                name = meta.get("ShipName", "").strip()
                if lat is None or lng is None:
                    return
                with lock:
                    for port in MAJOR_PORTS:
                        bb = port["bbox"]
                        if bb[0][0] <= lat <= bb[1][0] and bb[0][1] <= lng <= bb[1][1]:
                            vessel_counts[port["name"]] += 1
                    vessel_details.append({"lat": lat, "lng": lng, "mmsi": mmsi, "name": name})
            except Exception:
                pass

        def on_open(ws):
            sub = {
                "APIKey": api_key,
                "BoundingBoxes": [p["bbox"] for p in MAJOR_PORTS],
                "FilterMessageTypes": ["PositionReport"]
            }
            ws.send(json.dumps(sub))

        def on_error(ws, err):
            done_event.set()

        wsa = websocket.WebSocketApp(
            "wss://stream.aisstream.io/v0/stream",
            on_message=on_message,
            on_open=on_open,
            on_error=on_error
        )

        t = threading.Thread(target=wsa.run_forever)
        t.daemon = True
        t.start()
        # Collect for 20 seconds
        time.sleep(20)
        wsa.close()

        total = sum(vessel_counts.values())
        ports_data = [
            {"name": k, "vessels": v,
             "signal": "critical" if v == 0 else "elevated" if v < 3 else "low"}
            for k, v in vessel_counts.items()
        ]
        ports_data.sort(key=lambda x: -x["vessels"])

        payload = {
            "ports":      ports_data,
            "totalVessels": total,
            "sampleSeconds": 20,
            "updatedAt":  datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "fetchedAt":  time.time(),
        }
        with open(AIS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ais-refresh", methods=["POST"])
def ais_refresh():
    if os.path.exists(AIS_FILE):
        os.remove(AIS_FILE)
    return ais_data()

FRED_INDICATORS = [
    {"id": "UNRATE",    "label": "Unemployment Rate",        "unit": "%",   "invert": True},
    {"id": "CPIAUCSL",  "label": "CPI Inflation",            "unit": "idx", "invert": True},
    {"id": "FEDFUNDS",  "label": "Federal Funds Rate",       "unit": "%",   "invert": False},
    {"id": "T10Y2Y",    "label": "Yield Curve (10y-2y)",     "unit": "%",   "invert": False},
    {"id": "ICSA",      "label": "Weekly Jobless Claims",    "unit": "k",   "invert": True},
    {"id": "DCOILWTICO","label": "WTI Crude Oil",            "unit": "$/b", "invert": False},
    {"id": "DTWEXBGS",  "label": "US Dollar Index",          "unit": "idx", "invert": False},
    {"id": "UMCSENT",   "label": "Consumer Sentiment",       "unit": "idx", "invert": False},
]

def fetch_fred_series(series_id, observation_start="2023-01-01"):
    """Fetch FRED CSV data — no API key required."""
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
           f"?id={series_id}&vintage_date=&cosd={observation_start}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CollapseMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(raw))
        rows = [(r["DATE"], float(r[series_id]))
                for r in reader
                if r.get(series_id) and r[series_id] not in (".", "")]
        return rows
    except Exception as e:
        return []

def compute_zscore(rows):
    """Compute z-score of the most recent value vs. trailing window."""
    if len(rows) < 10:
        return None, None, None
    values = [v for _, v in rows]
    recent  = values[-1]
    # Use up to 104 weeks (~2 years) of history
    window  = values[max(0, len(values)-104):-1]
    if len(window) < 5:
        return recent, None, None
    mu  = statistics.mean(window)
    try:
        sd  = statistics.stdev(window)
    except Exception:
        sd = 0
    z   = (recent - mu) / sd if sd > 0 else 0.0
    return recent, round(z, 2), round(mu, 3)

def zscore_to_signal(z, invert=False):
    """Convert z-score to signal level. invert=True means high value = bad."""
    if z is None:
        return "unknown"
    if invert:
        if z > 2.5:  return "critical"
        if z > 1.5:  return "elevated"
        if z > 0.5:  return "moderate"
        return "low"
    else:
        if z < -2.5: return "critical"
        if z < -1.5: return "elevated"
        if z < -0.5: return "moderate"
        return "low"


@app.route("/fred-data", methods=["GET"])
def fred_data():
    """Return cached FRED economic indicators, refreshing if >24h old."""
    try:
        # Check cache
        if os.path.exists(FRED_FILE):
            with open(FRED_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age_hours = (time.time() - cached.get("fetchedAt", 0)) / 3600
            if age_hours < 24:
                return jsonify(cached)

        # Fetch fresh data
        results = []
        for ind in FRED_INDICATORS:
            rows = fetch_fred_series(ind["id"])
            if not rows:
                continue
            current, z, mean_val = compute_zscore(rows)
            signal = zscore_to_signal(z, ind.get("invert", False))
            # Last 12 data points for sparkline
            sparkline = [{"date": d, "value": v} for d, v in rows[-12:]]
            results.append({
                "id":       ind["id"],
                "label":    ind["label"],
                "unit":     ind["unit"],
                "current":  round(current, 3) if current is not None else None,
                "mean":     mean_val,
                "zscore":   z,
                "signal":   signal,
                "invert":   ind.get("invert", False),
                "date":     rows[-1][0] if rows else None,
                "sparkline": sparkline,
            })

        payload = {
            "indicators": results,
            "fetchedAt":  time.time(),
            "updatedAt":  datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
        with open(FRED_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e), "indicators": []}), 500


@app.route("/fred-refresh", methods=["POST"])
def fred_refresh():
    """Force a fresh FRED fetch by deleting the cache."""
    try:
        if os.path.exists(FRED_FILE):
            os.remove(FRED_FILE)
        return fred_data()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── ARTICLE VELOCITY & ANOMALY DETECTION ─────────────────────────────────────

@app.route("/velocity", methods=["GET"])
def velocity():
    """
    Compute rolling z-scores for article counts per topic.
    Detects when a topic's coverage is spiking above its recent baseline.
    Returns per-topic velocity scores and an overall convergence signal.
    """
    try:
        # Check cache (refresh every 2 hours)
        if os.path.exists(VELOCITY_FILE):
            with open(VELOCITY_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("computedAt", 0) < 7200:
                return jsonify(cached)

        articles = load_articles()
        if not articles:
            return jsonify({"topics": [], "convergence": None, "computedAt": time.time()})

        # Group articles by topic and week
        from collections import defaultdict
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        topic_weeks = defaultdict(lambda: defaultdict(int))

        for a in articles:
            raw = (a.get("date") or "")[:10]
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            age_days = (now - dt).days
            if age_days > 365:
                continue
            week = age_days // 7  # 0 = this week, 1 = last week, etc.
            tid = a.get("topicId", "unknown")
            topic_weeks[tid][week] += 1

        results = []
        anomalous_topics = []

        for tid, weeks in topic_weeks.items():
            # Build 12-week series (most recent first = week 0)
            series = [weeks.get(w, 0) for w in range(12)]
            current = series[0]          # this week
            baseline = series[1:]        # previous 11 weeks

            if len(baseline) < 3:
                continue

            mu = statistics.mean(baseline)
            try:
                sd = statistics.stdev(baseline)
            except Exception:
                sd = 0

            z = (current - mu) / sd if sd > 0 else 0.0
            signal = ("critical" if z > 3.0 else
                      "elevated" if z > 2.0 else
                      "moderate" if z > 1.0 else "low")

            entry = {
                "topicId":  tid,
                "current":  current,
                "baseline": round(mu, 1),
                "zscore":   round(z, 2),
                "signal":   signal,
                "series":   list(reversed(series)),  # chronological order for chart
                "trend":    "accelerating" if z > 1.5 else "stable" if abs(z) < 0.5 else "declining"
            }
            results.append(entry)
            if signal in ("critical", "elevated"):
                anomalous_topics.append(tid)

        results.sort(key=lambda x: -abs(x["zscore"]))

        # Cross-domain convergence: multiple topics spiking simultaneously
        convergence = None
        if len(anomalous_topics) >= 3:
            convergence = {
                "signal":     "critical" if len(anomalous_topics) >= 5 else "elevated",
                "topicCount": len(anomalous_topics),
                "topics":     anomalous_topics,
                "description": f"{len(anomalous_topics)} topics showing simultaneous coverage spikes — potential cross-domain convergence event."
            }
        elif len(anomalous_topics) == 2:
            convergence = {
                "signal":     "moderate",
                "topicCount": 2,
                "topics":     anomalous_topics,
                "description": f"2 topics ({', '.join(anomalous_topics)}) showing concurrent spikes."
            }

        payload = {
            "topics":      results,
            "convergence": convergence,
            "totalArticles": len(articles),
            "computedAt":  time.time(),
            "updatedAt":   now.strftime("%Y-%m-%d %H:%M UTC")
        }

        with open(VELOCITY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e), "topics": [], "convergence": None}), 500


# ── ANALYSIS HISTORY ──────────────────────────────────────────────────────────

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"patterns": [], "thresholds": [], "resilience": [], "backslide": []}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


@app.route("/history/append", methods=["POST"])
def history_append():
    """Append a new analysis result to the history log (max 30 per type)."""
    data = request.get_json() or {}
    kind  = data.get("kind")   # patterns | thresholds | resilience | backslide
    entry = data.get("entry")
    if not kind or not entry:
        return jsonify({"ok": False, "error": "Missing kind or entry"}), 400
    try:
        history = load_history()
        if kind not in history:
            history[kind] = []
        entry["savedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        history[kind].append(entry)
        history[kind] = history[kind][-30:]  # keep last 30
        save_history(history)
        return jsonify({"ok": True, "count": len(history[kind])})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/history/<kind>", methods=["GET"])
def history_get(kind):
    """Get history for a given analysis type."""
    history = load_history()
    return jsonify(history.get(kind, []))


# ── BACKGROUND SCHEDULER ─────────────────────────────────────────────────────

_scheduler_thread = None
_scheduler_stop   = threading.Event()
_scheduler_status = {"running": False, "interval": 0, "lastRun": None, "nextRun": None}


def _scheduler_worker(interval_hours, settings):
    """Background thread: collect every interval_hours using saved settings."""
    while not _scheduler_stop.is_set():
        next_run = time.time() + interval_hours * 3600
        _scheduler_status["nextRun"] = datetime.fromtimestamp(
            next_run, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Wait until next run or stop signal
        while time.time() < next_run and not _scheduler_stop.is_set():
            _scheduler_stop.wait(60)  # check every minute

        if _scheduler_stop.is_set():
            break

        # Run collection using saved settings
        try:
            saved = load_settings()
            kws    = saved.get("keywords", [])
            topics = saved.get("topics",   [])
            source = saved.get("ingestSource", "ddg")
            days   = int(saved.get("lbDays", 1))

            from_date = (datetime.now(timezone.utc) -
                         __import__("datetime").timedelta(days=days)
                         ).strftime("%Y-%m-%d")

            # POST to our own /collect endpoint
            import urllib.request, json as json_mod
            payload = json_mod.dumps({
                "keywords":  kws[:20],
                "topicMap":  {t["id"]: t["keywords"] for t in topics if isinstance(t, dict)},
                "fromDate":  from_date,
                "domains":   [],
                "source":    source
            }).encode()

            req = urllib.request.Request(
                "http://localhost:5000/collect",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=600)
            _scheduler_status["lastRun"] = datetime.now(
                timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass  # scheduler keeps running even if one collection fails


@app.route("/scheduler", methods=["GET"])
def scheduler_get():
    return jsonify(_scheduler_status)


@app.route("/scheduler/start", methods=["POST"])
def scheduler_start():
    global _scheduler_thread, _scheduler_stop
    data = request.get_json() or {}
    interval = float(data.get("intervalHours", 24))
    if interval < 1:
        return jsonify({"ok": False, "error": "Minimum interval is 1 hour"}), 400

    # Stop existing scheduler if running
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_stop.set()
        _scheduler_thread.join(timeout=5)

    _scheduler_stop = threading.Event()
    settings = load_settings()
    _scheduler_thread = threading.Thread(
        target=_scheduler_worker,
        args=(interval, settings),
        daemon=True
    )
    _scheduler_thread.start()
    _scheduler_status.update({"running": True, "interval": interval})

    # Persist scheduler config in settings
    settings["schedulerInterval"] = interval
    save_settings(settings)
    return jsonify({"ok": True, "intervalHours": interval})


@app.route("/scheduler/stop", methods=["POST"])
def scheduler_stop():
    global _scheduler_thread
    _scheduler_stop.set()
    _scheduler_status.update({"running": False, "nextRun": None})
    settings = load_settings()
    settings.pop("schedulerInterval", None)
    save_settings(settings)
    return jsonify({"ok": True})



@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    else:
        try:
            if os.path.exists(EVENTS_FILE):
                with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
        return jsonify([])


@app.route("/fascism", methods=["GET", "POST"])
def fascism():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            with open(FASCISM_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    else:
        try:
            if os.path.exists(FASCISM_FILE):
                with open(FASCISM_FILE, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
        return jsonify({})


@app.route("/resilience", methods=["GET", "POST"])
def resilience():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            with open(RESILIENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    else:
        try:
            if os.path.exists(RESILIENCE_FILE):
                with open(RESILIENCE_FILE, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
        return jsonify({})


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
    seen_urls  = set(a.get("url","") for a in load_articles())
    seen_titles = set()
    # Also load existing title fingerprints for similarity dedup
    for a in load_articles():
        t = a.get("title","").lower().strip()
        if t: seen_titles.add(t[:60])  # first 60 chars as fingerprint
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
                                title_fp=(r.get("title","")or"").lower().strip()[:60]
                                if title_fp and title_fp in seen_titles: continue
                                seen_urls.add(url)
                                if title_fp: seen_titles.add(title_fp)
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
                            title_fp=(r.get("title","")or"").lower().strip()[:60]
                            if title_fp and title_fp in seen_titles: continue
                            seen_urls.add(url)
                            if title_fp: seen_titles.add(title_fp)
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
                    title_fp=(r.get("title","")or"").lower().strip()[:60]
                    if title_fp and title_fp in seen_titles: continue
                    seen_urls.add(url)
                    if title_fp: seen_titles.add(title_fp)
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
                    title_fp=(r.get("title","")or"").lower().strip()[:60]
                    if title_fp and title_fp in seen_titles: continue
                    seen_urls.add(url)
                    if title_fp: seen_titles.add(title_fp)
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
