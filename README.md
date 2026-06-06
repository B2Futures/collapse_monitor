# Collapse Monitor v0.4

A local, offline-first tool for tracking systemic collapse signals across 15 categories — climate, governance, conflict, water, food, energy, finance, trade, infrastructure, health systems, disease, manufacturing, migration, agriculture, and technology. Collects articles via DuckDuckGo News and/or GDELT, stores them locally, and uses a locally-running LLM (via LM Studio) to analyze patterns and answer questions about the data.

**No API keys required. No data leaves your machine except for news searches.**

---

## What You Need

| Component | What it does | Free? |
|---|---|---|
| Python 3.9+ | Runs the local server | Yes |
| LM Studio | Runs the AI model locally | Yes |
| A local AI model | Does the analysis and Q&A | Yes |
| A browser | The UI | Yes |

---

## Step 1 — Install Python

**Windows:** Download from [python.org](https://www.python.org/downloads/). During install, check **"Add Python to PATH"**.

**Mac:** Python 3 is usually already installed. Check with `python3 --version` in Terminal. If not, install via [python.org](https://www.python.org/downloads/) or `brew install python3`.

**Linux:** `sudo apt install python3 python3-pip` (Debian/Ubuntu) or equivalent.

Verify it works:
```
python3 --version   # Mac/Linux
python --version    # Windows
```

---

## Step 2 — Download LM Studio

1. Go to [lmstudio.ai](https://lmstudio.ai) and download for your OS
2. Install and open it
3. You'll see a search bar at the top — this is where you find models

---

## Step 3 — Choose and Download a Model

LM Studio lets you run models entirely on your own hardware. Which model to pick depends on how much RAM you have.

### Recommended models (in order of preference)

| Model | RAM needed | Quality | Notes |
|---|---|---|---|
| **Qwen2.5-14B-Instruct** | 16 GB | ★★★★★ | Best overall for this use case. Strong at structured JSON output which the Patterns analyzer needs. |
| **Mistral-Nemo-Instruct-2407** | 16 GB | ★★★★☆ | Excellent at summarization and Q&A. Good alternative to Qwen. |
| **Gemma-4-12B** | 16 GB | ★★★★☆ | Google's latest. Fast and accurate, good balance of JSON and prose. |
| **Llama-3.1-8B-Instruct** | 10 GB | ★★★★☆ | Good balance of speed and quality. Works well on 12 GB RAM. |
| **Gemma-2-9B-Instruct** | 10 GB | ★★★★☆ | Fast and accurate. Good for the Interrogate view. |
| **Phi-3.5-mini-instruct** | 6 GB | ★★★☆☆ | Runs on 8 GB RAM. Decent but struggles with complex JSON output. |
| **Gemma-2-2B-Instruct** | 4 GB | ★★☆☆☆ | Last resort for low RAM. Limited analysis quality. |

### How to download in LM Studio

1. Click the **Search** tab (magnifying glass icon)
2. Search for the model name, e.g. `Qwen2.5-14B`
3. Choose a **Q4_K_M** or **Q5_K_M** quantization — these are compressed versions that fit in less RAM with minimal quality loss
4. Click Download
5. Wait for it to finish (models are 4–10 GB)

> **What is quantization?** Models are compressed into smaller files. Q4_K_M means 4-bit quantization, which uses roughly half the RAM of the full model with maybe 5% quality reduction. Q5_K_M is slightly better quality at slightly more RAM. Avoid Q2 — too much quality loss.

---

## Step 4 — Start the Model Server in LM Studio

1. Click the **Developer** tab (the `<->` icon on the left sidebar)
2. **Enable CORS** — find the CORS toggle and turn it on. Without this the browser will block connections to LM Studio.
3. Click **Start Server** — the button turns green and shows `Running on port 1234`
4. In the model dropdown at the top, select the model you downloaded
5. Leave LM Studio running in the background

> The server runs at `http://localhost:1234` by default. Collapse Monitor is pre-configured for this address.

**Important:** Note the exact model name shown in LM Studio's dropdown. You'll need to paste this into Collapse Monitor's settings. It usually looks like `qwen2.5-14b-instruct` or `gemma-4-12b` — copy it exactly.

**Context window:** LM Studio defaults to a conservative context size. Set it to at least **8,192** for any model, or **16,384+** for Qwen2.5-14B. Go to My Models → your model → Context Length → set the value → Apply.

---

## Step 5 — Get the Files

**Option A — Clone with Git:**
```bash
git clone https://github.com/b2futures/collapse-monitor.git
cd collapse-monitor
```

**Option B — Download ZIP:**
Click the green **Code** button on GitHub → **Download ZIP** → extract it

You should have these files:
```
collapse-monitor/
├── collapse-monitor.html   <- the entire UI (single file)
├── server.py               <- local web server + search backend
├── requirements.txt        <- Python dependencies
├── start.bat               <- Windows launcher
├── start.sh                <- Mac/Linux launcher
├── sources.json            <- editable news source list
└── data/                   <- created automatically on first run
```

---

## Step 6 — Run It

### Windows
Double-click `start.bat`. A command window opens (keep it running), and the browser opens automatically.

### Mac / Linux
```bash
chmod +x start.sh
./start.sh
```

Or manually:
```bash
pip3 install -r requirements.txt
python3 server.py
```
Then open `http://localhost:5000` in your browser.

---

## Step 7 — Configure the App

When the app opens, click **Intake** in the left sidebar.

### Connection Settings

| Setting | Value |
|---|---|
| Server URL | `http://localhost:5000` (leave as-is) |
| LM Studio URL | `http://localhost:1234` (leave as-is) |
| Model Name | Paste the exact name from LM Studio's dropdown |

Click **Test Connections** — both indicators should turn green. If LM Studio shows OFFLINE, make sure you started the server in LM Studio's Developer tab and CORS is enabled.

### Ingest Source

- **DuckDuckGo** — fast, good for recent news (past 1–12 months). Start here.
- **GDELT** — global archive of news in 65+ languages, better for older articles and non-English sources. Slower. Subject to rate limiting — see note below.
- **Both** — maximum coverage.

> **GDELT rate limiting:** GDELT is a free public API. During large collections it will return HTTP 429 errors. The app retries each failed query up to 3 times with 30s, 60s, and 120s waits. Failed queries are saved to `data/failed_queries.json` and a warning banner appears in Intake. Use **[>] Rerun Failed** to replay them later. GDELT rate limits typically reset within 5–10 minutes.

### Topics

All 15 topics are enabled by default. Disable any you don't care about — fewer topics means faster collection.

| Topic | Why it's separate |
|---|---|
| Climate & Weather | Extreme events, sea level, warming trends |
| Disease Outbreaks | Specific pathogen events, WHO alerts |
| Manufacturing | Industrial output, factory closures |
| Trade & Supply Chain | Tariffs, shipping, port disruptions |
| Food Systems | Food insecurity, famine risk |
| Energy Systems | Grid failures, fuel shortages, blackouts |
| Financial Systems | Bank failures, debt crises, currency collapse |
| Infrastructure | Roads, bridges, water systems decay |
| Governance & Politics | Democratic backsliding, coups, state failure |
| Water Systems | Aquifer depletion, freshwater conflicts |
| Migration & Displacement | The human output of most other categories |
| Conflict & Geopolitics | Wars, sanctions, territorial disputes |
| Health Systems | Hospital capacity, drug supply chains |
| Technology & AI | Data center energy, cyberattacks, semiconductor shortages |
| Agriculture | Soil health, fertilizer inputs, crop yields |

### Your Country / Region

Select your country — this adds local news sources alongside the international wires.

### Local Location

Enter your **City**, **County**, and **State/Province**. This is used by the Local tab to collect community-specific news and generate a local risk briefing. City + State gives the best results. These fields save automatically when you click away from them.

---

## Step 8 — First Collection

### Set the lookback period

Choose how far back to search:
- **7–30 days** — quick test run, minimal data
- **60–90 days** — good starting point for pattern detection
- **6 months – 1 year** — comprehensive baseline

### How long the initial collection takes

The bottleneck is the number of active topics multiplied by keywords per topic, not the date range.

| Source | Expected time | Rate limit risk |
|---|---|---|
| DuckDuckGo only | 15–40 minutes | Low |
| GDELT only | 20–50 minutes + retry waits | Medium |
| Both | 45–120 minutes or more | Medium–High |

The browser tab needs to stay open the whole time.

---

## Using the App

The sidebar: **Monitor → Intake → Interrogate → Patterns → Thresholds → National → Local → Archive → Sources**

---

### Monitor

Overview dashboard. Shows total articles, active topics, source count, and the 15 most recent articles. The **Overall Signal** indicator reflects your last Pattern Analysis run and persists across restarts.

---

### Intake

Configure and run collections. Key sections:

- **Connection Settings** — server and LM Studio URLs, model name
- **Ingest Source** — DuckDuckGo, GDELT, or Both
- **Tracked Topics** — toggle any of the 15 topics
- **Country Sources** — local and global outlet toggles per country
- **Local Location** — City / County / State for the Local tab (saves on blur)
- **Date Window** — lookback period with presets and custom days input
- **GDELT Historical Collection** — fetch a specific calendar month back to February 2015

---

### Interrogate

Ask plain-English questions about your collected data. The header shows exactly what you're querying — e.g. **`289 national`** (cyan) and **`47 local`** (green) — so you can see both article pools are always included. A topic dropdown lets you focus the context on a single sector for more specific answers.

The LLM reads the 40 most relevant articles (scored by keyword overlap with your question) and answers with citations like `[12]`. Today's date is injected into the prompt so the model uses article dates as its reference rather than its training cutoff.

**Example questions:**
- *Which sector is collapsing fastest and what are the drivers?*
- *What early warning signals appear across multiple sectors at once?*
- *How are governance failures accelerating other collapse categories?*
- *What water shortages or conflicts are emerging and where?*
- *How are the local patterns in [your area] connecting to national trends?*

---

### Patterns

Structured analysis across all 15 sectors. Produces collapse rates (0–100%), trend direction, signal levels, interconnections, leading indicators, emerging threats, and a dated event timeline. Results persist across restarts.

**Interactive features:**
- **Click any sector name** to expand the model's reasoning for that signal level
- **Click any Leading Indicator or Emerging Threat** to open an article drill panel showing supporting articles scored by relevance. Click again to close.
- **Event Timeline** shows key dated developments in chronological order

This view needs a capable model — Qwen2.5-14B or Gemma-4-12B recommended.

---

### Thresholds

Evaluates 12 planetary boundaries against scientific thresholds. Each card always shows the scientific threshold value and a plain-English explanation of why it matters — visible before any analysis runs.

After clicking **Run Threshold Assessment**, each card shows: current known value, signal level, trend direction, and a 2-3 sentence assessment.

The 12 indicators: Global Temperature, Greenhouse Gas Levels, Sea Level Rise, Ocean Heat Content, Ocean Acidity, Ice Sheets, Glaciers, Arctic Sea Ice, Snow Cover, Permafrost, Earth's Energy Balance, Precipitation & Drought Patterns.

Results save to `data/thresholds.json` and auto-populate on restart.

---

### National

Country-specific risk assessment for the country selected in Intake. Two modes:

**Full Briefing — All Topics:** Analyses 8 sectors (Political Stability & Governance, Economic Health, Food & Water Security, Energy Infrastructure, Healthcare System, Climate Vulnerability, Social Cohesion, Supply Chain Resilience). Each sector shows a collapse rate bar, signal badge, trend arrow, status, and key development. Also generates unique risk factors, stabilizing factors, and watch items specific to that country.

**Deep Dive: [Topic]:** Focuses entirely on one of the 15 topics for that country. Returns a more detailed prompt with 6 topic-specific sub-sectors, actual data points and statistics, named events, a 6-12 month outlook, and 5 watch items. Uses 7,000 max tokens for more thorough output.

Results save to `data/local_monitor.json` and auto-populate on restart.

---

### Local

Community-level monitoring for your specific city, county, and state. Set your location in Intake → Local Location first.

#### Collecting Local News

The **Lookback** dropdown (7 days to 1 year) sets how far back to search. It locks after your first collection run — clear articles to change it. Click **[o] Collect Local News** to run a DuckDuckGo search combining your location with topic-specific community keywords:

- General: `"Austin Texas" local news today`
- Climate: `"Austin Texas" flooding`, `"Travis County" drought`
- Infrastructure: `"Austin Texas" power outage`, `"Travis County" water main`
- And so on across all active topics, 2 keywords per topic

The article count badge in the header updates immediately after collection and shows dismissed articles separately: `47 local articles (3 dismissed)`.

#### Local Archive

Click **[= Local Archive]** to open the full article list. From here you can:

- **Search** by title or source name
- **Filter** by topic
- **[x] Dismiss** any article — marks it as excluded. The URL is kept so it won't be re-fetched, but dismissed articles are filtered out of all analysis: briefings, drill panels, and Interrogate context
- **[+ Restore]** to bring a dismissed article back
- **Show dismissed** checkbox to review what you've excluded

Use dismiss to remove articles that matched your location keywords but are clearly not actually local — national wire stories that mention your city in passing, for example.

#### Local Briefing

Two modes, same as National:

**Full Briefing — All Topics:** 6 sectors (Infrastructure, Economy & Jobs, Food & Water, Energy, Public Health, Governance & Safety) with collapse rates, signal levels, trends, and developments. Plus local risk factors, 30-day watch items, community impacts, and a paragraph connecting local conditions to regional trends.

**Deep Dive: [Topic]:** Focused deep analysis of one topic for your specific location. Asks the model to name specific local infrastructure, employers, water sources, and other concrete local details. Returns 5 risks, 5 watch items, 4 community impacts, 4 data points with numbers, and a trajectory outlook.

Risk factors and watch items are **clickable** — clicking any item searches your local article archive and returns supporting articles in a drill panel, the same way Patterns does.

Results save to `data/local_briefing.json` and auto-populate on restart.

---

### Archive

Full searchable archive of national and global articles. Filter by topic dropdown, search by title/snippet. Articles tagged `GDELT` came from the GDELT archive. Local articles are managed separately in the Local tab.

---

### Sources

Manage the news outlets the app searches. Sources are stored in `sources.json` and persist across app updates. Organized into tabs: Global/Intl, Journals, and one tab per country.

To add a source: enter the display name and domain (e.g. `spiegel.de`), click **[+] Add**. To remove: click **[x] Remove**. Changes save immediately. Removing a source stops future collection — existing articles stay in the archive.

---

## Recurring Collection

The **Date Window** selector is always visible in Intake. The deduplication system skips anything already in your archive, so you can run the same window multiple times safely.

**Common patterns:**
- **Daily top-up** — select Today, click Collect
- **Weekly catch-up** — select 7 days, click Collect
- **Adding a new topic** — enable it, select 90 days or more, collect. Only the new topic's articles come through
- **Going back further** — select 6 months or 1 year; existing articles are skipped
- **Specific historical month** — use GDELT Historical Collection at the bottom of Intake. Coverage back to February 2015

---

## Data Files

All data lives in the `data/` folder and is excluded from Git:

| File | Contents |
|---|---|
| `articles.json` | National/global collected articles |
| `settings.json` | Saved preferences, keywords, location, LM Studio config |
| `failed_queries.json` | GDELT queries that exhausted retries |
| `thresholds.json` | Saved planetary threshold assessment |
| `local_monitor.json` | Saved national/country risk assessment |
| `local_briefing.json` | Saved local community briefing |
| `local_articles.json` | Local community articles (with dismissed flags) |

Storage sizing runs roughly 10–18 MB per year of daily collection runs.

---

## Troubleshooting

**Server shows OFFLINE**
Make sure `server.py` is running. On Windows, check that the command window from `start.bat` is still open.

**LM Studio shows OFFLINE**
Open LM Studio → Developer tab → enable CORS → click Start Server. Confirm a model is loaded in the dropdown.

**"Could not parse JSON" in Patterns, Thresholds, National, or Local**
The model struggled to produce valid JSON. Try again — it's probabilistic and usually works on the second attempt. If it fails consistently, try a larger model. Qwen2.5-14B is the most reliable for structured output.

**Collection returns 0 articles**
DuckDuckGo may be rate-limiting — wait a few minutes and try again. Check that at least one topic is enabled.

**GDELT 429 errors / red warning banner in Intake**
Normal during large GDELT collections. The app saves failed queries to `data/failed_queries.json`. Click **[>] Rerun Failed** after waiting 5–10 minutes for the rate limit to reset. See the GDELT note under Step 7 for full detail.

**Local articles include irrelevant national stories**
DuckDuckGo matches on keywords so national stories mentioning your city will sometimes appear. Open **[= Local Archive]** in the Local tab, find the irrelevant articles, and click **[x] Dismiss**. Dismissed articles are excluded from all briefings and analysis but retained so they won't be re-fetched.

**Location fields reset after refresh**
The city, county, and state fields save automatically when you click or tab away from them. If they're not persisting, make sure the server is running when you fill them in — the save requires a round-trip to `server.py`.

**Local briefing doesn't reflect my location specifically**
The briefing quality depends on having local articles collected. Run **[o] Collect Local News** first, then dismiss any clearly irrelevant results before running the briefing. More local articles = more specific output.

**Thresholds or National shows stale data after switching country**
A warning banner appears if the saved assessment is for a different country. Click **[^] Refresh** to regenerate.

---

## Context Windows and Token Limits

| Call | Approx input tokens | Max output | Total needed |
|---|---|---|---|
| Interrogate | ~2,500 | 3,000 | ~5,500 |
| Patterns | ~4,500 | 8,000 | ~12,500 |
| Thresholds | ~2,500 | 4,000 | ~6,500 |
| National Full Briefing | ~2,500 | 5,000 | ~7,500 |
| National Deep Dive | ~2,500 | 7,000 | ~9,500 |
| Local Full Briefing | ~2,000 | 6,000 | ~8,000 |
| Local Deep Dive | ~2,000 | 7,000 | ~9,000 |

Set your context window in LM Studio to at least **8,192** for all models. For Qwen2.5-14B, set **16,384** or higher. Patterns requires the most headroom — if it truncates, raise the context window first.

---

## Hardware Notes

| RAM | Recommended setup |
|---|---|
| 8 GB | Gemma-2-2B (Q4). Limited quality but functional. |
| 12 GB | Llama-3.1-8B or Gemma-2-9B at Q4. Good quality. |
| 16 GB | Qwen2.5-14B, Gemma-4-12B, or Mistral-Nemo. Best results. |
| 32 GB+ | Any model, including unquantized versions. |

GPU acceleration: LM Studio automatically uses NVIDIA CUDA or Apple Metal if available. Analysis that takes 2–3 minutes on CPU takes 10–20 seconds with GPU.

---

## File Structure for GitHub

```
.gitignore
README.md
collapse-monitor.html   <- entire UI, self-contained single file
server.py               <- local web server + search + collection backend
requirements.txt        <- Python dependencies (flask, flask-cors, ddgs, requests)
sources.json            <- editable news source list (ships with app)
start.bat               <- Windows launcher
start.sh                <- Mac/Linux launcher
data/                   <- created automatically, excluded from Git
```

Recommended `.gitignore`:
```
data/
__pycache__/
*.pyc
.DS_Store
```

`sources.json` lives in the base folder so it ships with the app as a versioned default. Your edits via the Sources tab are saved back to the same file and persist — but since it's tracked by Git, pulling updates may overwrite local additions. Back up your customizations before pulling.

---

## Contributing and Feedback

Bug reports, feature requests, and questions are welcome through **GitHub Issues** at `https://github.com/b2futures/collapse-monitor/issues`.

**To report a bug:** include what you were doing, what you expected vs what happened, any error messages from the browser console (F12 → Console) or the server window, your OS, Python version, and which model you're running.

**To request a feature:** open an issue describing what you'd like and why.
