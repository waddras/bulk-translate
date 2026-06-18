# Bulk Subtitle Translator

A self-hosted FastAPI service that translates subtitle files (SRT/ASS) to Arabic using the Gemini API. Designed to run as a systemd service on a Proxmox LXC alongside [bazarr-translator](https://github.com/waddras/bazarr-translator).

## Features

- **Web UI** — file browser, queue, live job log, quota dashboard, API key manager, settings editor
- **Blob architecture** — strips timestamps from all selected files, merges into one JSON payload, sends to Gemini in a single request, then reassembles per-file `.ar.srt` outputs
- **Global deduplication** — identical lines across all selected files are sent to Gemini only once, saving tokens and quota
- **Single-char noise filtering** — cues that are a single non-digit character (music notes, dashes, lone punctuation) are silently dropped; digit-only cues (e.g. `5`) survive
- **Model pool with OOS tracking** — rotates across multiple Gemini models with per-model daily RPD limits; marks a model Out-Of-Service after configurable failure threshold, resets at midnight
- **Multi-API-key support** — add multiple Gemini keys (stored by email label, key never displayed); service round-robins across active keys to multiply effective quota
- **Configurable limits** — chunk size, output token ceiling (both our splitter and Gemini's `maxOutputTokens`), retry attempts, cooldown, OOS threshold — all editable in the UI
- **Cancel support** — cancel a running job mid-way; fully translated files are still written
- **Shared DB** — shares `/opt/bazarr-translator/usage.db` with bazarr-translator so both services track the same daily quota

---

## Requirements

- Python 3.10+
- Gemini API key (free tier at [aistudio.google.com](https://aistudio.google.com))
- `bazarr-translator` already installed (shares its SQLite DB)

---

## Installation

### 1. Clone the repo

```bash
cd /opt
git clone https://github.com/waddras/bulk-translate
cd bulk-translate
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. Set your Gemini API key

Add it to `/etc/environment` (persists across reboots):

```bash
echo "GEMINI_API_KEY=your_key_here" >> /etc/environment
source /etc/environment
```

Or add keys via the **Keys** tab in the web UI after the service starts.

### 4. Install and start the systemd service

```bash
cat > /etc/systemd/system/bulk-translate.service << 'EOF'
[Unit]
Description=Bulk Subtitle Translator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bulk-translate
EnvironmentFile=/etc/environment
ExecStart=/opt/bulk-translate/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8091
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now bulk-translate
```

### 5. Verify

```bash
systemctl status bulk-translate
curl http://localhost:8091/api/usage
```

Open the UI at `http://<your-lxc-ip>:8091`

---

## Usage

1. **Browse** — navigate to the folder containing your `.srt` files, check the ones you want, they appear in the **Queue** sidebar
2. **Execute Batch** — click the button; the job starts in the background and you are taken to the **Log** tab automatically
3. **Monitor** — the log auto-refreshes every 2 seconds showing all 4 phases:
   - `PHASE 1` — parse files, build blob, dedup summary
   - `PHASE 2` — split into chunks
   - `PHASE 3` — translate via Gemini
   - `PHASE 4` — reassemble and write `.ar.srt` files next to originals
4. **Cancel** — click **Cancel Job** at any time; files that were fully translated before cancellation are still written

Output files are saved next to the originals with `.ar.srt` extension:
```
Haikyuu!! - S01E01.en.srt  →  Haikyuu!! - S01E01.ar.srt
```

---

## File Structure

```
bulk-translate/
├── main.py       — FastAPI app, all HTTP routes
├── config.py     — paths, default settings, live cfg dict
├── db.py         — SQLite usage/quota/OOS tracking + API key CRUD
├── logger.py     — logging setup + job state accessors
├── srt_pre.py    — subtitle parsing, tag stripping, noise filtering
├── blob.py       — blob construction, dedup, splitting, expansion
├── ai.py         — Gemini API calls, retry/fallback/OOS logic
├── srt_post.py   — reassemble translated cues into .ar.srt files
├── job.py        — 4-phase background job orchestration
├── ui.py         — HTML/JS single-page UI
└── requirements.txt
```

---

## Settings

All settings are editable live in the **Settings** tab and persisted to `/opt/bulk-translate/settings.json`.

| Setting | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `300` | Max blocks per chunk (0 = no block-count limit) |
| `CHARS_PER_TOKEN` | `3` | Chars-to-tokens divisor for output token estimation |
| `CHUNK_OUTPUT_TOKENS` | `6000` | Our splitter threshold in estimated output tokens (0 = disabled) |
| `GEMINI_MAX_OUTPUT_TOKENS` | `0` | Sent as `maxOutputTokens` to Gemini (0 = use model default) |
| `OOS_THRESHOLD` | `2` | Retry exhaustions per day before a model is marked Out-Of-Service |
| `RETRY_ATTEMPTS` | `5` | Max attempts per chunk per model before cycling to next model |
| `RETRY_COOLDOWN` | `10` | Seconds between retry attempts |
| `MAX_BLOB_LINES` | `10000` | Sanity cap on total cues per job |
| `MODEL_POOL` | see below | Ordered list of models with RPD and RPM limits |

### Default model pool (priority order)

| Model | RPD | RPM |
|---|---|---|
| `gemini-3.5-flash` | 20 | 5 |
| `gemini-2.5-flash` | 20 | 5 |
| `gemini-2.5-flash-lite` | 20 | 10 |
| `gemini-3.1-flash-lite` | 500 | 15 |

Models are tried in order; exhausted or OOS models are skipped. All reset at midnight (server time).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/api/translate-bulk` | Start a translation job `{"files": [...paths]}` |
| `GET` | `/api/job-status` | Current job state + log lines |
| `POST` | `/api/job/cancel` | Cancel the running job |
| `GET` | `/api/usage` | Daily quota for all models |
| `POST` | `/api/usage/{model}/reset-oos` | Clear OOS flag + failure count for a model |
| `POST` | `/api/usage/{model}/reset-usage` | Reset all usage counters for a model |
| `GET` | `/api/keys` | List saved API keys (emails only, no key values) |
| `POST` | `/api/keys` | Add a key `{"email": "...", "api_key": "..."}` |
| `DELETE` | `/api/keys/{id}` | Delete a key |
| `POST` | `/api/keys/{id}/toggle` | Enable/disable a key |
| `GET` | `/api/settings` | Get current settings |
| `POST` | `/api/settings` | Update settings |
| `GET` | `/api/browse?path=...` | Browse filesystem for SRT files |

---

## Updating

```bash
cd /opt/bulk-translate
git pull
systemctl restart bulk-translate
```

---

## Logs

```bash
journalctl -u bulk-translate -o cat -f
```
