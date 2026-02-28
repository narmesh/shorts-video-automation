"""
Batch Video Generator
Generate multiple YouTube Shorts from a list of topics
"""

import json
import time
from pathlib import Path
from ysa_pix import YouTubeShortsAutomation, Config


def load_topics(topics_file: str) -> list:
    """Load topics from JSON file"""
    with open(topics_file, 'r') as f:
        data = json.load(f)
    return data.get('topics', [])


def generate_batch(topics: list, delay: int = 60):
    """
    Generate multiple videos from a list of topics.

    Args:
        topics: List of video topics
        delay:  Delay between videos in seconds (for API rate limiting)
    """
    config = Config()
    automation = YouTubeShortsAutomation(config)

    results = {
        'successful': [],
        'failed': []
    }

    total = len(topics)

    for i, topic in enumerate(topics, 1):
        print(f"\n{'='*60}")
        print(f"📹 Processing {i}/{total}: {topic}")
        print(f"{'='*60}\n")

        # Unique ID includes timestamp so repeated runs never overwrite each other
        video_id = f"batch_{i}_{int(time.time())}"

        try:
            video_path = automation.create_video(topic, video_id=video_id)

            if video_path:
                results['successful'].append({
                    'topic': topic,
                    'video_path': str(video_path)
                })
                print(f"✅ Video {i} completed: {video_path}")
            else:
                results['failed'].append({
                    'topic': topic,
                    'reason': 'Pipeline returned None'
                })
                print(f"❌ Video {i} failed")

        except Exception as e:
            results['failed'].append({
                'topic': topic,
                'reason': str(e)
            })
            print(f"❌ Error processing video {i}: {e}")
            import traceback
            traceback.print_exc()

        # Delay before next video (skip after last)
        if i < total:
            print(f"\n⏳ Waiting {delay}s before next video…")
            time.sleep(delay)

    # ── Save results ──────────────────────────────────────────────────
    results_file = config.OUTPUT_DIR / 'batch_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successful : {len(results['successful'])}/{total}")
    print(f"❌ Failed     : {len(results['failed'])}/{total}")
    if results['failed']:
        for f in results['failed']:
            print(f"   • '{f['topic']}': {f['reason']}")
    print(f"📊 Results saved to: {results_file}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python batch_generator.py <topics_file.json> [delay_seconds]")
        print("\nTopics file format:")
        print('''{
  "topics": [
    "Amazing facts about space",
    "Mysterious ocean creatures",
    "Unbelievable world records"
  ]
}''')
        sys.exit(1)

    topics_file = sys.argv[1]
    topics = load_topics(topics_file)

    if not topics:
        print(f"❌ No topics found in '{topics_file}'. Check the file format.")
        sys.exit(1)

    print(f"📋 Loaded {len(topics)} topic(s) from '{topics_file}'")

    delay = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    print(f"⏱️  Delay between videos: {delay}s")

    generate_batch(topics, delay)
