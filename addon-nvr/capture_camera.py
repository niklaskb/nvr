from datetime import datetime
import threading
import time
from os import listdir
import subprocess, io
import signal
import os


class CaptureCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        ffmpeg_options,
        video_file_path,
        image_file_path,
        capture_timeout,
    ):
        self._logger = logger
        self._capture_video_process = None
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._ffmpeg_options = ffmpeg_options
        self._video_file_path = video_file_path
        self._image_file_path = image_file_path
        self._capture_timeout = capture_timeout

    def _capture_video(self, filename):
        start = time.time()
        command = f'ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {self._camera_url} -t {self._capture_timeout} -metadata title="" {self._ffmpeg_options} {self._video_file_path}{filename}.mp4'
        self._logger.info(
            f"Launching capture video process for {self._camera_name}: {command}"
        )
        self._capture_video_process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=-1,
            preexec_fn=os.setsid,
        )
        output = io.TextIOWrapper(self._capture_video_process.stdout)
        self._capture_video_process.wait()
        output
        self._capture_video_process = None
        elapsed = time.time() - start
        self._logger.info(
            f"Capture video process for {self._camera_name} done in {elapsed:.1f}s"
        )

    # def _rewrite_video(self, filename):
    #     start = time.time()
    #     command = f'ffmpeg -loglevel panic -nostats -y -i {self._video_file_path}{filename}.tmp.mp4 -metadata title="" -f mp4 -c copy {self._video_file_path}{filename}.mp4'
    #     self._logger.info(f"Launching rewrite video process: {command}")
    #     rewrite_video_process = subprocess.Popen(
    #         command, shell=True, stdout=subprocess.PIPE, bufsize=-1
    #     )
    #     output = io.TextIOWrapper(rewrite_video_process.stdout)
    #     rewrite_video_process.wait()
    #     output
    #     os.remove(f"{self._video_file_path}{filename}.tmp.mp4")
    #     elapsed = time.time() - start
    #     self._logger.info(f"Rewrite video process done in {elapsed:.1f}s")

    def _capture_image(self, filename):
        start = time.time()
        command = f"ffmpeg -loglevel panic -nostats -y -rtsp_transport tcp -i {self._camera_url} -frames:v 1 {self._image_file_path}{filename}.jpeg"
        self._logger.info(
            f"Launching capture image process for {self._camera_name}: {command}"
        )
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, bufsize=-1
        )
        output = io.TextIOWrapper(process.stdout)
        process.wait()
        output
        elapsed = time.time() - start
        self._logger.info(
            f"Capture image process done for {self._camera_name} in {elapsed:.1f}s"
        )

    def capture_start(self, timestamp):
        if self._capture_video_process:
            return
        filename = f"{timestamp}_{self._camera_name}"

        video_thread = threading.Thread(
            target=self._capture_video, args=(filename,), kwargs={}
        )
        image_thread = threading.Thread(
            target=self._capture_image, args=(filename,), kwargs={}
        )

        video_thread.start()
        image_thread.start()

    def capture_end(self):
        if self._capture_video_process:
            self._logger.info(f"Terminating video process for {self._camera_name}")
            os.killpg(os.getpgid(self._capture_video_process.pid), signal.SIGTERM)
