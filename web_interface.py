"""
Simple Web Interface for Shorts Video Automation
Run with: python web_interface.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template_string, request, jsonify, send_file

from ysa_pix import YouTubeShortsAutomation, Config

import threading
import time
from pathlib import Path
import json

app = Flask(__name__)

# Store job status
jobs = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Shorts Automation</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #000000;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #fff;
            position: relative;
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(255, 62, 28, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(255, 62, 28, 0.05) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }

        .container {
            background: rgba(15, 15, 15, 0.6);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 56px;
            max-width: 640px;
            width: 100%;
            position: relative;
            z-index: 1;
        }

        .container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255, 62, 28, 0.5), transparent);
        }

        h1 { 
            color: #ffffff; 
            margin-bottom: 6px; 
            font-size: 32px; 
            font-weight: 700;
            letter-spacing: -1.2px;
            line-height: 1.1;
        }

        .subtitle { 
            color: rgba(255, 255, 255, 0.4); 
            margin-bottom: 48px; 
            font-size: 14px;
            font-weight: 400;
            letter-spacing: 0.2px;
        }

        .form-group { margin-bottom: 28px; }

        label { 
            display: block; 
            margin-bottom: 10px; 
            color: rgba(255, 255, 255, 0.6); 
            font-weight: 500;
            font-size: 12px;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }

        textarea {
            width: 100%;
            padding: 18px 20px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            font-size: 15px;
            color: #ffffff;
            transition: border-color 0.15s ease, background 0.15s ease;
            resize: vertical;
            min-height: 140px;
            font-family: inherit;
            line-height: 1.6;
        }

        textarea::placeholder {
            color: rgba(255, 255, 255, 0.25);
        }

        textarea:focus { 
            outline: none; 
            border-color: #ff3e1c;
            background: rgba(0, 0, 0, 0.6);
        }

        button {
            background: #ff3e1c;
            color: #ffffff;
            border: none;
            padding: 18px 32px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: background 0.15s ease;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            position: relative;
            overflow: hidden;
        }

        button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
            transition: left 0.5s;
        }

        button:hover::before {
            left: 100%;
        }

        button:hover { 
            background: #e6381a;
        }

        button:disabled { 
            background: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.3);
            cursor: not-allowed; 
        }

        .status { 
            margin-top: 48px; 
            display: none; 
        }

        .status.processing,
        .status.success,
        .status.error { 
            display: block; 
        }

        .status-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }

        .status-text { 
            color: rgba(255, 255, 255, 0.5); 
            font-weight: 500;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .progress { 
            height: 1px; 
            background: rgba(255, 255, 255, 0.06); 
            overflow: hidden;
            margin-bottom: 32px;
            position: relative;
        }

        .progress-bar {
            height: 100%;
            background: #ff3e1c;
            width: 0%;
            transition: width 0.3s linear;
            box-shadow: 0 0 10px rgba(255, 62, 28, 0.5);
        }

        .stage-list { 
            display: flex;
            flex-direction: column;
            gap: 1px;
            background: rgba(255, 255, 255, 0.03);
        }

        .stage-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px 24px;
            background: rgba(0, 0, 0, 0.3);
            opacity: 0;
            transform: translateX(-20px);
            transition: all 0.25s ease;
            position: relative;
        }

        .stage-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 2px;
            background: transparent;
            transition: background 0.2s ease;
        }

        .stage-item.visible {
            opacity: 1;
            transform: translateX(0);
        }

        .stage-item.active::before {
            background: #ff3e1c;
        }

        .stage-item.completed::before {
            background: #10b981;
        }

        .stage-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .stage-icon {
            width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .stage-icon svg {
            width: 100%;
            height: 100%;
            stroke: rgba(255, 255, 255, 0.3);
            transition: stroke 0.2s ease;
        }

        .stage-item.active .stage-icon svg {
            stroke: #ff3e1c;
        }

        .stage-item.completed .stage-icon svg {
            stroke: #10b981;
        }

        .stage-label {
            color: rgba(255, 255, 255, 0.4);
            font-size: 13px;
            font-weight: 500;
            letter-spacing: 0.3px;
        }

        .stage-item.active .stage-label {
            color: rgba(255, 255, 255, 0.9);
        }

        .stage-item.completed .stage-label {
            color: rgba(255, 255, 255, 0.5);
        }

        .stage-percent {
            color: rgba(255, 255, 255, 0.3);
            font-size: 12px;
            font-weight: 600;
            min-width: 45px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .stage-item.active .stage-percent {
            color: #ff3e1c;
        }

        .stage-item.completed .stage-percent {
            color: #10b981;
        }

        .download-link {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            margin-top: 32px;
            padding: 18px 32px;
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            text-decoration: none;
            font-weight: 600;
            font-size: 13px;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            transition: background 0.15s ease;
            width: 100%;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .download-link:hover { 
            background: rgba(255, 255, 255, 0.08);
        }

        .examples { 
            margin-top: 48px; 
            padding: 28px; 
            background: rgba(0, 0, 0, 0.3); 
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .examples h3 { 
            font-size: 11px; 
            color: rgba(255, 255, 255, 0.4); 
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }

        .example-chip {
            display: inline-block;
            padding: 10px 18px;
            margin: 4px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            transition: all 0.15s ease;
            letter-spacing: 0.3px;
        }

        .example-chip:hover { 
            background: rgba(255, 62, 28, 0.08);
            border-color: rgba(255, 62, 28, 0.3); 
            color: #ff3e1c;
        }

        .error-message {
            margin-top: 24px;
            padding: 18px 20px;
            background: rgba(220, 38, 38, 0.08);
            border: 1px solid rgba(220, 38, 38, 0.2);
            color: #ff6b6b;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: 0.2px;
        }

        @media (max-width: 600px) {
            .container { padding: 40px 28px; }
            h1 { font-size: 26px; }
            .subtitle { font-size: 13px; }
        }

        /* Custom scrollbar */
        textarea::-webkit-scrollbar {
            width: 8px;
        }

        textarea::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.02);
        }

        textarea::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
        }

        textarea::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.15);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube Shorts Automation</h1>
        <p class="subtitle">Generate viral shorts in minutes with AI</p>

        <form id="videoForm">
            <div class="form-group">
                <label for="topic">Video Topic</label>
                <textarea
                    id="topic"
                    name="topic"
                    placeholder="Enter your video topic... e.g., 'The immortal jellyfish that can live forever'"
                    required
                ></textarea>
            </div>
            <button type="submit" id="submitBtn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                Generate Video
            </button>
        </form>

        <div id="status" class="status">
            <div class="status-header">
                <div class="status-text" id="statusText">Processing...</div>
            </div>
            <div class="progress">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            <div class="stage-list" id="stageList"></div>
        </div>

        <div class="examples">
            <h3>Example Topics</h3>
            <span class="example-chip" onclick="setTopic('The immortal jellyfish that can live forever')">Immortal Jellyfish</span>
            <span class="example-chip" onclick="setTopic('Why honey never spoils')">Eternal Honey</span>
            <span class="example-chip" onclick="setTopic('The shortest war in history')">Shortest War</span>
            <span class="example-chip" onclick="setTopic('Animals that can survive in space')">Space Animals</span>
            <span class="example-chip" onclick="setTopic('The deepest point in the ocean')">Ocean Depths</span>
        </div>
    </div>

    <script>
        let jobId = null;
        let lastStages = {};
        let updateInterval = null;

        const STAGE_LABELS = [
            { 
                key: 'script', 
                label: 'Generating script',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>'
            },
            { 
                key: 'videos', 
                label: 'Downloading videos',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line></svg>'
            },
            { 
                key: 'audio', 
                label: 'Generating voiceover',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>'
            },
            { 
                key: 'subtitles', 
                label: 'Creating subtitles',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path><line x1="9" y1="10" x2="15" y2="10"></line><line x1="9" y1="14" x2="15" y2="14"></line></svg>'
            },
            { 
                key: 'editing', 
                label: 'Composing video',
                icon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"></path><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>'
            }
        ];

        const SVG_ICONS = {
            download: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
            error: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
        };

        function setTopic(topic) {
            document.getElementById('topic').value = topic;
        }

        function updateStageDisplay(stages) {
            const stageList = document.getElementById('stageList');
            
            // Create stage items if they don't exist
            if (stageList.children.length === 0) {
                stageList.innerHTML = STAGE_LABELS.map(s => `
                    <div class="stage-item" data-stage="${s.key}">
                        <div class="stage-left">
                            <span class="stage-icon">${s.icon}</span>
                            <span class="stage-label">${s.label}</span>
                        </div>
                        <span class="stage-percent">0%</span>
                    </div>
                `).join('');
            }

            // Update each stage
            STAGE_LABELS.forEach(s => {
                const pct = stages[s.key] || 0;
                const item = stageList.querySelector(`[data-stage="${s.key}"]`);
                const percentEl = item.querySelector('.stage-percent');
                
                // Show item if it has progress
                if (pct > 0 && !item.classList.contains('visible')) {
                    setTimeout(() => item.classList.add('visible'), 100);
                }
                
                // Update status classes
                item.classList.remove('active', 'completed');
                if (pct === 100) {
                    item.classList.add('completed');
                } else if (pct > 0) {
                    item.classList.add('active');
                }
                
                // Animate percentage change
                const currentPct = parseInt(percentEl.textContent) || 0;
                if (currentPct !== pct) {
                    animateValue(percentEl, currentPct, pct, 400);
                }
            });
            
            lastStages = { ...stages };
        }

        function animateValue(element, start, end, duration) {
            const range = end - start;
            const increment = range / (duration / 16);
            let current = start;
            
            const timer = setInterval(() => {
                current += increment;
                if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
                    current = end;
                    clearInterval(timer);
                }
                element.textContent = Math.round(current) + '%';
            }, 16);
        }

        function updateStatus(status, text, progress, stages) {
            const statusDiv = document.getElementById('status');
            const statusText = document.getElementById('statusText');
            const progressBar = document.getElementById('progressBar');

            statusDiv.className = 'status ' + status;
            statusText.textContent = text;

            if (progress !== undefined) {
                progressBar.style.width = progress + '%';
            }

            if (stages) {
                updateStageDisplay(stages);
            }
        }

        function checkJobStatus() {
            if (!jobId) return;

            fetch('/status/' + jobId)
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'processing') {
                        updateStatus('processing', data.message, data.progress, data.stages);
                        setTimeout(checkJobStatus, 3000);

                    } else if (data.status === 'completed') {
                        updateStatus('success', 'Video created successfully!', 100, data.stages);

                        if (!document.getElementById('downloadBtn')) {
                            const link = document.createElement('a');
                            link.id = 'downloadBtn';
                            link.href = '/download/' + jobId;
                            link.className = 'download-link';
                            link.innerHTML = SVG_ICONS.download + ' Download Video';
                            document.getElementById('status').appendChild(link);
                        }

                        document.getElementById('submitBtn').disabled = false;
                        jobId = null;

                    } else if (data.status === 'error') {
                        const errorHtml = `<div class="error-message">${SVG_ICONS.error} ${data.message}</div>`;
                        document.getElementById('status').insertAdjacentHTML('beforeend', errorHtml);
                        updateStatus('error', 'Generation failed', 0);
                        document.getElementById('submitBtn').disabled = false;
                        jobId = null;
                    }
                })
                .catch(err => {
                    const errorHtml = `<div class="error-message">${SVG_ICONS.error} Network error: ${err.message}</div>`;
                    document.getElementById('status').insertAdjacentHTML('beforeend', errorHtml);
                    updateStatus('error', 'Connection error', 0);
                    document.getElementById('submitBtn').disabled = false;
                    jobId = null;
                });
        }

        document.getElementById('videoForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const topic = document.getElementById('topic').value.trim();
            const submitBtn = document.getElementById('submitBtn');
            if (!topic) return;

            // Clean up previous state
            const old = document.getElementById('downloadBtn');
            if (old) old.remove();
            const stageList = document.getElementById('stageList');
            stageList.innerHTML = '';
            lastStages = {};

            submitBtn.disabled = true;
            updateStatus('processing', 'Initializing...', 0);

            fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic })
            })
            .then(r => r.json())
            .then(data => {
                if (data.job_id) {
                    jobId = data.job_id;
                    checkJobStatus();
                } else {
                    const errorHtml = `<div class="error-message">${SVG_ICONS.error} ${data.error || 'Failed to start generation'}</div>`;
                    document.getElementById('status').insertAdjacentHTML('beforeend', errorHtml);
                    updateStatus('error', 'Failed to start', 0);
                    submitBtn.disabled = false;
                }
            })
            .catch(err => {
                const errorHtml = `<div class="error-message">${SVG_ICONS.error} ${err.message}</div>`;
                document.getElementById('status').insertAdjacentHTML('beforeend', errorHtml);
                updateStatus('error', 'Request failed', 0);
                submitBtn.disabled = false;
            });
        });
    </script>
</body>
</html>
"""


