"""
YouTube Shorts Automation System
Automatically generates fact-based short videos using:
- Groq API for script generation
- Pixabay API for stock videos
- Piper TTS for voiceover
- MoviePy for video editing
- AssemblyAI for subtitle generation
"""

import os
import json
import time
import cv2
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import random

from groq import Groq
from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, TextClip,
    CompositeVideoClip, AudioFileClip
)
from moviepy.video.fx.resize import resize
from moviepy.video.fx.crop import crop
import numpy as np

#Fix for Pillow 10+ compatability
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Configuration for the automation system"""
    # API Keys
    GROQ_API_KEY: str = "YOUR GROQ_API_KEY"
    PIXABAY_API_KEY: str = "YOUR PIXABAY_API_KEY" 
    ASSEMBLYAI_API_KEY: str = "YOUR ASSEMBLYAI_API_KEY" 
    
    # Video Settings
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920  # 9:16 for vertical video
    VIDEO_DURATION: int = 30  # Base Target duration, but duration depends upon the audio length
    FPS: int = 30
    
    # Directories
    OUTPUT_DIR: Path = Path("output")
    TEMP_DIR: Path = Path("temp")
    ASSETS_DIR: Path = Path("assets")
    
    # TTS Settings
    PIPER_MODEL: str = "piper/en_US-lessac-medium.onnx"  # Medium-quality voice model
    PIPER_PATH: str = "piper"  # Path to piper
    
    # Groq Settings
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # https://console.groq.com/docs/models
    
    def __post_init__(self):
        """Create necessary directories"""
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.ASSETS_DIR.mkdir(exist_ok=True)


# ============================================================================
# SCRIPT GENERATION (Using Groq)
# ============================================================================

class ScriptGenerator:
    """Generate video scripts using Groq API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = Groq(api_key=config.GROQ_API_KEY)
    
    def generate_script(self, topic: str) -> Dict[str, any]:
        print(f"🎬 Generating script for topic: {topic}")
        
        prompt = f"""Create a YouTube Shorts script about: {topic}

    You MUST write exactly 5 scenes. Each scene narration MUST be 30-45 words long (count them carefully). 
    The total word count across all 5 scenes must be between 175-220 words.
    This is critical — short narrations will ruin the video.

    The search_term must visually match what is being said. For example:
    - Talking about deep ocean → "deep ocean"  
    - Talking about cheetah speed → "cheetah"
    - Talking about ancient Egypt → "pyramids"
    - Talking about any kind of war → "war" or "world war" or "weapons"

    Return ONLY this JSON, no other text:
    {{
        "title": "Catchy video title",
        "hook": "Opening hook sentence",
        "scenes": [
            {{
                "narration": "Write 30 to 45 words here describing this fact in detail. This is the voiceover text and must be long enough to fill 8 seconds of speech. Do not write a short sentence.",
                "duration": 8,
                "search_term": "visual description matching narration"
            }},
            {{
                "narration": "Write 30 to 45 words here for the second fact. Keep it engaging and informative. Remember each narration needs to be long enough to fill 8 full seconds when spoken aloud at normal speed.",
                "duration": 8,
                "search_term": "visual description matching narration"
            }},
            {{
                "narration": "Write 30 to 45 words here for the third fact. The audience should learn something surprising. Make sure this narration is detailed enough to last 8 seconds when read aloud.",
                "duration": 8,
                "search_term": "visual description matching narration"
            }},
            {{
                "narration": "Write 30 to 45 words here for the fourth fact. Add interesting context and details. This voiceover must be long enough that it takes 8 seconds to speak at a comfortable natural pace.",
                "duration": 8,
                "search_term": "visual description matching narration"
            }},
            {{
                "narration": "Write 30 to 45 words here for the fifth and final fact. End with something memorable that makes viewers want to share. This narration must also be 30 to 45 words long.",
                "duration": 8,
                "search_term": "visual description matching narration"
            }}
        ]
    }}"""

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a YouTube Shorts script writer. You always write narrations that are exactly 30-45 words each. You always return valid JSON only with no extra text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.config.GROQ_MODEL,
                temperature=0.7,
                max_tokens=2000,
            )
            
            script_text = response.choices[0].message.content.strip()
            
            # Extract JSON
            json_start = script_text.find('{')
            json_end = script_text.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                script_text = script_text[json_start:json_end]
            
            script = json.loads(script_text)
            
            # Validate and log word counts
            print(f"✅ Script generated: {script['title']}")
            total_words = 0
            for i, scene in enumerate(script['scenes']):
                word_count = len(scene['narration'].split())
                total_words += word_count
                print(f"   Scene {i+1}: {word_count} words | search: '{scene['search_term']}'")
            print(f"   Total words: {total_words} (target: 175-220)")
            
            # Warn if too short
            if total_words < 100:
                print(f"⚠️ WARNING: Script is very short ({total_words} words). Video may be under 20s.")
            
            return script
            
        except Exception as e:
            print(f"❌ Error generating script: {e}")
            raise


