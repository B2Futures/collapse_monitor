# Collapse Monitor v0.6

A local, offline-first intelligence tool for tracking systemic collapse signals — planetary thresholds, democratic backsliding, economic stress, geopolitical conflict, and community resilience. Aggregates news via DuckDuckGo and GDELT, enriches it with real-time data from FRED, NOAA, and AISStream, and uses a locally-running LLM (via LM Studio) to analyze patterns, answer questions, and score 28 early warning indicators of authoritarianism.

All analysis runs on your machine. No cloud AI. No subscriptions.

---

## What You Need

### Required (free)

| Component | Purpose | Free? |
|---|---|---|
| Python 3.9+ | Runs the local server | Yes |
| LM Studio | Runs the AI model locally | Yes |
| A local AI model | Does all analysis and Q&A | Yes |
| A browser | The UI | Yes |

### Optional API Keys (all free tiers available)

| Service | What it adds | Where to get it |
|---|---|---|
| **NOAA NCDC** | Real climate data (temperature, precipitation anomalies) for your local area | [ncdc.noaa.gov/cdo-web/token](https://www.ncdc.noaa.gov/cdo-web/token) — instant approval |
| **AISStream.io** | Live vessel tracking near 8 major ports — shipping congestion indicator | [aisstream.io](https://aisstream.io) — free tier available |

Keys are entered on the **Intake** page and stored locally in `data/api_keys.json`. They never leave your machine except to hit the respective APIs.

> **FRED economic data** (unemployment, inflation, yield curve, oil prices, consumer sentiment) requires no API key — it uses FRED's public CSV endpoint automatically.

---

## Step 1 — Install Python

**Windows:** Download from [python.org](https://www.python.org/downloads/). During install, check **"Add Python to PATH"**.

**Mac:** Python 3 is usually pre-installed. Check with `python3 --version` in Terminal. If not: `brew install python3` or download from [python.org](https://www.python.org/downloads/).

**Linux:** `sudo apt install python3 python3-pip` (Debian/Ubuntu) or equivalent.

Verify:
```bash
python3 --version   # Mac/Linux
python --version    # Windows
```

---

## Step 2 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or individually:
```bash
pip install flask flask-cors ddgs requests websocket-client
```

> `websocket-client` is required for AISStream vessel tracking. If you skip it, the server will attempt to auto-install it the first time you use the AIS endpoint.

---

## Step 3 — Download LM Studio

1. Go to [lmstudio.ai](https://lmstudio.ai) and download for your OS
2. Install and open it

---

## Step 4 — Download a Model

In LM Studio, click the **Search** tab and download one of these:

| Model | RAM needed | Quality | Notes |
|---|---|---|---|
| **Qwen2.5-14B-Instruct** | 16 GB | ★★★★★ | Best overall. Strongest at structured JSON output. |
| **Gemma-4-12B** | 16 GB | ★★★★☆ | Fast, accurate, good balance of JSON and prose. |
| **Mistral-Nemo-Instruct-2407** | 16 GB | ★★★★☆ | Excellent at summarization and Q&A. |
| **Llama-3.1-8B-Instruct** | 10 GB | ★★★★☆ | Good balance of speed and quality. |
| **Gemma-2-9B-Instruct** | 10 GB | ★★★★☆ | Fast and accurate. Good for Interrogate. |
| **Phi-3.5-mini-instruct** | 6 GB | ★★★☆☆ | 8 GB RAM minimum. Struggles with complex JSON. |
| **Gemma-2-2B-Instruct** | 4 GB | ★★☆☆☆ | Last resort for very low RAM. |

Choose **Q4_K_M** or **Q5_K_M** quantization — compressed versions that fit in less RAM with minimal quality loss.

---

## Step 5 — Start the LM Studio Server

1. Click the **Developer** tab (`<->` icon)
2. Enable **CORS** (required — browser will block connections without it)
3. Click **Start Server** → turns green on port 1234
4. Select your downloaded model from the dropdown
5. Set context length to at least **8,192** (16,384+ for Qwen2.5-14B)

---

## Step 6 — Get the Files

```bash
git clone https://github.com/b2futures/collapse-monitor.git
cd collapse-monitor
```

Or download ZIP from GitHub → Code → Download ZIP.

File structure:
```
collapse-monitor/
├── collapse-monitor.html   ← entire UI (single self-contained file)
├── server.py               ← local server, data collection, API integrations
├── requirements.txt        ← Python dependencies
├── sources.json            ← editable news source list
├── start.bat               ← Windows launcher
├── start.sh                ← Mac/Linux launcher
└── data/                   ← created automatically, not tracked by Git
```

---

## Step 7 — Run It

**Windows:** Double-click `start.bat`. A command window opens (keep it running).

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

Or manually:
```bash
python3 server.py
```

Then open `http://localhost:5000` in your browser.

---

## Step 8 — Configure on First Run

Click **Intake** in the left sidebar.

### Connection Settings
| Setting | Default |
|---|---|
| Server URL | `http://localhost:5000` |
| LM Studio URL | `http://localhost:1234` |
| Model Name | Auto-detected from LM Studio on load |

Click **Test Connections** — both should turn green.

### Local Location
Enter your **City**, **County**, and **State** — used by the Local tab and Resilience local scale. Saves automatically on blur.

### Optional API Keys (bottom of Intake page)
- **NOAA NCDC Token** — paste your token, click Save. The app will find the nearest weather station in your state and start pulling real climate data.
- **AISStream.io API Key** — paste your key, click Save. Click ↻ to take a 20-second vessel snapshot near major global ports.

---

## Navigation

**Monitor** → signal overview dashboard  
**Interrogate** → ask questions about your article archive  
**Patterns** → structured analysis across all 15 topics  
**Thresholds** → 19 planetary boundaries + real-time economic indicators  
**Resilience** → societal resilience at World / National / Local scale  
**Backslide** → 28-indicator democratic backsliding tracker (Britt's 14 + Eco's 14)  
**Map** → geographic event extraction from article archive  
**Intake** → collection settings, location, API keys  
**Keywords** → manage tracked keywords  
**Sources** → manage trusted news domains  
**Archive** → searchable article database  

---

## Tabs in Detail

### Monitor
Overview dashboard showing article counts, signal levels, articles by topic (national and local columns), top sources, and recent articles. Source filter (All / Trusted / Unverified) controls which articles appear.

### Interrogate
Ask plain-English questions about your collected data. Uses both national archive and local articles. The header shows exactly how many articles from each pool are included. Click any topic to focus the context.

### Patterns
Structured collapse analysis across all 15 sectors. Shows collapse rates (0–100%), trend direction, signal levels, interconnections, leading indicators, emerging threats, and a dated event timeline. Click any indicator to drill supporting articles.

### Thresholds
**Economic Indicators** (top): 8 real-time FRED signals with z-scores and sparklines — Unemployment, CPI, Federal Funds Rate, Yield Curve, Jobless Claims, WTI Crude, Dollar Index, Consumer Sentiment. Auto-refreshed every 24 hours, no API key required.

**Planetary Thresholds** (below): 19 indicators including the original 12 climate boundaries plus AMOC, Amazon Rainforest, Ozone, Freshwater, Biodiversity, Nitrogen Cycle, Permafrost, and Democratic Backsliding.

### Resilience
Three-scale societal resilience analysis:
- **World** — global resilience from national archive: Strengths, Key Stressors, Stabilizing Factors, Watch Items
- **National** — country-specific: Unique Risk Factors, Stabilizing Factors, Watch Items
- **Local** — community level: Community Impacts, Local Risk Factors, Stabilizing Factors, Watch Items (next 30 days), Local Weather & Climate

All scales cover 7 sectors: Governance, Economic Health, Food & Water, Energy & Infrastructure, Public Health, Social Cohesion, Housing & Cost of Living.

### Backslide
Scores each of 28 indicators of democratic backsliding against your article archive:
- **Britt's 14 Early Warning Signs of Fascism** — Nationalism, Human Rights Disdain, Scapegoating, Military Supremacy, Sexism, Media Control, Security Obsession, Religion/Government Fusion, Corporate Protection, Labor Suppression, Anti-Intellectualism, Crime/Punishment Obsession, Cronyism, Election Fraud
- **Eco's 14 Features of Ur-Fascism** — Cult of Tradition, Rejection of Modernism, Cult of Action, Disagreement as Treason, Fear of Difference, Middle Class Appeal, Plot Obsession, Enemy Paradox, Pacifism as Treason, Contempt for the Weak, Hero Cult, Machismo, Selective Populism, Newspeak

Each card shows a score (0–100), signal level, and 2-sentence assessment. Click any card to drill supporting articles.

### Map
Extracts geographic events from your article archive and plots them on a Leaflet map. 10 event types: Disease, Famine, Drought, Flood, Conflict, Displacement, Infrastructure, Economic, Fire, Storm. Marker size scales with severity. Filter by type and date range. Events are aggregated (same type + location + date window = one marker).

---

## Data Files

All data lives in `data/` and is excluded from Git:

| File | Contents |
|---|---|
| `articles.json` | National/global collected articles |
| `settings.json` | Preferences, keywords, location, LM Studio config |
| `sources.json` | Trusted news domains (tracked by Git — back up before pulling) |
| `api_keys.json` | NOAA and AISStream API keys |
| `fred_cache.json` | FRED economic data cache (24h TTL) |
| `noaa_cache.json` | NOAA climate data cache (24h TTL) |
| `ais_cache.json` | AISStream vessel snapshot cache (6h TTL) |
| `thresholds.json` | Saved planetary threshold assessment |
| `resilience.json` | Saved resilience analysis |
| `fascism.json` | Saved backslide assessment |
| `events.json` | Map events + processed article index |
| `local_articles.json` | Local community articles |
| `local_briefing.json` | Saved local briefing |
| `failed_queries.json` | GDELT queries that exhausted retries |

---

## Python Dependencies

```
flask           - web server
flask-cors      - cross-origin requests (browser ↔ server)
ddgs            - DuckDuckGo news search
requests        - HTTP client
websocket-client - AISStream.io live vessel tracking
```

Install all at once:
```bash
pip install -r requirements.txt
```

> `csv`, `io`, `statistics`, `urllib` — standard library, no install needed.

---

## LM Studio Context Window Requirements

| Analysis | Min context | Recommended |
|---|---|---|
| Interrogate | 8,192 | 16,384 |
| Patterns | 16,384 | 32,768 |
| Thresholds (19 indicators) | 16,384 | 32,768 |
| Resilience | 8,192 | 16,384 |
| Backslide (28 indicators) | 16,384 | 32,768 |
| Map extraction (per chunk) | 4,096 | 8,192 |

Set context length in LM Studio: My Models → your model → Context Length → Apply.

---

## Hardware

| RAM | Recommended setup |
|---|---|
| 8 GB | Gemma-2-2B Q4. Limited quality but functional. |
| 12 GB | Llama-3.1-8B or Gemma-2-9B at Q4. Good quality. |
| 16 GB | Qwen2.5-14B, Gemma-4-12B, or Mistral-Nemo. Best results. |
| 32 GB+ | Any model including unquantized. |

GPU acceleration (NVIDIA CUDA or Apple Metal) reduces analysis time from 2–3 minutes to 10–20 seconds.

---

## Collection

### Sources
- **DuckDuckGo** — fast, good for recent news (past 1–12 months)
- **GDELT** — global archive, 65+ languages, slower, subject to rate limiting

### Rate Limiting
GDELT throttles large collections with HTTP 429 errors. Failed queries save to `data/failed_queries.json`. Use **[>] Rerun Failed** after waiting 5–10 minutes.

### Deduplication
Already-collected articles are skipped. Safe to run the same date window multiple times.

---

## Troubleshooting

**Server shows OFFLINE** — make sure `server.py` is still running.

**LM Studio shows OFFLINE** — open LM Studio → Developer tab → enable CORS → Start Server.

**Model dropdown shows nothing** — click the ↻ next to the model selector in the bottom-left sidebar. LM Studio must have its server running and a model loaded.

**"Could not parse JSON"** — the model failed to produce valid JSON. Try again — it's probabilistic. If it fails consistently, use a larger or more capable model. Qwen2.5-14B is most reliable for structured output.

**NOAA returns "No stations found"** — make sure your State is set correctly on Intake. The state name must match (e.g. `Wisconsin` not `WI`).

**AIS returns an error about websocket** — run `pip install websocket-client` manually, then restart `server.py`.

**Map shows no events** — click **[+] Extract Events** on the Map tab. Events are extracted on demand, not automatically during collection.

**Source filter shows "+N untagged"** — run **[~] Retag All Articles** in the Sources tab to stamp trust badges on your existing archive.

---

## .gitignore

```
data/
__pycache__/
*.pyc
.DS_Store
```

---

## Issues and Feedback

GitHub Issues: `https://github.com/b2futures/collapse-monitor/issues`

When reporting a bug, include: what you were doing, what happened, any error messages from browser console (F12 → Console) or the server window, your OS, Python version, and which LLM model you're running.