# ============================================================================
# Stage helpers
# ============================================================================

STAGE_ORDER = ['script', 'videos', 'audio', 'subtitles', 'editing']

STAGE_MESSAGES = {
    'script':    'Generating script with AI…',
    'videos':    'Downloading stock videos…',
    'audio':     'Generating voiceover…',
    'subtitles': 'Generating subtitles…',
    'editing':   'Composing & exporting final video…',
}

def _make_job(status, message, stages=None, video_path=None):
    stages = stages or {s: 0 for s in STAGE_ORDER}
    overall = int(sum(stages.values()) / len(stages))
    job = {'status': status, 'message': message, 'progress': overall, 'stages': stages}
    if video_path:
        job['video_path'] = video_path
    return job

def _set_stage(job_id, stage, pct):
    current = jobs.get(job_id, {})
    stages  = dict(current.get('stages', {s: 0 for s in STAGE_ORDER}))
    stages[stage] = pct
    jobs[job_id]  = _make_job('processing', STAGE_MESSAGES[stage], stages, current.get('video_path'))


# ============================================================================
# Background task
# ============================================================================

def generate_video_async(job_id: str, topic: str, config: Config):
    """Run the full pipeline in a background thread, updating job status at each stage."""
    try:
        import traceback

        jobs[job_id] = _make_job('processing', 'Starting…')
        automation   = YouTubeShortsAutomation(config)

        # ── Step 1: Script ────────────────────────────────────────────
        _set_stage(job_id, 'script', 10)
        script = automation.script_generator.generate_script(topic)
        _set_stage(job_id, 'script', 100)

        # ── Step 2: Videos ────────────────────────────────────────────
        _set_stage(job_id, 'videos', 5)
        video_clips  = []
        total_scenes = len(script['scenes'])

        for i, scene in enumerate(script['scenes']):
            video_url = automation.video_searcher.search_video(
                scene['search_term'], scene['duration']
            )
            if video_url:
                clip_path = automation.video_searcher.download_video(
                    video_url, f"{job_id}_clip_{i}.mp4"
                )
                if clip_path:
                    video_clips.append(clip_path)

            _set_stage(job_id, 'videos', int(((i + 1) / total_scenes) * 100))
            time.sleep(0.5)  # light rate-limiting

        if not video_clips:
            jobs[job_id] = _make_job('error', 'No video clips could be downloaded.')
            return

        # ── Step 3: Voiceover ─────────────────────────────────────────
        _set_stage(job_id, 'audio', 10)
        full_narration  = " ".join([s['narration'] for s in script['scenes']])
        audio_path_base = config.TEMP_DIR / f"{job_id}_audio"
        audio_wav       = audio_path_base.with_suffix('.wav')
        audio_mp3       = audio_path_base.with_suffix('.mp3')

        if not automation.tts_generator.generate_audio(full_narration, audio_path_base):
            jobs[job_id] = _make_job('error', 'Failed to generate voiceover.')
            return

        # MP3 for muxing (avoids old-ffmpeg AAC issues); WAV for AssemblyAI
        audio_for_video = audio_mp3 if audio_mp3.exists() else audio_wav
        _set_stage(job_id, 'audio', 100)

        # ── Step 4: Subtitles ─────────────────────────────────────────
        _set_stage(job_id, 'subtitles', 10)
        srt_path = config.TEMP_DIR / f"{job_id}_subtitles.srt"
        automation.subtitle_generator.get_subtitles(audio_wav, srt_path)
        _set_stage(job_id, 'subtitles', 100)

        # ── Step 5: Compose ───────────────────────────────────────────
        _set_stage(job_id, 'editing', 10)
        output_path     = config.OUTPUT_DIR / f"{job_id}.mp4"
        scene_durations = [s.get('duration', 8) for s in script['scenes']]

        success = automation.video_editor.compose_video(
            video_clips,
            audio_for_video,
            srt_path,
            output_path,
            scene_durations=scene_durations
        )

        if success:
            _set_stage(job_id, 'editing', 100)
            stages = jobs[job_id]['stages']
            jobs[job_id] = _make_job('completed', 'Video created successfully!', stages, str(output_path))
        else:
            jobs[job_id] = _make_job('error', 'Video composition failed.')

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs[job_id] = _make_job('error', str(e))


# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/generate', methods=['POST'])
def generate():
    data  = request.json or {}
    topic = data.get('topic', '').strip()

    if not topic:
        return jsonify({'error': 'Topic is required'}), 400

    job_id = f"video_{int(time.time())}"
    config = Config()

    threading.Thread(
        target=generate_video_async,
        args=(job_id, topic, config),
        daemon=True
    ).start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])


@app.route('/download/<job_id>')
def download(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({'error': 'Video not ready yet'}), 400

    video_path = Path(job['video_path'])
    if not video_path.exists():
        return jsonify({'error': 'Video file not found on disk'}), 404

    return send_file(
        video_path,
        as_attachment=True,
        download_name=f"{job_id}.mp4",
        mimetype='video/mp4'
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 YouTube Shorts Automation — Web Interface")
    print("=" * 60)
    print("\n✨ Starting server…")
    print("📡 Open your browser: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop\n")
    print("=" * 60)

    app.run(debug=False, host='0.0.0.0', port=5000)
