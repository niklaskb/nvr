import sys
from flask import Flask
from flask import request, send_from_directory
from flask import Response
import logging
from datetime import datetime
import threading
import cv2
import time
import pytz
from os import listdir
import subprocess, io

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

class RemoteCamera(object):
    def __init__(self, camera_url_full, camera_url_low, max_unread_frames, capture_timeout, file_path):
        self.unread_frames = 0
        self._is_streaming = False
        self._state_lock = threading.Lock()
        self._stream_video_thread = None
        self._capture_video_process = None

        self._camera_url_full = camera_url_full
        self._camera_url_low = camera_url_low
        self._max_unread_frames = max_unread_frames
        self._capture_timeout = capture_timeout
        self._file_path = file_path

    def __del__(self):
        with self._state_lock:
            self._is_streaming = False
        if self._stream_video_thread is not None:
            self._stream_video_thread.join()

    def get_frame(self):
        self._start_stream_if_not_started()
        time.sleep(0.2)

        with self._state_lock:
            self.unread_frames = 0

        #width = 1280
        #height = 720
        #resized = cv2.resize(current_frame, (width, height), interpolation = cv2.INTER_AREA)
        frame = bytearray(cv2.imencode(".jpeg", self.frame)[1])
        return frame

    def _start_stream_if_not_started(self):
        self._state_lock.acquire()
        if self._is_streaming:
            self._state_lock.release()
            return
        else:
            app.logger.info("Starting camera stream")
            self._is_streaming = True
            self.unread_frames = 0
            self._state_lock.release()

        self.video_capture = cv2.VideoCapture(self._camera_url_low)
        self._stream_video_thread = threading.Thread(target=self._stream)
        self._stream_video_thread.start()

        while True:
            with self._state_lock:
                if self.unread_frames > 0:
                    break
            time.sleep(0.1)

        app.logger.info("Camera stream started")

    def _stream(self):
        app.logger.info("Streaming start")
        while True:
            with self._state_lock:
                if not self._is_streaming:
                    app.logger.info("Stopping camera stream (shutdown)")
                    break
                if self.unread_frames > self._max_unread_frames:
                    app.logger.info("Stopping camera stream (no consumer)")
                    break

            self.success, self.frame = self.video_capture.read()
            with self._state_lock:
                self.unread_frames = self.unread_frames + 1
        self.video_capture.release()
        with self._state_lock:
            self._is_streaming = False
            self.unread_frames = 0
        app.logger.info("Camera stream stopped")

    def _capture_video(self, filename):
        start = time.time()
        command = f"ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {camera_url_full} -use_wallclock_as_timestamps 1 -metadata title=\"\" -f mp4 -t {self._capture_timeout} -c copy -movflags frag_keyframe+separate_moof+default_base_moof+empty_moov {self._file_path}{filename}.mp4"
        app.logger.info(f"Launching capture video process: {command}")
        self._capture_video_process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=-1)
        output = io.TextIOWrapper(self._capture_video_process.stdout)
        self._capture_video_process.wait()
        output
        self._capture_video_process = None
        elapsed = time.time() - start
        app.logger.info(f"Capture video process done in {elapsed:.1f}s")

    def _capture_image(self, filename):
        start = time.time()
        command = f"ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {camera_url_full} -frames:v 1 {self._file_path}{filename}.jpeg"
        app.logger.info(f"Launching capture image process: {command}")
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=-1)
        output = io.TextIOWrapper(process.stdout)
        process.wait()
        output
        elapsed = time.time() - start
        app.logger.info(f"Capture image process done in {elapsed:.1f}s")

    def capture_start(self):
        if self._capture_video_process:
            return
        filename = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.capture_video_thread = threading.Thread(target=self._capture_video, args=(filename,), kwargs={})
        self.capture_video_thread.start()
        self._capture_image(filename)
        self._start_stream_if_not_started()

    def capture_end(self):
        if self._capture_video_process:
            self._capture_video_process.terminate()

    def get_latest_file(self, type):
        files = list(filter(lambda x: x.endswith(type), listdir(self._file_path)))
        files.sort(reverse=True)
        if len(files) > 0:
            return files[0]
        else:
            return None

@app.route("/videos")
def get_videos():
    html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Recordings</title>
    </head>
    <body>
        <ul>
"""
    timezone = pytz.timezone('Europe/Stockholm')
    video_files = list(filter(lambda x: x.endswith(".mp4"), listdir(file_path)))
    video_files.sort(reverse=True)
    for video_file in video_files:
        local_time = timezone.localize(datetime.strptime(video_file[:-5], "%Y%m%d_%H%M%S")).strftime("%Y-%m-%d %H:%M:%S")
        html += f"<li><a target=\"_blank\" href=\"./videos/{video_file}\">{local_time}</a></li>"

    html += """
        </ul>
    </body>
</html>
"""
    return html

@app.route("/videos/<path:file>")
def get_videos_file(file):
    return send_from_directory(file_path, file, cache_timeout = 0)

@app.route("/video/stream")
def get_video_stream():
    html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Video</title>
    </head>
    <body style="margin:0; height:100%; background-color: #000;">
        <script>
            function sleep(ms) {
                return new Promise(resolve => setTimeout(resolve, ms));
            }

            async function reload() {
                await sleep(1000);
                window.location.reload();
            }
        </script>
        <a target="_blank" href="./stream"><img id="video-image" onerror="reload();" src="./stream/mjpeg" style="width:100%;" alt="video"></img></a>
    </body>
</html>
"""
    return html

def latest_file(type):
    files = list(filter(lambda x: x.endswith(type), listdir(file_path)))
    files.sort(reverse=True)
    if len(files) > 0:
        return send_from_directory(file_path, files[0], cache_timeout = 0)
    else:
        return "Not found", 404

@app.route("/videos/latest")
def get_videos_latest():
    file = camera.get_latest_file(".mp4")
    if file:
        return send_from_directory(file_path, file, cache_timeout = 0)
    else:
        return "Not found", 404

@app.route("/images/latest")
def get_images_latest():
    file = camera.get_latest_file(".jpeg")
    if file:
        return send_from_directory(file_path, file, cache_timeout = 0)
    else:
        return "Not found", 404

@app.route("/capture/start")
def get_capture_start():
    camera.capture_start()
    return "OK"

@app.route("/capture/end")
def get_capture_end():
    camera.capture_end()
    return "OK"

def http_stream(camera):
    while True:
        frame = camera.get_frame()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

@app.route("/video/stream/mjpeg")
def get_video_stream_mjpeg():
    return Response(http_stream(camera),
        mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    camera_url_full = sys.argv[1] 
    camera_url_low = sys.argv[2]
    max_unread_frames = int(sys.argv[3])
    capture_timeout = int(sys.argv[4])
    file_path = sys.argv[5]
    camera = RemoteCamera(camera_url_full, camera_url_low, max_unread_frames, capture_timeout, file_path)
    app.run(host="0.0.0.0")
