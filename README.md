# 🎬 YouTube Shorts Automation

Automatically generate complete, publish-ready YouTube Shorts from a single topic string. The pipeline writes a script with AI, downloads matching stock footage, synthesizes a voiceover, transcribes subtitles, and composes the final video — all without touching a video editor.

---

## ✨ Features

- **AI script generation** via Groq (LLaMA 3.3 70B) — 5 scenes, ~40–50 s narration
- **Stock video download** from Pixabay (free, no attribution required for most content)
- **Text-to-speech voiceover** via Piper TTS (offline, high-quality neural voices)
- **Auto-subtitles** via AssemblyAI (word-level accuracy, burned directly onto frames)
- **Frame-accurate subtitle rendering** using OpenCV — no ImageMagick dependency
- **Reliable audio muxing** via direct ffmpeg call — avoids MoviePy Windows audio bugs
- **Web interface** (Flask) with live per-stage progress tracking
- **Batch processing** from a JSON topic list
- **Optimised runner** with parallel downloads and script caching

---

## 📁 Project Structure

```
shorts-video-automation/
│
├── ysa_pix.py                 # ← Core pipeline (main script)
├── optimized_automation.py    # ← Parallel downloads + caching + batch
├── batch_generator.py         # ← Simple batch runner from a JSON file
├── web_interface.py           # ← Flask web UI
│
├── requirements.txt
├── setup.py
├── README.md
│
├── output/                    # Final rendered videos (auto-created)
├── temp/                      # Intermediate files (auto-created)
│   └── cache/                 # Cached scripts (optimized runner only)
└── assets/                    # Reserved for future static assets
```

---

## 🔧 Prerequisites

### 1 — Python 3.9+

```bash
python --version
```

### 2 — ffmpeg (system binary)

ffmpeg handles audio conversion and final muxing.

**Windows:** Download the latest build from https://www.gyan.dev/ffmpeg/builds/  
Extract and add the `bin/` folder to your system PATH.

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

> ⚠️ **Windows users:** The bundled ffmpeg from MoviePy (vintage 2013 build) is too old. Download a current build (2020+) from the link above and make sure `ffmpeg` and `ffprobe` resolve from your terminal before continuing.

### 3 — Piper TTS (offline neural voice)

1. Download the latest release for your platform from https://github.com/rhasspy/piper/releases
2. Extract the archive and note the path to the `piper` executable
3. Download a voice model — the project uses `en_US-lessac-medium`:
   ```
   https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium
   ```
   Download both `en_US-lessac-medium.onnx` and `en_US-lessac-medium.onnx.json`  
   and place them in a `piper/` folder next to your scripts.

Test it:
```bash
echo "Hello world" | piper --model piper/en_US-lessac-medium.onnx --output_file test.wav
```

---

## 📦 Installation

```bash
# Clone or download the project
git clone https://github.com/narmesh/shorts-video-automation
cd shorts-video-automation

# Install Python dependencies
pip install -r requirements.txt
```

---

## 🔑 API Keys

You need three free API keys. Set them as environment variables or pass them as CLI flags.