# ============================================================================
# VIDEO SEARCH & DOWNLOAD (Pixabay)
# ============================================================================

class VideoSearcher:
    """Search and download stock videos from Pixabay"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://pixabay.com/api/videos/"
    
    def search_video(self, query: str, duration: int) -> Optional[str]:
        """
        Search for a video on Pixabay and return the best download URL.
        
        Pixabay video response structure:
          hits[].videos.large  → 1920x1080 mp4
          hits[].videos.medium → 1280x720  mp4
          hits[].videos.small  → 960x540   mp4
          hits[].videos.tiny   → 640x360   mp4
        """
        try:
            params = {
                "key": self.config.PIXABAY_API_KEY,
                "q": query,
                "video_type": "film",       # 'film' = real footage, vs 'animation'
                "per_page": 15,
                "safesearch": "true",
                "order": "popular",
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", [])
            if not hits:
                print(f"⚠️  No videos found for: '{query}' — trying broader search")
                # Fallback: use only first word of query for a broader match
                fallback_query = query.split()[0]
                params["q"] = fallback_query
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                hits = response.json().get("hits", [])
            
            if not hits:
                print(f"❌ Still no videos found for: '{query}'")
                return None
            
            # Pick randomly from the top 5 results for variety
            video = random.choice(hits[:min(5, len(hits))])
            videos = video["videos"]
            
            # Prefer large (1080p), fall back down the quality ladder
            for quality in ("large", "medium", "small", "tiny"):
                url = videos.get(quality, {}).get("url", "")
                if url:
                    w = videos[quality].get("width", 0)
                    h = videos[quality].get("height", 0)
                    print(f"✅ Found Pixabay video for '{query}': {quality} ({w}x{h})")
                    return url
            
            print(f"❌ No usable video URL in response for: '{query}'")
            return None
            
        except Exception as e:
            print(f"❌ Error searching Pixabay for '{query}': {e}")
            return None
    
    def download_video(self, url: str, filename: str) -> Optional[Path]:
        """Download video from URL to temp directory"""
        try:
            filepath = self.config.TEMP_DIR / filename
            print(f"⬇️  Downloading: {filename}")
            
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ Downloaded: {filename}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error downloading video: {e}")
            return None


# ============================================================================
# TEXT-TO-SPEECH (Piper)
# ============================================================================

class TTSGenerator:
    """Generate voiceover using Piper TTS"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def generate_audio(self, text: str, output_file: Path) -> bool:
        try:
            print(f"🎤 Generating voiceover...")
            
            wav_file = output_file.with_suffix('.wav')
            
            cmd = [
                self.config.PIPER_PATH,
                "--model", self.config.PIPER_MODEL,
                "--output_file", str(wav_file)
            ]
            
            result = subprocess.run(
                cmd,
                input=text.encode('utf-8'),
                capture_output=True,
                check=True
            )
            
            if not wav_file.exists():
                print(f"❌ Voiceover WAV not created")
                return False
            
            # Convert WAV to MP3 using ffmpeg for better MoviePy compatibility
            mp3_file = output_file.with_suffix('.mp3')
            convert_cmd = [
                "ffmpeg", "-y",
                "-i", str(wav_file),
                "-codec:a", "libmp3lame",
                "-qscale:a", "2",
                str(mp3_file)
            ]
            subprocess.run(convert_cmd, capture_output=True, check=True)
            
            if mp3_file.exists():
                print(f"✅ Voiceover generated: {mp3_file}")
                return True
            else:
                print(f"❌ MP3 conversion failed, falling back to WAV")
                return wav_file.exists()
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Piper error: {e.stderr.decode()}")
            return False
        except Exception as e:
            print(f"❌ Error generating audio: {e}")
            return False


