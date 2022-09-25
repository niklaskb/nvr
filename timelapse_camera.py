from datetime import datetime, timedelta
import time
import threading
from os import listdir
import subprocess, io
import os
import psutil
import utils
from datetime import timezone

class TimelapseCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_image_url,
        ffmpeg_options,
        video_file_path,
        image_file_path,
        hours,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_image_url = camera_image_url
        self._ffmpeg_options = ffmpeg_options
        self._video_file_path = video_file_path
        self._image_file_path = image_file_path
        self._hours = hours

        self._capture_image_thread = None

    def capture_image_async(self):
        self._logger.info(f"Triggered timelapse for {self._camera_name}")
        self._capture_image_thread = threading.Thread(
            target=self._capture_image
        )
        self._capture_image_thread.start()

    def _capture_image(self):
        hour = int(datetime.now(tz=timezone.utc).strftime("%H"))

        if not hour in self._hours:
            self._logger.info(f"Timelapse not configured for hour {hour}, skipping")
            return

        padded_hour = f'{hour:02}'
        self._logger.info(f"Starting timelapse image capture for {self._camera_name} and hour {padded_hour}")

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{padded_hour}_{self._camera_name}"
        start = time.time()
        utils.urlopen_to_file(self._logger, self._camera_image_url, f"{self._image_file_path}{filename}.jpeg", 4)
        elapsed = time.time() - start
        self._logger.info(f"Capture timelapse image done for {self._camera_name} in {elapsed:.1f}s")

    def _preexec_fn(self):
        try:
            os.setsid()
            pid = os.getpid()
            ps = psutil.Process(pid)
            ps.nice(19)
        except Exception as err:
            self._logger.error(f"Failed execute preexec_fn: {err}")
        
    def _build_video(self, year, padded_hour):
        start = time.time()
        command = f'ffmpeg -loglevel error -nostats -y -framerate 7 -pattern_type  glob -i "{self._image_file_path}{year}*_{padded_hour}_{self._camera_name}.jpeg" -metadata title="" {self._ffmpeg_options} {self._video_file_path}{year}_{padded_hour}_{self._camera_name}.mp4'
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

    def build_videos(self):
        year = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y")
        old_year = (datetime.now(tz=timezone.utc) - timedelta(days=2)).strftime("%Y")

        for hour in range(0, 23):
            padded_hour = f'{hour:02}'
            files = list(
                filter(lambda x: (x.startswith(old_year) and x.endswith(f"_{padded_hour}_{self._camera_name}.jpeg")), listdir(self._image_file_path))
            )
            if len(files) > 0:
                self._build_video(year, padded_hour)

                if year != old_year and os.path.isfile(f"{self._video_file_path}{year}_{padded_hour}_{self._camera_name}.mp4"):
                    for file in files:
                        os.remove(f"{self._image_file_path}/{file}")
