# Setup

## Prerequisites
On Raspberry Pi 5, ensure the camera interface is enabled:
```bash
sudo raspi-config
# Go to Interface Options > Camera and enable it
```

## Installation

```bash
# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Note: picamera2 is already installed as a system package
# No additional pip packages needed
```

## Usage

```bash
# Record indefinitely (press Ctrl+C to stop)
python3 video.py

# Record for 30 seconds
python3 video.py --duration 30

# Custom output filename
python3 video.py --output my_video.mp4

# Custom resolution and framerate
python3 video.py --resolution 1280 720 --fps 24
```

Videos will be saved in the current directory as MP4 files.