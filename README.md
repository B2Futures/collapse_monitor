# Collapse Monitor

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
| **Llama-3.1-8B-Instruct** | 10 GB | ★★★★☆ | Good balance of speed and quality. Works well on 12 GB RAM. |
| **Gemma-2-9B-Instruct** | 10 GB | ★★★★☆ | Google's model, fast and accurate. Good for the Interrogate view. |
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
2. Click **Start Server** — the button turns green and shows `Running on port 1234`
3. In the model dropdown at the top, select the model you downloaded
4. Leave LM Studio running in the background

> The server runs at `http://localhost:1234` by default. Collapse Monitor is pre-configured for this address.

**Important:** Note the exact model name shown in LM Studio's dropdown. You'll need to paste this into Collapse Monitor's settings. It usually looks like `qwen2.5-14b-instruct` or `llama-3.1-8b-instruct-q4_k_m` — copy it exactly including any suffixes.

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
├── collapse-monitor.html   ← the entire UI (single file)
├── server.py               ← local web server + search backend
├── requirements.txt        ← Python dependencies
├── start.bat               ← Windows launcher
├── start.sh                ← Mac/Linux launcher
└── data/                   ← created automatically on first run
    ├── articles.json       ← your collected articles
    └── settings.json       ← your saved settings
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

Click **Test Connections** — both indicators should turn green. If LM Studio shows OFFLINE, make sure you started the server in LM Studio's Developer tab.

### Ingest Source

- **DuckDuckGo** — fast, good for recent news (past 1–12 months). Start here.
- **GDELT** — global archive of news in 65+ languages, better for older articles and non-English sources. Slower. **Subject to rate limiting** — see note below.
- **Both** — maximum coverage. Use this for initial collection if you have time.

> **GDELT rate limiting:** GDELT is a free public API with no SLA. During large collections it will return HTTP 429 (too many requests) errors. The app handles this automatically — it retries each failed query up to 4 times with increasing wait periods (5s, 10s, 20s). If a query still fails after all retries it is saved to `data/failed_queries.json`. A red warning banner will appear in the Collection Run section showing how many queries failed. Use the **[>] Rerun Failed** button to replay them when ready. Failed queries persist across restarts so you can close the app and retry later. GDELT rate limits typically reset within a few minutes.

### Topics

All 15 topics are enabled by default. Disable any you don't care about — fewer topics means faster collection. The topics and why they're distinct:

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
| **Governance & Politics** | Democratic backsliding, coups, state failure — accelerates every other category |
| **Water Systems** | Aquifer depletion, freshwater conflicts — separate from climate because the dynamics differ |
| **Migration & Displacement** | The human output of most other categories |
| **Conflict & Geopolitics** | Wars, sanctions, territorial disputes |
| **Health Systems** | Hospital capacity, drug supply chains, antibiotic resistance |
| **Technology & AI** | Data center energy, cyberattacks, semiconductor shortages |
| **Agriculture** | Soil health, fertilizer inputs, crop yields — more granular than food systems |

### Your Country

Select your country — this adds local news sources (NYT, BBC, Le Monde, etc.) alongside the international wires.

---

## Step 8 — First Collection

### Set the lookback period

This only appears on first run. Choose how far back to search:
- **7–30 days** — quick test run, minimal data
- **60–90 days** — good starting point for pattern detection
- **6 months – 1 year** — comprehensive baseline

### How long the initial collection takes

**The lookback period has much less effect on collection time than you'd expect.** The bottleneck is not the date range — it's the number of active topics multiplied by the number of keywords and query variants being searched. With all 15 topics active, the app is making hundreds of individual search requests regardless of whether you picked 7 days or 6 months.

Rough timing estimates with all 15 topics active:

| Source | Expected time | Rate limit risk |
|---|---|---|
| DuckDuckGo only | 15–40 minutes | Low |
| GDELT only | 20–50 minutes + retry waits | High |
| Both | 45–120 minutes or more | Medium–High |