| Service | Purpose | Free tier |
|---|---|---|
| [Groq](https://console.groq.com) | Script generation (LLM) | Generous free tier |
| [Pixabay](https://pixabay.com/api/docs/) | Stock video search & download | 500 req/hour |
| [AssemblyAI](https://www.assemblyai.com) | Speech-to-text for subtitles | 5 hours free/month |

### Set as environment variables (recommended)

**Windows (PowerShell):**
```powershell
$env:GROQ_API_KEY      = "your_groq_key"
$env:PIXABAY_API_KEY   = "your_pixabay_key"
$env:ASSEMBLYAI_API_KEY = "your_assemblyai_key"
```

**macOS / Linux:**
```bash
export GROQ_API_KEY="your_groq_key"
export PIXABAY_API_KEY="your_pixabay_key"
export ASSEMBLYAI_API_KEY="your_assemblyai_key"
```

Or add them to a `.env` file and load with `python-dotenv` if preferred.

---

## 🚀 Usage

### Option 1 — Main script (single video)

```bash
python ysa_pix.py "Amazing facts about the human brain"
```

With explicit keys:
```bash
python ysa_pix.py "Deep sea creatures" \
  --groq-key YOUR_KEY \
  --pexels-key YOUR_KEY \
  --assemblyai-key YOUR_KEY \
  --cleanup
```

| Flag | Description |
|---|---|
| `--groq-key` | Groq API key (overrides env var) |
| `--pixabay-key` | Pixabay API key (overrides env var) |
| `--assemblyai-key` | AssemblyAI API key (overrides env var) |
| `--cleanup` | Delete temp files after completion |

---

### Option 2 — Optimized runner (parallel downloads + caching)

```bash
python optimized_automation.py "Why octopuses are basically aliens" --quality high
```

| Flag | Default | Description |
|---|---|---|
| `--quality` | `medium` | `fast` / `medium` / `high` — controls FPS and parallel workers |
| `--no-cache` | off | Disable script caching (always regenerate) |
| `--workers` | `3` | Number of parallel video download threads |

**Quality presets:**

| Preset | FPS | Workers | Best for |
|---|---|---|---|
| `fast` | 24 | 5 | Quick drafts |
| `medium` | 30 | 3 | Balanced |
| `high` | 30 | 2 | Final renders |

---

### Option 3 — Batch generator

Create a `topics.json` file:
```json
{
  "topics": [
    "The immortal jellyfish that can live forever",
    "Why honey never expires",
    "The shortest war in history lasted 38 minutes",
    "Animals that can survive in space",
    "The deepest point in the ocean"
  ]
}
```

Run:
```bash
python batch_generator.py topics.json 60
```

The second argument is the delay in seconds between videos (default `60`). Results are saved to `output/batch_results.json`.

---

### Option 4 — Web interface

```bash
pip install flask          # if not already installed
python web_interface.py
```

Open **http://localhost:5000** in your browser.

Features:
- Topic text area with example chips
- Live stage-by-stage progress bar (Script → Videos → Audio → Subtitles → Editing)
- One-click download when complete
- Handles multiple concurrent jobs via background threads

---

## ⚙️ Configuration

All settings live in the `Config` dataclass at the top of `ysa_pix.py`:

```python
@dataclass
class Config:
    GROQ_API_KEY:      str  = ""
    PIXABAY_API_KEY:   str  = ""
    ASSEMBLYAI_API_KEY: str = ""

    VIDEO_WIDTH:    int  = 1080
    VIDEO_HEIGHT:   int  = 1920   # 9:16 vertical
    VIDEO_DURATION: int  = 45     # Target seconds
    FPS:            int  = 30

    PIPER_MODEL: str = "piper/en_US-lessac-medium.onnx"
    PIPER_PATH:  str = "piper"    # Path to piper binary

    GROQ_MODEL: str = "llama-3.3-70b-versatile"
```

---

## 🏗️ Pipeline Overview

```
Topic string
    │
    ▼
┌─────────────────────────────┐
│  1. Script Generation       │  Groq LLM → 5 scenes (narration + search term + duration)
└──────────────┬──────────────┘
               │
    ▼
┌─────────────────────────────┐
│  2. Stock Video Download    │  Pixabay API → search per scene → download MP4
└──────────────┬──────────────┘
               │
    ▼
┌─────────────────────────────┐
│  3. Voiceover (TTS)         │  Piper → WAV → ffmpeg → MP3
└──────────────┬──────────────┘
               │
    ▼
┌─────────────────────────────┐
│  4. Subtitle Generation     │  WAV → AssemblyAI → SRT file
└──────────────┬──────────────┘
               │
    ▼
┌─────────────────────────────┐
│  5. Video Composition       │  MoviePy: crop → resize → loop/trim each clip
│                             │  OpenCV: burn subtitles onto frames
│                             │  ffmpeg: mux silent video + MP3 audio → final MP4
└──────────────┬──────────────┘
               │
    ▼
  output/video_<timestamp>.mp4
```

---

## 🛠️ Troubleshooting

### No audio in output video

- Confirm `ffmpeg` on your PATH is a **2020+ build** — the old MoviePy-bundled 2013 binary causes AAC encoder failures
- Check the temp folder for `*_audio.mp3` — if it's missing, the Piper → ffmpeg conversion step failed
- Run `ffprobe temp/<video_id>_audio.mp3` manually to verify the file is valid

### Video is only a few seconds long

- The script generator returned very short narrations — check the word count log printed after "Script generated"
- If total words are under 100, re-run; Groq occasionally ignores word-count instructions
- You can also increase `max_tokens` in `generate_script()` if the JSON is getting truncated

### Subtitles not appearing

- Confirm the `.srt` file exists in `temp/` after the AssemblyAI step
- AssemblyAI receives the `.wav` file — make sure it was created by Piper before the MP3 conversion
- Check your AssemblyAI API key and remaining free-tier hours

### `PIL.Image has no attribute ANTIALIAS`

Already patched at the top of `ysa_pix.py`. If you still see it, ensure you imported `ysa_pix` before any other MoviePy import.

### Pixabay returns no results for a scene

The script generator's `search_term` is passed directly to Pixabay. If the term is too specific, the searcher automatically retries with only the first word of the query as a fallback. If both fail, that scene is skipped and the remaining clips fill the video.

### Web interface progress gets stuck

Flask uses background threads — on Windows, make sure `debug=False` in `app.run()`. The debug reloader spawns a second process that breaks daemon threads.

---

## 📝 Output

Every run produces a single file:

```
output/
└── video_<unix_timestamp>.mp4   # 1080×1920, H.264, AAC, ~40–50 s
```

Batch runs additionally produce:
```
output/
└── batch_results.json           # { successful: [...], failed: [...] }
```

---

## 📋 Dependencies Summary

| Package | Version | Purpose |
|---|---|---|
| `groq` | ≥0.9.0 | LLM API client |
| `moviepy` | ≥1.0.3 | Video clip editing |
| `opencv-python` | ≥4.8.0 | Subtitle frame rendering |
| `Pillow` | ≥9.0.0 | Image processing (MoviePy dependency) |
| `numpy` | ≥1.24.0 | Frame array operations |
| `requests` | ≥2.31.0 | HTTP calls to Pixabay + AssemblyAI |
| `flask` | ≥3.0.0 | Web UI (optional) |
| `piper` | — | TTS binary (install separately) |
| `ffmpeg` | — | Audio conversion + muxing (install separately) |

---

## 📄 License

MIT — do whatever you want, attribution appreciated.
