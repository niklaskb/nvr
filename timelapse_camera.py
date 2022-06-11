from datetime import datetime, timedelta
import time
import urllib.request
import ssl
import threading
from os import listdir
import subprocess, io
import os
import psutil

class TimelapseCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_image_url,
        ffmpeg_options,
        video_file_path,
        temp_file_path,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_image_url = camera_image_url
        self._ffmpeg_options = ffmpeg_options
        self._video_file_path = video_file_path
        self._temp_file_path = temp_file_path

        self._capture_image_thread = None

    def capture_image_async(self):
        self._capture_image_thread = threading.Thread(
            target=self._capture_image
        )
        self._capture_image_thread.start()

    def _capture_image(self):
        self._logger.debug( f"Starting timelapse image capture for {self._camera_name}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self._camera_name}"
        start = time.time()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(self._camera_image_url, context=ctx) as u, open(f"{self._temp_file_path}{filename}.jpeg", 'wb') as f:
            f.write(u.read())
        elapsed = time.time() - start
        self._logger.info( f"Capture timelapse image done for {self._camera_name} in {elapsed:.1f}s")

    def _preexec_fn(self):
        try:
            os.setsid()
            pid = os.getpid()
            ps = psutil.Process(pid)
            ps.nice(19)
        except Exception as err:
            self._logger.error(f"Failed execute preexec_fn: {err}")
        
    def _build_video(self, date):
        start = time.time()
        command = f'ffmpeg -loglevel error -nostats -y -framerate 24 -pattern_type  glob -i "{self._temp_file_path}{date}_*_{self._camera_name}.jpeg" -metadata title="" {self._ffmpeg_options} {self._video_file_path}{date}_{self._camera_name}.mp4'
        self._logger.info(
            f"Launching timelapse video build process for {self._camera_name}: {command}"
        )
        build_video_process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=-1,
            preexec_fn=self._preexec_fn,
        )
        output = io.TextIOWrapper(build_video_process.stdout)
        build_video_process.wait()
        output
        elapsed = time.time() - start
        self._logger.info(
            f"Timelapse video build process for {self._camera_name} done in {elapsed:.1f}s"
        )

    def build_video(self):
        yesterdays_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        self._build_video(yesterdays_date)

        files = list(
            filter(lambda x: x.endswith(".jpeg"), listdir(self._temp_file_path))
        )

        if os.path.isfile(f"{self._video_file_path}{yesterdays_date}_{self._camera_name}.mp4"):
            for file in files:
                d = file.rsplit("_", 2)[1]
                if d == yesterdays_date:
                    os.remove(f"{self._temp_file_path}/{file}")