These are real numbers. Let it run — the browser tab needs to stay open and active the whole time. Do not close or navigate away. The progress bar moves through 7 batches (topic groups) plus a journal pass at the end.

**GDELT timing note:** When GDELT rate limits trigger, the app automatically waits before retrying (up to 5s, 10s, then 20s per failed query). This can add significant time to a collection run. If rate limiting is severe, some queries will be saved to the failed list for manual retry after the main run completes — this is normal and expected, not an error.

**If you want a faster first run:** disable topics you care less about in the Tracked Topics grid before starting. Each disabled topic removes an entire batch or reduces a batch's keyword count. You can always re-enable topics and run again later — the deduplication system means you'll only collect articles you don't already have.

> **First run tip:** Start with DuckDuckGo only and your most important topics enabled to verify everything works end-to-end. Then do follow-up runs with GDELT or the Historical picker to fill in coverage.

---

## Using the App

The sidebar runs in this order: Monitor → Intake → Interrogate → Patterns → Maps → Thresholds → Local → Archive → Sources.

### Monitor
Overview dashboard. Shows total articles, active topics, active source count, and the 15 most recent articles. The **Overall Signal** indicator in the top-right card reflects your last Pattern Analysis run and persists across restarts.

### Intake
Configure and run collections. See Step 7–8 above for full detail. Key sections:
- **Connection Settings** — server and LM Studio URLs, model name
- **Ingest Source** — DuckDuckGo, GDELT, or Both
- **Tracked Topics** — toggle any of the 15 topics on/off
- **Date Window** — always visible; pick any window and run; deduplication handles the rest
- **GDELT Historical Collection** — fetch a specific calendar month from GDELT back to February 2015

### Interrogate
Ask plain-English questions about your collected data. The LLM reads the 40 most relevant articles (scored by keyword overlap) and answers with citations like `[12]`. Today's date is injected into the prompt so the model uses article dates as its temporal reference rather than defaulting to its training cutoff.

**Example questions that work well:**
- *Which sector is collapsing fastest and what are the drivers?*
- *What early warning signals appear across multiple sectors at once?*
- *How are governance failures accelerating other collapse categories?*
- *What water conflicts or shortages are emerging and where?*
- *How is migration being driven by climate and conflict?*

### Patterns
Runs a structured analysis across all 15 sectors. Produces collapse rates (0–100%), trend direction, signal levels, interconnections, leading indicators, emerging threats, and a dated event timeline. Results are saved and restored on restart — you don't need to re-run every session.

**Interactive features:**
- **Click any sector name or signal badge** to expand a 2-3 sentence explanation of why that signal level was assigned
- **Click any Leading Indicator or Emerging Threat** to open an article drill-down panel showing the archive articles that support it, scored by relevance. Click again to close.
- **Event Timeline** at the bottom shows key dated developments across sectors in chronological order

**This view needs a capable model** — Qwen2.5-14B or Mistral-Nemo are recommended. Phi-3.5-mini may struggle to produce well-formed JSON consistently. If you get "Could not parse JSON", try again — it's probabilistic.

### Maps
Three visualizations of your collected data:

