#!/usr/bin/env python3
"""
Raspberry Pi 5 Camera Livestream Server
Streams live camera feed to a web browser via MJPEG in real-time.
"""
motion_timer = 0
motion_recording = False
MOTION_RECORD_SECONDS = 5
prev_frame = None
motion_detected = False
import threading
import logging
import time
from datetime import datetime
from pathlib import Path
from io import BytesIO
from flask import Flask, render_template_string, Response, jsonify
from PIL import Image
import numpy as np
import cv2
try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder, JpegEncoder, MJPEGEncoder
    from picamera2.outputs import FfmpegOutput, FileOutput
except ImportError:
    print("Error: picamera2 is not installed")
    exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)

# Global variables
camera = None
frame_buffer = None
frame_lock = threading.Lock()
streaming = False
recording = False
recording_output = None


# HTML template for the web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi 5 Camera Livestream</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 1200px;
            width: 100%;
            padding: 30px;
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 2em;
        }
        
        .status {
            text-align: center;
            color: #666;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        
        .status.live {
            color: #27ae60;
            font-weight: bold;
        }
        
        .status.live::before {
            content: "● ";
            color: #27ae60;
            font-size: 1.2em;
            margin-right: 5px;
        }
        
        .video-container {
            position: relative;
            width: 100%;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 20px;
            aspect-ratio: 16 / 9;
        }
        
        #stream {
            width: 100%;
            height: 100%;
            display: block;
            background: #000;
        }
        
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        
        button {
            padding: 12px 20px;
            font-size: 1em;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        button:active:not(:disabled) {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-capture {
            background: #3498db;
            color: white;
        }
        
        .btn-capture:hover:not(:disabled) {
            background: #2980b9;
        }
        
        .btn-record {
            background: #e74c3c;
            color: white;
        }
        
        .btn-record:hover:not(:disabled) {
            background: #c0392b;
        }
        
        .btn-record.recording {
            background: #27ae60;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .info {
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 0.9em;
            color: #555;
            display: none;
        }
        
        .error {
            background: #fadbd8;
            border-left: 4px solid #e74c3c;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 0.9em;
            color: #c0392b;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Raspberry Pi 5 Livestream</h1>
        <div class="status live" id="status">LIVE</div>
        
        <div class="video-container">
            <img id="stream" src="/video_feed" alt="Camera Stream">
        </div>
        
        <div class="controls">
            <button class="btn-capture" onclick="captureImage()">📸 Capture</button>
            <button class="btn-record" id="recordBtn" onclick="toggleRecording()">🔴 Record</button>
        </div>
        
        <div id="message" class="info"></div>
        <div id="error" class="error"></div>
    </div>
    
    <script>
        let isRecording = false;
        let streamTimeout;
        
        // Keep refreshing the stream
        function refreshStream() {
            const img = document.getElementById('stream');
            const now = new Date().getTime();
            img.src = '/video_feed?t=' + now;
            streamTimeout = setTimeout(refreshStream, 100);
        }
        
        function captureImage() {
            const button = event.target;
            button.disabled = true;
            
            fetch('/capture')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('📸 Image captured: ' + data.filename);
                    } else {
                        showError('Failed to capture image: ' + data.error);
                    }
                })
                .catch(error => {
                    showError('Failed to capture image: ' + error);
                })
                .finally(() => {
                    button.disabled = false;
                });
        }
        
        function toggleRecording() {
            const button = event.target;
            button.disabled = true;
            
            const action = isRecording ? 'stop_recording' : 'start_recording';
            
            fetch('/' + action, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        isRecording = !isRecording;
                        if (isRecording) {
                            button.classList.add('recording');
                            button.textContent = '⏹️ Stop Recording';
                            showMessage('🔴 Recording started: ' + data.filename);
                        } else {
                            button.classList.remove('recording');
                            button.textContent = '🔴 Record';
                            showMessage('Recording stopped');
                        }
                    } else {
                        showError('Failed: ' + data.error);
                    }
                })
                .catch(error => {
                    showError('Failed to toggle recording: ' + error);
                })
                .finally(() => {
                    button.disabled = false;
                });
        }
        
        function showMessage(msg) {
            const msgDiv = document.getElementById('message');
            msgDiv.textContent = msg;
            msgDiv.style.display = 'block';
            setTimeout(() => {
                msgDiv.style.display = 'none';
            }, 3000);
        }
        
        function showError(msg) {
            const errDiv = document.getElementById('error');
            errDiv.textContent = msg;
            errDiv.style.display = 'block';
        }
        
        // Start streaming when page loads
        window.addEventListener('load', refreshStream);
        window.addEventListener('beforeunload', () => clearTimeout(streamTimeout));
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    """Stream individual JPEG frames."""
    def generate():
        """Generate frames continuously."""
        while streaming:
            try:
                with frame_lock:
                    if frame_buffer is not None:
                        # frame_buffer is the raw JPEG data from JpegEncoder
                        frame_data = frame_buffer
                        # Send as MJPEG frame
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n'
                            b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n\r\n'
                            + frame_data + b'\r\n'
                        )
                    else:
                        time.sleep(0.01)
                        continue
                
                time.sleep(0.01)  # Small delay to prevent 100% CPU
            except Exception as e:
                logger.error(f"Stream error: {e}")
                time.sleep(0.1)
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/capture')
def capture():
    """Capture a still image."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}.jpg"
        
        request_obj = camera.capture_request()
        request_obj.save("main", filename)
        request_obj.release()
        
        logger.info(f"Image captured: {filename}")
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        logger.error(f"Error capturing image: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/start_recording', methods=['POST'])
def start_recording():
    global recording, recording_output

    if recording:
        return jsonify({'success': False, 'error': 'Already recording'})

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.mp4"

        encoder = H264Encoder(bitrate=10000000)
        output = FfmpegOutput(filename)

        camera.start_recording(encoder, output)
        recording = True

        return jsonify({'success': True, 'filename': filename})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    """Stop recording video."""
    global recording, recording_output
    
    if not recording:
        return jsonify({'success': False, 'error': 'Not recording'})
    
    try:
        camera.stop_recording()
        recording = False
        logger.info("Recording stopped")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        return jsonify({'success': False, 'error': str(e)})


def frame_capture_thread():
    """Continuously capture frames from camera."""
    global frame_buffer, streaming, prev_frame
    global motion_recording, motion_timer
    print("THREAD STARTED")
    logger.info("Frame capture thread started")

    while streaming:
        try:
            frame = camera.capture_array()

            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_frame is None:
                prev_frame = gray
                continue

            frame_delta = cv2.absdiff(prev_frame, gray)
            print("Delta mean:", np.mean(frame_delta))

            thresh = cv2.threshold(frame_delta, 10, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours, _ = cv2.findContours(
                thresh.copy(),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            print("Contours found:", len(contours))

            motion_detected = False

            for contour in contours:
                area = cv2.contourArea(contour)
                print("Area:", area)

                if area < 500:
                    continue

                motion_detected = True

                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

            if motion_detected:
                print("MOTION!")
                cv2.putText(frame, "MOTION DETECTED",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 0, 255),
                            2)
            if motion_recording:
                if time.time() - motion_timer > MOTION_RECORD_SECONDS:
                    print("Stopping motion recording")

                    try:
                        camera.stop_recording()
                        motion_recording = False
                    except Exception as e:
                        print("Error stopping recording:", e)
            if not motion_recording:
                print("Starting motion recording")
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"motion_{timestamp}.mp4"

                    encoder = H264Encoder(bitrate=10000000)
                    output = FfmpegOutput(filename)

                    camera.start_recording(encoder, output)
                    motion_recording = True
                except Exception as e:
                    print("Error starting motion recording:", e)
       
            prev_frame = gray

            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

            with frame_lock:
                frame_buffer = jpeg.tobytes()

            time.sleep(0.03)

        except Exception as e:
            print("ERROR:", e)
            time.sleep(0.05)


def initialize_camera(resolution=(1280, 720), fps=24):
    """Initialize the camera."""
    global camera, streaming
    
    try:
        logger.info("Initializing camera...")
        camera = Picamera2()
        
        config = camera.create_video_configuration(
            main={"format": "RGB888", "size": resolution}
        )
        camera.configure(config)
        camera.start()
        
        streaming = True
        
        # Start frame capture thread
        capture_thread = threading.Thread(target=frame_capture_thread, daemon=True)
        capture_thread.start()
        
        logger.info(f"Camera initialized: {resolution} @ {fps}fps")
        return True
    except Exception as e:
        logger.error(f"Error initializing camera: {e}")
        return False


def cleanup_camera():
    """Clean up camera resources."""
    global camera, streaming
    
    streaming = False
    time.sleep(0.005)
    
    if camera:
        try:
            if recording:
                camera.stop_recording()
            camera.stop()
            camera.close()
            logger.info("Camera cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up camera: {e}")
    
    # Clean up temp frame file
    try:
        import os
        if os.path.exists("temp_frame.jpg"):
            os.remove("temp_frame.jpg")
    except:
        pass


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Raspberry Pi 5 Camera Livestream Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Start livestream server on localhost:5000
  python3 livestream.py
  
  # Make accessible from network (0.0.0.0 = all interfaces)
  python3 livestream.py --host 0.0.0.0
  
  # Custom port
  python3 livestream.py --port 8080
  
  # Custom resolution
  python3 livestream.py --resolution 1280 720
  
ACCESS FROM BROWSER:
  Local: http://localhost:5000
  Network: http://<raspberry-pi-ip>:5000
        """
    )
    
    parser.add_argument('-p', '--port', type=int, default=5000,
                        help='Port to run server on (default: 5000)')
    parser.add_argument('-H', '--host', type=str, default='127.0.0.1',
                        help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('-r', '--resolution', type=int, nargs=2, default=[1920, 1080],
                        metavar=('WIDTH', 'HEIGHT'),
                        help='Camera resolution (default: 1920 1080)')
    parser.add_argument('-f', '--fps', type=int, default=30,
                        help='Framerate in fps (default: 30)')
    
    args = parser.parse_args()
    
    try:
        if initialize_camera(tuple(args.resolution), args.fps):
            logger.info(f"🚀 Starting livestream server on http://{args.host}:{args.port}")
            app.run(host=args.host, port=args.port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        cleanup_camera()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        cleanup_camera()