# ============================================================================
# SUBTITLE GENERATION (AssemblyAI)
# ============================================================================

class SubtitleGenerator:
    """Generate subtitles using AssemblyAI"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://api.assemblyai.com/v2"  # Must include /v2
        self.headers = {
            "authorization": config.ASSEMBLYAI_API_KEY
        }
    
    def upload_audio(self, audio_path: Path) -> Optional[str]:
        """Upload audio file and get URL"""
        try:
            print(f"📤 Uploading audio file...")
            with open(audio_path, 'rb') as f:
                response = requests.post(
                    f"{self.base_url}/upload",
                    headers=self.headers,  # Only authorization header for upload
                    data=f
                )
            response.raise_for_status()
            upload_url = response.json()['upload_url']
            print(f"✅ Audio uploaded successfully")
            return upload_url
        except Exception as e:
            print(f"❌ Error uploading audio: {e}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response.text}")
            return None
    
    def transcribe(self, audio_url: str) -> Optional[str]:
        """Transcribe audio and get transcript ID"""
        try:
            print(f"🎯 Starting transcription...")
            data = {
                "audio_url": audio_url,
                "speech_models": ["universal-3-pro", "universal-2"],
                "language_detection": True,
                "speaker_labels": True
            }
            # Add content-type for JSON request
            headers = {
                "authorization": self.config.ASSEMBLYAI_API_KEY,
                "content-type": "application/json"
            }
            response = requests.post(
                f"{self.base_url}/transcript",
                json=data,
                headers=headers
            )
            response.raise_for_status()
            transcript_id = response.json()['id']
            print(f"✅ Transcription started: {transcript_id}")
            return transcript_id
        except Exception as e:
            print(f"❌ Error starting transcription: {e}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response.text}")
            return None
    
    def get_subtitles(self, audio_path: Path, output_srt: Path) -> bool:
        """
        Generate SRT subtitles from audio
        
        Args:
            audio_path: Path to audio file
            output_srt: Where to save SRT file
            
        Returns:
            True if successful
        """
        try:
            print("📝 Generating subtitles...")
            
            # Upload audio
            audio_url = self.upload_audio(audio_path)
            if not audio_url:
                return False
            
            # Start transcription
            transcript_id = self.transcribe(audio_url)
            if not transcript_id:
                return False
            
            # Poll for completion
            print("⏳ Waiting for transcription...")
            max_attempts = 60  # 3 minutes max (60 * 3 seconds)
            attempts = 0
            
            while attempts < max_attempts:
                response = requests.get(
                    f"{self.base_url}/transcript/{transcript_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                result = response.json()
                
                status = result['status']
                
                if status == 'completed':
                    print(f"✅ Transcription completed!")
                    break
                elif status == 'error':
                    error_msg = result.get('error', 'Unknown error')
                    print(f"❌ Transcription error: {error_msg}")
                    return False
                elif status in ['queued', 'processing']:
                    print(f"   Status: {status}... ({attempts + 1}/{max_attempts})")
                
                time.sleep(3)
                attempts += 1
            
            if attempts >= max_attempts:
                print(f"❌ Transcription timed out")
                return False
            
            # Get SRT format
            print("📥 Downloading SRT subtitles...")
            srt_response = requests.get(
                f"{self.base_url}/transcript/{transcript_id}/srt",
                headers=self.headers
            )
            srt_response.raise_for_status()
            
            # Save SRT file
            with open(output_srt, 'w', encoding='utf-8') as f:
                f.write(srt_response.text)
            
            print(f"✅ Subtitles generated: {output_srt}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating subtitles: {e}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response.text}")
            return False


# ============================================================================
# VIDEO EDITOR (MoviePy + OpenCV for subtitles)
# ============================================================================

import cv2
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, VideoClip
from moviepy.video.fx.resize import resize
from moviepy.video.fx.crop import crop
import re

class VideoEditor:
    """Edit and compose final video"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def crop_to_portrait(self, clip: VideoFileClip) -> VideoFileClip:
        width, height = clip.size
        target_ratio = self.config.VIDEO_WIDTH / self.config.VIDEO_HEIGHT
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            new_width = int(height * target_ratio)
            x_center = width / 2
            x1 = int(x_center - new_width / 2)
            return crop(clip, x1=x1, width=new_width)
        else:
            new_height = int(width / target_ratio)
            y_center = height / 2
            y1 = int(y_center - new_height / 2)
            return crop(clip, y1=y1, height=new_height)
    
    def resize_to_target(self, clip: VideoFileClip) -> VideoFileClip:
        return resize(clip, height=self.config.VIDEO_HEIGHT)

    def parse_srt(self, srt_path: Path) -> List[Dict]:
        subtitles = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            blocks = re.split(r'\n\s*\n', content.strip())
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    continue
                
                time_line = lines[1]
                match = re.match(
                    r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                    time_line
                )
                if not match:
                    continue
                
                h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
                start = int(h1)*3600 + int(m1)*60 + int(s1) + int(ms1)/1000
                end = int(h2)*3600 + int(m2)*60 + int(s2) + int(ms2)/1000
                text = ' '.join(lines[2:]).strip()
                subtitles.append({'start': start, 'end': end, 'text': text})
        
        except Exception as e:
            print(f"⚠️ Could not parse SRT: {e}")
        
        return subtitles

    def add_subtitles_to_frame(self, frame: np.ndarray, text: str) -> np.ndarray:
        if not text:
            return frame
        
        frame = frame.copy()
        h, w = frame.shape[:2]
        
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 1.8
        thickness = 3
        max_width = w - 80

        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            (tw, _), _ = cv2.getTextSize(test_line, font, font_scale, thickness)
            if tw <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_height = 60
        total_height = len(lines) * line_height
        #position at center center
        y_start = (h - total_height) // 2

        for i, line in enumerate(lines):
            (tw, th), _ = cv2.getTextSize(line, font, font_scale, thickness)
            x = (w - tw) // 2
            y = y_start + i * line_height
            cv2.putText(frame, line, (x, y), font, font_scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
            cv2.putText(frame, line, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        return frame

    def get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration using ffprobe"""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(audio_path)
            ], capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            print(f"   🎵 Audio duration (ffprobe): {duration:.2f}s")
            return duration
        except Exception as e:
            print(f"⚠️ ffprobe failed: {e}, falling back to MoviePy")
            clip = AudioFileClip(str(audio_path))
            duration = clip.duration
            clip.close()
            return duration

    def compose_video(
        self,
        video_clips: List[Path],
        audio_path: Path,
        srt_path: Path,
        output_path: Path,
        scene_durations: List[float] = None
    ) -> bool:
        try:
            print("🎬 Composing final video...")

            # Get audio duration via ffprobe (more reliable than MoviePy on Windows)
            total_duration = self.get_audio_duration(audio_path)
            print(f"   Total video duration target: {total_duration:.2f}s")

            # Determine per-scene durations
            if scene_durations and len(scene_durations) == len(video_clips):
                # Scale scene durations to match actual audio duration
                declared_total = sum(scene_durations)
                scale = total_duration / declared_total
                trimmed_durations = [d * scale for d in scene_durations]
            else:
                trimmed_durations = [total_duration / len(video_clips)] * len(video_clips)

            print(f"   Scene durations: {[f'{d:.1f}s' for d in trimmed_durations]}")

            # Load, crop, resize, and trim each clip to its scene duration
            trimmed_clips = []
            for i, (clip_path, duration) in enumerate(zip(video_clips, trimmed_durations)):
                print(f"  Processing clip {i+1}/{len(video_clips)} → {duration:.1f}s")
                clip = VideoFileClip(str(clip_path))
                clip = self.crop_to_portrait(clip)
                clip = self.resize_to_target(clip)

                # Loop if clip is shorter than needed
                if clip.duration < duration:
                    loops = int(duration / clip.duration) + 2
                    from moviepy.editor import concatenate_videoclips as _cat
                    clip = _cat([clip] * loops)

                clip = clip.subclip(0, duration)
                # Mute background video — audio comes only from voiceover
                clip = clip.without_audio()
                trimmed_clips.append(clip)

            # Concatenate all clips
            final_video = concatenate_videoclips(trimmed_clips, method="compose")
            print(f"   Concatenated video duration: {final_video.duration:.2f}s")

            # Parse and burn subtitles
            subtitles = []
            if srt_path.exists():
                subtitles = self.parse_srt(srt_path)
                print(f"   Loaded {len(subtitles)} subtitle entries")

            if subtitles:
                def process_frame(get_frame, t):
                    frame = get_frame(t)
                    current_sub = ""
                    for sub in subtitles:
                        if sub['start'] <= t <= sub['end']:
                            current_sub = sub['text']
                            break
                    return self.add_subtitles_to_frame(frame, current_sub)
                final_video = final_video.fl(process_frame)

            # ----------------------------------------------------------------
            # Export video WITHOUT audio first, then mux audio via ffmpeg
            # This avoids MoviePy's Windows WAV/MP3 audio muxing bugs entirely
            # ----------------------------------------------------------------
            silent_path = output_path.parent / f"_silent_{output_path.name}"
            print("💾 Exporting silent video...")
            final_video.write_videofile(
                str(silent_path),
                fps=self.config.FPS,
                codec='libx264',
                audio=False,          # No audio in this pass
                preset='medium',
                threads=4
            )

            # Cleanup MoviePy objects before ffmpeg pass
            for clip in trimmed_clips:
                clip.close()
            final_video.close()

            # Mux audio using ffmpeg directly — most reliable on Windows
            print("🔊 Muxing audio with ffmpeg...")
            mux_cmd = [
                "ffmpeg", "-y",
                "-i", str(silent_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "copy",        # Just copy MP3 stream directly, no re-encoding
                "-shortest",
                "-map", "0:v:0",
                "-map", "1:a:0",
                str(output_path)
            ]
            result = subprocess.run(mux_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"❌ ffmpeg mux error:\n{result.stderr}")
                return False

            # Remove silent intermediate file
            silent_path.unlink(missing_ok=True)

            print(f"✅ Video created: {output_path}")
            return True

        except Exception as e:
            print(f"❌ Error composing video: {e}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# MAIN AUTOMATION PIPELINE
# ============================================================================

class YouTubeShortsAutomation:
    """Main automation pipeline"""
    
    def __init__(self, config: Config):
        self.config = config
        self.script_generator = ScriptGenerator(config)
        self.video_searcher = VideoSearcher(config)
        self.tts_generator = TTSGenerator(config)
        self.subtitle_generator = SubtitleGenerator(config)
        self.video_editor = VideoEditor(config)
    
    def create_video(self, topic: str, video_id: Optional[str] = None) -> Optional[Path]:
        """
        Create a complete YouTube Short video
        
        Args:
            topic: Video topic/idea
            video_id: Optional custom video ID
            
        Returns:
            Path to final video or None if failed
        """
        if not video_id:
            video_id = f"video_{int(time.time())}"
        
        print(f"\n{'='*60}")
        print(f"🚀 Creating YouTube Short: {topic}")
        print(f"{'='*60}\n")
        
        try:
            # Step 1: Generate script
            script = self.script_generator.generate_script(topic)
            
            # Step 2: Search and download videos
            video_clips = []
            for i, scene in enumerate(script['scenes']):
                search_term = scene['search_term']
                video_url = self.video_searcher.search_video(
                    search_term,
                    scene['duration']
                )
                
                if video_url:
                    clip_path = self.video_searcher.download_video(
                        video_url,
                        f"{video_id}_clip_{i}.mp4"
                    )
                    if clip_path:
                        video_clips.append(clip_path)
                
                time.sleep(1)  # Rate limiting
            
            if not video_clips:
                print("❌ No video clips downloaded")
                return None
            
            # Step 3: Generate voiceover
            full_narration = " ".join([scene['narration'] for scene in script['scenes']])
            audio_path_base = self.config.TEMP_DIR / f"{video_id}_audio"
            audio_wav = audio_path_base.with_suffix('.wav')
            audio_path = audio_path_base.with_suffix('.mp3')  # Use MP3 for MoviePy

            if not self.tts_generator.generate_audio(full_narration, audio_path_base):
                print("❌ Failed to generate voiceover")
                return None

            # Use MP3 if it exists, fall back to WAV
            if not audio_path.exists():
                audio_path = audio_wav

            # Step 4: Generate subtitles (use WAV for AssemblyAI — it's more reliable)
            srt_path = self.config.TEMP_DIR / f"{video_id}_subtitles.srt"
            self.subtitle_generator.get_subtitles(audio_wav, srt_path)
            
            # Step 5: Compose final video
            output_path = self.config.OUTPUT_DIR / f"{video_id}.mp4"

            # Pass declared scene durations so clips are trimmed proportionally
            scene_durations = [scene.get('duration', 8) for scene in script['scenes']]

            if self.video_editor.compose_video(
                video_clips,
                audio_path,
                srt_path,
                output_path,
                scene_durations=scene_durations
            ):
                print(f"\n{'='*60}")
                print(f"✨ SUCCESS! Video created: {output_path}")
                print(f"{'='*60}\n")
                return output_path
            else:
                return None
                
        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")
            return None
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        import shutil
        if self.config.TEMP_DIR.exists():
            shutil.rmtree(self.config.TEMP_DIR)
            self.config.TEMP_DIR.mkdir()
        print("🧹 Cleaned up temporary files")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automated YouTube Shorts Video Generator"
    )
    parser.add_argument(
        "topic",
        type=str,
        help="Video topic or idea"
    )
    parser.add_argument(
        "--groq-key",
        type=str,
        help="Groq API key (or set GROQ_API_KEY env var)"
    )
    parser.add_argument(
        "--pixabay-key",
        type=str,
        help="Pixabay API key (or set PIXABAY_API_KEY env var)"
    )
    parser.add_argument(
        "--assemblyai-key",
        type=str,
        help="AssemblyAI API key (or set ASSEMBLYAI_API_KEY env var)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up temporary files after completion"
    )
    
    args = parser.parse_args()
    
    # Setup configuration
    config = Config()
    
    # Override with environment variables or arguments
    if args.groq_key:
        config.GROQ_API_KEY = args.groq_key
    elif os.getenv("GROQ_API_KEY"):
        config.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    if args.pixabay_key:
        config.PIXABAY_API_KEY = args.pixabay_key
    elif os.getenv("PIXABAY_API_KEY"):
        config.PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
    
    if args.assemblyai_key:
        config.ASSEMBLYAI_API_KEY = args.assemblyai_key
    elif os.getenv("ASSEMBLYAI_API_KEY"):
        config.ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
    
    # Create automation instance
    automation = YouTubeShortsAutomation(config)
    
    # Generate video
    video_path = automation.create_video(args.topic)
    
    # Cleanup if requested
    if args.cleanup and video_path:
        automation.cleanup_temp_files()
    
    return 0 if video_path else 1


if __name__ == "__main__":
    exit(main())