- **[·] Event Map** — every article plotted at its source outlet's geographic location, coloured by topic. Click any dot for the headline, source, date, and a link to the article. Covers sources across the US, UK, Europe, South America, Africa, Russia, Japan, India, Australia, and specialist outlets (Arctic, environment).
- **[#] Risk Density** — countries sized by article volume, coloured by worst signal level from Pattern Analysis. Run Patterns first for signal colouring; otherwise all bubbles show green.
- **[~] Sector Network** — the 15 sectors arranged in a circle. Node size = collapse rate. Border colour = signal level. Connecting lines show cross-sector relationships from Pattern Analysis (red = strong, orange = moderate, yellow = weak, dashed = weak).

All three maps require collected articles. The Sector Network additionally requires a completed Pattern Analysis.

### Thresholds
Evaluates 12 planetary boundaries against their scientific thresholds using your LLM. Each indicator card always shows:
- The scientific threshold value (what the science says the safe limit is)
- **Why It Matters** — a fixed explanation of why this indicator is tracked, visible before any analysis is run

After clicking **Run Threshold Assessment**:
- Current known value/range for each indicator
- Signal level (critical/elevated/moderate/low)
- Trend direction
- A 2-3 sentence assessment comparing current reality to the threshold

The 12 indicators: Global Temperature, Greenhouse Gas Levels, Sea Level Rise, Ocean Heat Content, Ocean Acidity, Ice Sheets, Glaciers, Arctic Sea Ice, Snow Cover, Permafrost, Earth's Energy Balance, Precipitation & Drought Patterns.

Results are saved to `data/thresholds.json` and restored on restart. Click **Refresh Thresholds** to update with a fresh assessment.

### Local Monitor
Generates a country-specific risk assessment for whichever country you selected in Intake → Your Country / Region. Analyses 8 sectors: Political Stability & Governance, Economic Health, Food & Water Security, Energy Infrastructure, Healthcare System, Climate Vulnerability, Social Cohesion, Supply Chain Resilience.

Each sector shows a collapse rate bar, signal badge, trend arrow, current status, and the most significant recent development. Three additional sections cover:
- **Unique Risk Factors** — what makes this country specifically vulnerable that may not apply elsewhere
- **Stabilizing Factors** — genuine buffers and strengths
- **Watch Items** — specific upcoming events or thresholds to monitor

If you switch countries after running an assessment, a warning banner appears with a prompt to refresh. Results saved to `data/local_monitor.json`.

### Archive
Full searchable article list. Filter by topic dropdown, search titles and snippets. Articles tagged `GDELT` came from the GDELT archive rather than DuckDuckGo.

### Sources
Manage the news outlets the app searches. All sources are stored in `sources.json` in the app folder — your changes persist across app updates. Organized into tabs by category:

- **Global / Intl** — wire services and international outlets (Reuters, AP, BBC, Al Jazeera, Deutsche Welle, and outlets covering South America, Africa, Russia/Ukraine, Arctic, and environment specialists)
- **Journals** — scientific publications (Nature, Science, The Lancet, NEJM, PNAS)
- **Country tabs** — local outlets per country (US, UK, Canada, Australia, Germany, France, India, Japan)

To add a source: enter the display name and domain (e.g. `spiegel.de`), click **[+] Add**. To remove: click **[x] Remove** next to any entry. Changes save immediately. Removing a source stops it being used in future collections — existing articles stay in your archive.

---

## Recurring Collection

The **Date Window** selector in Intake → Collection Run is always visible. Pick the window you want and click Collect — the deduplication system automatically skips anything already in your archive, so you can run the same window multiple times safely.

**Common patterns:**
- **Daily top-up** — select Today, click Collect. Fast with DuckDuckGo.
- **Weekly catch-up** — select 7 days, click Collect.
- **Adding a new topic** — enable the topic in Tracked Topics, select 90 days or more, click Collect. Only the new topic's articles come through since the others are already archived.
- **Going back further** — select 6 months or 1 year and collect. Existing articles are skipped, only new ones are added.
- **Specific historical month** — use the GDELT Historical Collection card at the bottom of Intake. Pick year and month, click Fetch. Coverage goes back to February 2015.

Click **[o] Collect** in the top bar (visible from any view except Intake) to jump straight to a collection run with your current settings.

---

## Troubleshooting

**Server shows OFFLINE**
Make sure `server.py` is running. On Windows, check that the command window from `start.bat` is still open. On Mac/Linux, run `python3 server.py` in a terminal.

**LM Studio shows OFFLINE**
Open LM Studio → Developer tab → click Start Server. Confirm a model is loaded in the dropdown at the top.

**"Could not parse JSON" in Patterns, Thresholds, or Local Monitor**
The model struggled to produce valid JSON. Try again — it's probabilistic and often works on the second attempt. If it fails consistently, try a larger or more capable model. Qwen2.5-14B is the most reliable for structured output. Phi-3.5-mini will struggle with the complexity of these prompts.

**Collection returns 0 articles**
- DuckDuckGo may be rate-limiting — wait a few minutes and try again
- Try switching to GDELT or Both in the Ingest Source setting
- Check that at least one topic is enabled

**GDELT returns no results or fewer results than expected**
GDELT is a free public API with no guaranteed uptime or rate limits. A few things to check:
- Look at the server console window for `GDELT 429` messages — these mean you were rate-limited
- Wait 5–10 minutes and try again — GDELT rate limits typically reset quickly
- Switch to DuckDuckGo temporarily if GDELT is consistently unresponsive
- Check `data/failed_queries.json` — any queries that exhausted all retries are saved there

**Red "GDELT queries failed" banner appears in Intake**
This is normal during large GDELT collections. The app saves every query that failed after all retry attempts to `data/failed_queries.json`. Options:
- Click **[>] Rerun Failed** to replay them immediately. The app will retry each one with the same date window that was originally used.
- Wait a few minutes first — GDELT rate limits reset and the retry is more likely to succeed
- Click **[x] Dismiss** if you don't need those specific queries (they'll be removed from the list permanently)
- The failed list persists across restarts, so you can close the app, come back later, and retry then

