#!/usr/bin/env python3
"""
Record 30 seconds of video from the Raspberry Pi camera
"""

import time
from datetime import datetime
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

def record_video(duration=30, resolution=(1920, 1080), fps=30):
    """Record video from the camera for specified duration"""
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"video_recording_{timestamp}.mp4"
    
    print(f"Initializing camera...")
    camera = Picamera2()
    
    # Configure camera
    config = camera.create_video_configuration(
        main={"size": resolution, "format": "RGB888"}
    )
    camera.configure(config)
    
    # Create encoder and output
    encoder = H264Encoder(bitrate=10000000)  # 10 Mbps
    output = FileOutput(output_file)
    
    print(f"Starting recording to {output_file}...")
    camera.start_recording(encoder, output)
    
    # Record for specified duration
    start_time = time.time()
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        print(f"Recording... {elapsed:.1f}s / {duration}s (remaining: {remaining:.1f}s)", end='\r')
        time.sleep(0.1)
    
    print(f"\nStopping recording...")
    camera.stop_recording()
    camera.close()
    
    print(f"Video saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    try:
        record_video(duration=30, resolution=(1920, 1080), fps=30)
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
