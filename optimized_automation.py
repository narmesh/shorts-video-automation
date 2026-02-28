"""
Optimized YouTube Shorts Automation with Advanced Features
- Caching for faster repeated topics
- Parallel video downloads
- Progress tracking
- Error recovery
- Quality presets
"""

import os
import json
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional
import pickle

from ysa_pix import (
    Config, ScriptGenerator, VideoSearcher,
    TTSGenerator, SubtitleGenerator, VideoEditor
)


class CacheManager:
    """Manage caching for scripts and assets"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.scripts_cache = cache_dir / "scripts"
        self.scripts_cache.mkdir(exist_ok=True)

    def get_topic_hash(self, topic: str) -> str:
        return hashlib.md5(topic.encode()).hexdigest()

    def cache_script(self, topic: str, script: dict):
        topic_hash = self.get_topic_hash(topic)
        cache_file = self.scripts_cache / f"{topic_hash}.json"
        with open(cache_file, 'w') as f:
            json.dump({
                'topic': topic,
                'script': script,
                'timestamp': time.time()
            }, f)

    def get_cached_script(self, topic: str, max_age: int = 86400) -> Optional[dict]:
        topic_hash = self.get_topic_hash(topic)
        cache_file = self.scripts_cache / f"{topic_hash}.json"

        if not cache_file.exists():
            return None

        with open(cache_file, 'r') as f:
            data = json.load(f)

        age = time.time() - data['timestamp']
        if age > max_age:
            return None

        return data['script']


class ProgressTracker:
    """Track and report progress"""

    def __init__(self):
        self.stages = {
            'script':    0,
            'videos':    0,
            'audio':     0,
            'subtitles': 0,
            'editing':   0
        }
        self.current_stage = None
        self.callbacks = []

    def update(self, stage: str, progress: int):
        self.stages[stage] = progress
        self.current_stage = stage
        self._notify()

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def _notify(self):
        overall_progress = sum(self.stages.values()) / len(self.stages)
        for callback in self.callbacks:
            callback(self.current_stage, self.stages[self.current_stage], overall_progress)

    def get_overall_progress(self) -> int:
        return int(sum(self.stages.values()) / len(self.stages))


class OptimizedAutomation:
    """Optimized automation with advanced features"""

    def __init__(self, config: Config, use_cache: bool = True, max_workers: int = 3):
        self.config = config
        self.use_cache = use_cache
        self.max_workers = max_workers

        self.script_generator  = ScriptGenerator(config)
        self.video_searcher    = VideoSearcher(config)
        self.tts_generator     = TTSGenerator(config)
        self.subtitle_generator = SubtitleGenerator(config)
        self.video_editor      = VideoEditor(config)

        if use_cache:
            self.cache = CacheManager(config.TEMP_DIR / "cache")
        else:
            self.cache = None

        self.progress = ProgressTracker()

    # ------------------------------------------------------------------
    # Script
    # ------------------------------------------------------------------

    def generate_script_with_cache(self, topic: str) -> dict:
        if self.cache:
            cached_script = self.cache.get_cached_script(topic)
            if cached_script:
                print("✅ Using cached script")
                self.progress.update('script', 100)
                return cached_script

        self.progress.update('script', 50)
        script = self.script_generator.generate_script(topic)

        if self.cache:
            self.cache.cache_script(topic, script)

        self.progress.update('script', 100)
        return script

    # ------------------------------------------------------------------
    # Parallel video download
    # ------------------------------------------------------------------

    def download_videos_parallel(self, scenes: List[dict], video_id: str) -> List[Path]:
        """Download multiple videos in parallel, preserving scene order"""
        total_scenes = len(scenes)

        def download_scene(i, scene):
            try:
                video_url = self.video_searcher.search_video(
                    scene['search_term'],
                    scene['duration']
                )
                if video_url:
                    clip_path = self.video_searcher.download_video(
                        video_url,
                        f"{video_id}_clip_{i}.mp4"
                    )
                    return i, clip_path
                return i, None
            except Exception as e:
                print(f"❌ Error downloading scene {i}: {e}")
                return i, None

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(download_scene, i, scene)
                for i, scene in enumerate(scenes)
            ]

            completed = 0
            for future in as_completed(futures):
                i, clip_path = future.result()
                if clip_path:
                    results.append((i, clip_path))

                completed += 1
                self.progress.update('videos', int((completed / total_scenes) * 100))
                time.sleep(0.5)  # light rate-limiting

        # Restore original scene order
        results.sort(key=lambda x: x[0])
        return [clip for _, clip in results]

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def create_video_optimized(
        self,
        topic: str,
        video_id: Optional[str] = None,
        quality: str = "high"
    ) -> Optional[Path]:
        """
        Create video with optimizations.

        Args:
            topic:    Video topic
            video_id: Optional video ID (auto-generated if omitted)
            quality:  'high' | 'medium' | 'fast'
        """
        if not video_id:
            video_id = f"video_{int(time.time())}"

        print(f"\n{'='*60}")
        print(f"🚀 Creating Optimized YouTube Short: {topic}")
        print(f"   Quality: {quality}")
        print(f"{'='*60}\n")

        try:
            # Apply quality preset
            preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS['medium'])
            self.config.FPS = preset['fps']
            self.max_workers = preset['max_workers']

            # ── Step 1: Script ────────────────────────────────────────
            script = self.generate_script_with_cache(topic)

            # ── Step 2: Videos (parallel) ─────────────────────────────
            video_clips = self.download_videos_parallel(script['scenes'], video_id)

            if not video_clips:
                print("❌ No video clips downloaded")
                return None

            # ── Step 3: Voiceover ─────────────────────────────────────
            self.progress.update('audio', 25)
            full_narration = " ".join([scene['narration'] for scene in script['scenes']])

            # audio_path_base has no extension; TTSGenerator appends .wav then .mp3
            audio_path_base = self.config.TEMP_DIR / f"{video_id}_audio"
            audio_wav = audio_path_base.with_suffix('.wav')
            audio_mp3 = audio_path_base.with_suffix('.mp3')

            if not self.tts_generator.generate_audio(full_narration, audio_path_base):
                print("❌ Failed to generate voiceover")
                return None

            # Use MP3 for video muxing (WAV has compat issues on Windows/old ffmpeg)
            audio_for_video = audio_mp3 if audio_mp3.exists() else audio_wav
            self.progress.update('audio', 100)
            print(f"   🎵 Using audio file: {audio_for_video.name}")

            # ── Step 4: Subtitles ─────────────────────────────────────
            # Always send WAV to AssemblyAI — it handles it more reliably
            self.progress.update('subtitles', 25)
            srt_path = self.config.TEMP_DIR / f"{video_id}_subtitles.srt"
            self.subtitle_generator.get_subtitles(audio_wav, srt_path)
            self.progress.update('subtitles', 100)

            # ── Step 5: Compose ───────────────────────────────────────
            self.progress.update('editing', 25)
            output_path = self.config.OUTPUT_DIR / f"{video_id}.mp4"

            # Pass declared scene durations so each clip is trimmed proportionally
            scene_durations = [scene.get('duration', 8) for scene in script['scenes']]

            if self.video_editor.compose_video(
                video_clips,
                audio_for_video,
                srt_path,
                output_path,
                scene_durations=scene_durations
            ):
                self.progress.update('editing', 100)

                print(f"\n{'='*60}")
                print(f"✨ SUCCESS! Video created: {output_path}")
                print(f"📊 Overall Progress: {self.progress.get_overall_progress()}%")
                print(f"{'='*60}\n")
                return output_path
            else:
                return None

        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch_create_optimized(
        self,
        topics: List[str],
        quality: str = "medium",
        delay: int = 30
    ) -> Dict[str, List]:
        """
        Create multiple videos sequentially with a delay between each.

        Args:
            topics:  List of topics
            quality: Quality preset
            delay:   Seconds to wait between videos
        """
        results = {'successful': [], 'failed': []}

        for i, topic in enumerate(topics, 1):
            print(f"\n{'='*60}")
            print(f"📹 Batch: Processing {i}/{len(topics)} — '{topic}'")
            print(f"{'='*60}\n")

            self.progress = ProgressTracker()  # fresh tracker per video

            try:
                video_path = self.create_video_optimized(
                    topic,
                    video_id=f"batch_{i}_{int(time.time())}",
                    quality=quality
                )

                if video_path:
                    results['successful'].append({
                        'topic': topic,
                        'video_path': str(video_path)
                    })
                else:
                    results['failed'].append({
                        'topic': topic,
                        'reason': 'Pipeline returned None'
                    })

            except Exception as e:
                results['failed'].append({'topic': topic, 'reason': str(e)})

            if i < len(topics):
                print(f"\n⏳ Waiting {delay}s before next video…")
                time.sleep(delay)

        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Batch complete: {len(results['successful'])} succeeded, "
              f"{len(results['failed'])} failed")
        for f in results['failed']:
            print(f"   ❌ '{f['topic']}': {f['reason']}")
        print(f"{'='*60}\n")

        return results


# ============================================================================
# Quality Presets
# ============================================================================

QUALITY_PRESETS = {
    'fast': {
        'fps': 24,
        'max_workers': 5,
        'description': 'Fast generation, lower quality'
    },
    'medium': {
        'fps': 30,
        'max_workers': 3,
        'description': 'Balanced speed and quality'
    },
    'high': {
        'fps': 30,
        'max_workers': 2,
        'description': 'Best quality, slower generation'
    }
}


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Optimized YouTube Shorts Automation"
    )
    parser.add_argument("topic", type=str, help="Video topic")
    parser.add_argument(
        "--quality",
        choices=['fast', 'medium', 'high'],
        default='medium',
        help="Quality preset (default: medium)"
    )
    parser.add_argument(
        "--no-cache",
        action='store_true',
        help="Disable script caching"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Max parallel download workers (default: 3)"
    )

    args = parser.parse_args()

    config = Config()
    automation = OptimizedAutomation(
        config,
        use_cache=not args.no_cache,
        max_workers=args.workers
    )

    def print_progress(stage, stage_progress, overall):
        print(f"📊 {stage.upper()}: {stage_progress}% | Overall: {int(overall)}%")

    automation.progress.add_callback(print_progress)

    video_path = automation.create_video_optimized(
        args.topic,
        quality=args.quality
    )

    return 0 if video_path else 1


if __name__ == "__main__":
    exit(main())