**Browser shows "React is not defined"**
React is bundled inside the HTML file — this shouldn't happen if you're using the current version. Make sure you have the latest `collapse-monitor.html` from the repository.

**Maps tab shows 0 articles mapped**
The Event Map matches article sources to geographic coordinates using outlet display names and domains. If you collected articles primarily from sources not in the built-in lookup (very regional or niche outlets), they may not map. Check the Archive tab to confirm articles were collected, then try adding those outlets in the Sources tab so the map recognizes them.

**Maps tab crashes or Sector Network is empty**
Make sure you have articles collected before opening Event Map or Risk Density. The Sector Network requires a completed Pattern Analysis run.

---

## Context Windows and Token Limits

This is the most important configuration detail to get right. If your model's context window is too small, the Interrogate and Patterns views will fail or return truncated garbage.

### How the app uses your model

The app makes two kinds of LM calls:

**Interrogate view** — takes your question, scores every article in your archive by keyword relevance, picks the top 40, formats them as a numbered list (top 12 include the article snippet), and sends that block to the model along with your question. The model is asked to answer and cite articles by number.

**Patterns view** — takes the 12 most recent articles per topic (up to 15 topics × 12 = 180 articles worth of titles and dates), plus a summary of totals per topic, then asks the model to return a structured JSON object covering all sectors.

### Token estimates

| Call | Input tokens | Output limit | Total needed |
|---|---|---|---|
| Interrogate | ~2,200 | 3,000 | **~5,500** |
| Patterns | ~4,000 | 4,000 | **~8,000** |
| Thresholds | ~2,500 | 4,000 | **~6,500** |
| Local Monitor | ~2,500 | 4,000 | **~6,500** |

These are estimates assuming a moderate archive size. With thousands of articles the context stays capped — the app sends the top 40 articles for Interrogate, 12 per topic for Patterns, and the 20 most recent articles for Thresholds and Local Monitor.

### Context window requirements by model

| Model | Context window | Works? |
|---|---|---|
| Phi-3.5-mini | 4,096 | ⚠️ Too small — both views will fail or truncate |
| Gemma-2-2B | 8,192 | ✓ Adequate for both views |
| Gemma-2-9B | 8,192 | ✓ Adequate for both views |
| Llama-3.1-8B | 8,192 | ✓ Adequate for both views |
| Qwen2.5-14B | 32,768 | ✓ Plenty of headroom |
| Mistral-Nemo | 128,000 | ✓ No constraint at all |

### Setting the context window in LM Studio

LM Studio defaults to a context window that may be smaller than the model's maximum. **You need to set this manually.**

1. Open LM Studio
2. Load your model
3. Go to the **My Models** tab → click your loaded model
4. Find **Context Length** (also called `n_ctx`) in the model settings panel
5. Set it to at least **8,192** for any model that supports it
6. For Qwen2.5-14B, set it to **16,384** or higher to give headroom
7. Click **Apply** and reload the model if prompted

