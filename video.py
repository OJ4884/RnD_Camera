#!/usr/bin/env python3
"""
Raspberry Pi 5 Video Recorder
Records video from the camera module and saves it to the current directory.
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import signal
import logging

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
except ImportError:
    print("Error: picamera2 is not installed. Please install it with:")
    print("sudo apt install -y python3-picamera2")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoRecorder:
    def __init__(self, duration=None, resolution=(1920, 1080), framerate=30):
        """
        Initialize the video recorder.
        
        Args:
            duration: Recording duration in seconds (None for indefinite)
            resolution: Video resolution as tuple (width, height)
            framerate: Video framerate in fps
        """
        self.duration = duration
        self.resolution = resolution
        self.framerate = framerate
        self.camera = None
        self.recording = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle interrupt signals gracefully."""
        logger.info("Received interrupt signal, stopping recording...")
        self.stop()
        sys.exit(0)
    
    def start(self, filename=None):
        """
        Start recording video.
        
        Args:
            filename: Output filename (if None, generates one with timestamp)
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"recording_{timestamp}.mp4"
            
            output_path = Path(filename)
            
            logger.info(f"Initializing camera...")
            self.camera = Picamera2()
            
            # Configure camera with specified resolution and framerate
            config = self.camera.create_video_configuration(
                main={"format": "YUV420", "size": self.resolution},
                controls={"FrameRate": self.framerate}
            )
            self.camera.configure(config)
            
            logger.info(f"Starting recording to: {output_path.absolute()}")
            logger.info(f"Resolution: {self.resolution}, FPS: {self.framerate}")
            
            # Start camera and recording
            self.camera.start()
            encoder = H264Encoder(bitrate=10000000)  # 10Mbps
            output = FfmpegOutput(str(output_path))
            self.camera.start_recording(encoder, output)
            
            self.recording = True
            logger.info("Recording started successfully")
            
            if self.duration:
                import time
                logger.info(f"Recording for {self.duration} seconds...")
                time.sleep(self.duration)
                self.stop()
            else:
                logger.info("Recording... Press Ctrl+C to stop")
                # Keep the script running until interrupted
                try:
                    while self.recording:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    self.stop()
            
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop recording and clean up."""
        if self.camera is not None:
            try:
                logger.info("Stopping recording...")
                self.camera.stop_recording()
                self.camera.stop()
                self.recording = False
                logger.info("Recording stopped and camera cleaned up")
            except Exception as e:
                logger.error(f"Error stopping camera: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Record video from Raspberry Pi 5 camera",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record indefinitely (press Ctrl+C to stop)
  python3 video.py
  
  # Record for 30 seconds
  python3 video.py --duration 30
  
  # Record with custom filename
  python3 video.py --output my_video.mp4
  
  # Record with custom resolution and framerate
  python3 video.py --resolution 1280 720 --fps 24
        """
    )
    
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=None,
        help='Recording duration in seconds (default: indefinite)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output filename (default: recording_YYYYMMDD_HHMMSS.mp4)'
    )
    parser.add_argument(
        '-r', '--resolution',
        type=int,
        nargs=2,
        default=[1920, 1080],
        metavar=('WIDTH', 'HEIGHT'),
        help='Video resolution (default: 1920 1080)'
    )
    parser.add_argument(
        '-f', '--fps',
        type=int,
        default=30,
        dest='framerate',
        help='Framerate in fps (default: 30)'
    )
    
    args = parser.parse_args()
    
    recorder = VideoRecorder(
        duration=args.duration,
        resolution=tuple(args.resolution),
        framerate=args.framerate
    )
    
    recorder.start(filename=args.output)


if __name__ == '__main__':
    main()
