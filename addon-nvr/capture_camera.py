from datetime import datetime
import threading
import time
from os import listdir
import subprocess, io


class CaptureCamera(object):
    def __init__(self, logger, camera_url_full, file_path, capture_timeout):
        self._logger = logger
        self._capture_video_process = None
        self._camera_url_full = camera_url_full
        self._file_path = file_path
        self._capture_timeout = capture_timeout

    def _capture_video(self, filename):
        start = time.time()
        command = f'ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {self._camera_url_full} -use_wallclock_as_timestamps 1 -metadata title="" -f mp4 -t {self._capture_timeout} -c copy -movflags frag_keyframe+separate_moof+default_base_moof+empty_moov {self._file_path}{filename}.mp4'
        self._logger.info(f"Launching capture video process: {command}")
        self._capture_video_process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, bufsize=-1
        )
        output = io.TextIOWrapper(self._capture_video_process.stdout)
        self._capture_video_process.wait()
        output
        self._capture_video_process = None
        elapsed = time.time() - start
        self._logger.info(f"Capture video process done in {elapsed:.1f}s")

    def _capture_image(self, filename):
        start = time.time()
        command = f"ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {self._camera_url_full} -frames:v 1 {self._file_path}{filename}.jpeg"
        self._logger.info(f"Launching capture image process: {command}")
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, bufsize=-1
        )
        output = io.TextIOWrapper(process.stdout)
        process.wait()
        output
        elapsed = time.time() - start
        self._logger.info(f"Capture image process done in {elapsed:.1f}s")

    def capture_start(self):
        if self._capture_video_process:
            return
        filename = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._capture_video_thread = threading.Thread(
            target=self._capture_video, args=(filename,), kwargs={}
        )
        self._capture_video_thread.start()
        self._capture_image(filename)

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