> **Why LM Studio defaults low:** Larger context windows use more VRAM. LM Studio picks a conservative default to avoid out-of-memory errors. You'll need to raise it manually for this app to work correctly.

### Setting max_tokens in the app

The app sends `max_tokens: 3000` for Interrogate and `max_tokens: 4000` for Patterns, Thresholds, and Local Monitor. The higher limit for the structured views gives the model room to output complete JSON without truncation.

If your model is cutting off responses mid-sentence or mid-JSON, the context window is the likely cause (the model ran out of room), not `max_tokens`. Fix the context window in LM Studio first.

If you want to raise the output limits, search for `max_tokens` in `collapse-monitor.html` and adjust the values. Don't go above the model's actual context window minus the input size.

---

## Hardware Notes

The app itself uses almost no resources — it's a local web page talking to a Python server. The only heavy component is LM Studio running the AI model.

| RAM | Recommended setup |
|---|---|
| 8 GB | Gemma-2-2B (Q4). Limited analysis quality but works. Phi-3.5-mini has too small a context window for this app. |
| 12 GB | Llama-3.1-8B or Gemma-2-9B at Q4 quantization. Good quality. |
| 16 GB | Qwen2.5-14B or Mistral-Nemo. Best results. |
| 32 GB+ | Any model, including unquantized versions. |

GPU acceleration: LM Studio automatically uses your GPU (NVIDIA CUDA or Apple Metal) if available. Analysis that takes 2–3 minutes on CPU takes 10–20 seconds with GPU acceleration.

---

## File Structure for GitHub

```
.gitignore              ← exclude data/ folder (your articles stay local)
README.md               ← this file
collapse-monitor.html   ← entire UI, self-contained
server.py               ← local web server + search + API backend
requirements.txt        ← Python dependencies
sources.json            ← editable news source list (ships with app)
start.bat               ← Windows launcher
start.sh                ← Mac/Linux launcher
data/                   ← created automatically, excluded from Git
    articles.json       ← your collected articles
    settings.json       ← saved preferences and configuration
    failed_queries.json ← GDELT queries that need retry
    thresholds.json     ← saved planetary threshold assessments
    local_monitor.json  ← saved country-specific risk assessment
```

Recommended `.gitignore`:
```
data/
__pycache__/
*.pyc
.DS_Store
```

**`sources.json`** lives in the base folder (not `data/`) so it ships with the app as a versioned default. Your local edits to it via the Sources tab are saved back to the same file — they persist but are not tracked by Git, so pulling updates won't overwrite your customizations (Git only updates tracked files).

The `data/` folder contains your personal archive and all generated analysis — keep it local and out of the repository.

---

**Thresholds or Local Monitor shows stale data after switching country**
If you switch country in Intake after running a Local Monitor assessment, a warning banner appears on the Local tab. Click **[^] Refresh** to generate a new assessment for the selected country. The old data is replaced.

**Thresholds assessment seems out of date**
The assessment reflects the LLM's knowledge as of its training cutoff, supplemented by your collected articles. For the most current values, ensure you have recent articles collected (past 30–90 days) before running the assessment, and include climate-related topics in your active collection.

## Contributing and Feedback

Bug reports, feature requests, and questions are welcome through **GitHub Issues**.

**To report a bug:** open an issue and include:
- What you were doing when it happened
- What you expected vs what actually occurred
- Any error messages from the browser console (F12 → Console) or the server window
- Your OS, Python version, and which model you're running in LM Studio

**To request a feature or topic:** open an issue describing what you'd like and why. New collapse categories, additional news sources, UI improvements, and analysis enhancements are all fair game.

**To ask a question:** open an issue with the Question label. If you figured out the answer yourself, feel free to close it with a comment explaining the fix — it helps the next person who hits the same thing.

GitHub Issues: `https://github.com/b2futures/collapse-monitor/issues`
