"""
Shorts Video Automation — Package Setup
"""

from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="shorts-video-automation",
    version="1.0.0",
    author="Narmesh Kumar Sah",
    description="Automatically generate Shorts Video using AI, stock video, and TTS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    install_requires=[
        "groq>=0.9.0",
        "moviepy>=1.0.3",
        "opencv-python>=4.8.0",
        "Pillow>=9.0.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
    ],
    extras_require={
        "web": ["flask>=3.0.0"],
    },
    entry_points={
        "console_scripts": [
            # Main generator
            "ysa=ysa_pix:main",
            # Optimized runner
            "ysa-optimized=optimized_automation:main",
            # Web interface
            "ysa-web=web_interface:app.run",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
