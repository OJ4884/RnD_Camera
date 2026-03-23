#!/usr/bin/env python3
"""
Raspberry Pi 5 Camera Module
Captures images and records video from the camera module.
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


class CameraController:
    """Base class for camera operations."""
    
    def __init__(self, resolution=(1920, 1080), framerate=30):
        """
        Initialize the camera controller.
        
        Args:
            resolution: Camera resolution as tuple (width, height)
            framerate: Camera framerate in fps
        """
        self.resolution = resolution
        self.framerate = framerate
        self.camera = None
        self.camera_ready = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle interrupt signals gracefully."""
        logger.info("Received interrupt signal, stopping operation...")
        self.cleanup()
        sys.exit(0)
    
    def _initialize_camera(self):
        """Initialize and configure the camera."""
        if self.camera_ready:
            return
        
        try:
            logger.info("Initializing camera...")
            self.camera = Picamera2()
            self.camera_ready = True
            logger.info("Camera initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing camera: {e}")
            raise
    
    def cleanup(self):
        """Clean up camera resources."""
        if self.camera is not None:
            try:
                if self.camera.started:
                    self.camera.stop()
                self.camera.close()
                logger.info("Camera closed successfully")
                self.camera_ready = False
            except Exception as e:
                logger.error(f"Error closing camera: {e}")


class ImageCapture(CameraController):
    """Handles image capture operations."""
    
    def capture(self, filename=None, count=1):
        """
        Capture image(s) from the camera.
        
        Args:
            filename: Output filename (if None, generates one with timestamp)
            count: Number of images to capture
        """
        try:
            self._initialize_camera()
            
            # Configure camera for still image capture
            config = self.camera.create_still_configuration(
                main={"format": "RGB888", "size": self.resolution}
            )
            self.camera.configure(config)
            
            logger.info(f"Starting image capture (count: {count})")
            logger.info(f"Resolution: {self.resolution}")
            
            self.camera.start()
            
            for i in range(count):
                if filename is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_name = f"image_{timestamp}"
                    if count > 1:
                        output_name += f"_{i+1}"
                    output_name += ".jpg"
                else:
                    if count > 1:
                        base = Path(filename).stem
                        ext = Path(filename).suffix
                        output_name = f"{base}_{i+1}{ext}"
                    else:
                        output_name = filename
                
                output_path = Path(output_name)
                
                # Capture the image
                request = self.camera.capture_request()
                request.save("main", str(output_path.absolute()))
                request.release()
                
                logger.info(f"Captured image {i+1}/{count}: {output_path.absolute()}")
                
                if i < count - 1:
                    import time
                    time.sleep(0.5)  # Small delay between captures
            
            self.camera.stop()
            logger.info("Image capture completed successfully")
            
        except Exception as e:
            logger.error(f"Error during image capture: {e}")
            self.cleanup()
            raise


class VideoRecorder(CameraController):
    """Handles video recording operations."""
    
    def __init__(self, duration=None, resolution=(1920, 1080), framerate=30):
        """
        Initialize the video recorder.
        
        Args:
            duration: Recording duration in seconds (None for indefinite)
            resolution: Video resolution as tuple (width, height)
            framerate: Video framerate in fps
        """
        super().__init__(resolution=resolution, framerate=framerate)
        self.duration = duration
        self.recording = False
    
    def start(self, filename=None):
        """
        Start recording video.
        
        Args:
            filename: Output filename (if None, generates one with timestamp)
        """
        try:
            self._initialize_camera()
            
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"recording_{timestamp}.mp4"
            
            output_path = Path(filename)
            
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
                self.recording = False
                logger.info("Recording stopped")
            except Exception as e:
                logger.error(f"Error stopping recording: {e}")
            finally:
                self.cleanup()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Capture images or record video from Raspberry Pi 5 camera",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
IMAGE CAPTURE EXAMPLES:
  # Capture a single image
  python3 camera.py image
  
  # Capture 5 images with custom output name
  python3 camera.py image --count 5 --output photo.jpg
  
  # Capture with custom resolution
  python3 camera.py image --resolution 2560 1920

VIDEO RECORDING EXAMPLES:
  # Record indefinitely (press Ctrl+C to stop)
  python3 camera.py video
  
  # Record for 30 seconds
  python3 camera.py video --duration 30
  
  # Record with custom filename
  python3 camera.py video --output my_video.mp4
  
  # Record with custom resolution and framerate
  python3 camera.py video --resolution 1280 720 --fps 24
        """
    )
    
    # Positional argument for mode
    parser.add_argument(
        'mode',
        choices=['image', 'video'],
        help='Operation mode: capture image or record video'
    )
    
    # Common arguments
    parser.add_argument(
        '-r', '--resolution',
        type=int,
        nargs=2,
        default=[1920, 1080],
        metavar=('WIDTH', 'HEIGHT'),
        help='Resolution (default: 1920 1080)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output filename'
    )
    
    # Image-specific arguments
    parser.add_argument(
        '-c', '--count',
        type=int,
        default=1,
        help='Number of images to capture (default: 1)'
    )
    
    # Video-specific arguments
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=None,
        help='Recording duration in seconds (default: indefinite)'
    )
    parser.add_argument(
        '-f', '--fps',
        type=int,
        default=30,
        dest='framerate',
        help='Video framerate in fps (default: 30)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'image':
            capturer = ImageCapture(resolution=tuple(args.resolution))
            capturer.capture(filename=args.output, count=args.count)
        elif args.mode == 'video':
            recorder = VideoRecorder(
                duration=args.duration,
                resolution=tuple(args.resolution),
                framerate=args.framerate
            )
            recorder.start(filename=args.output)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
