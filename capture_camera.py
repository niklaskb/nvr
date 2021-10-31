from datetime import datetime, timedelta
import threading
import time
from os import listdir
import subprocess, io
import signal
import os
import urllib.request


class CaptureCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        camera_image_url,
        ffmpeg_options,
        video_file_path,
        image_file_path,
        temp_file_path,
        capture_timeout,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._camera_image_url = camera_image_url
        self._ffmpeg_options = ffmpeg_options
        self._video_file_path = video_file_path
        self._image_file_path = image_file_path
        self._temp_file_path = temp_file_path
        self._capture_timeout = capture_timeout
        self._capture_video_process = None
        self._event_timestamp = None
        self._capturing = False

    def _capture_video(self):
        start = time.time()
        command = f'ffmpeg -loglevel error -nostats -y -rtsp_transport tcp -i {self._camera_url} -t {self._capture_timeout} -metadata title="" {self._ffmpeg_options} {self._temp_file_path}{self._camera_name}_tmp.mp4'
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
        elapsed = time.time() - start
        self._logger.info(
            f"Capture video process for {self._camera_name} done in {elapsed:.1f}s"
        )
        self._capture_video_process = None
        self._capturing = False

    # def _rewrite_video(self, filename):
    #     start = time.time()
    #     command = f'ffmpeg -loglevel error -nostats -y -i {self._video_file_path}{filename}.tmp.mp4 -metadata title="" -f mp4 -c copy {self._video_file_path}{filename}.mp4'
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

    # def _capture_image(self):
    #     start = time.time()
    #     command = f"ffmpeg -loglevel error -nostats -y -rtsp_transport tcp -i {self._camera_url} -frames:v 1 {self._temp_file_path}{self._camera_name}_tmp.jpeg"
    #     self._logger.info(
    #         f"Launching capture image process for {self._camera_name}: {command}"
    #     )
    #     process = subprocess.Popen(
    #         command, shell=True, stdout=subprocess.PIPE, bufsize=-1
    #     )
    #     output = io.TextIOWrapper(process.stdout)
    #     process.wait()
    #     output
    #     elapsed = time.time() - start
    #     self._logger.info(
    #         f"Capture image process done for {self._camera_name} in {elapsed:.1f}s"
    #     )

    def _capture_image(self):
        filename = f"{self._event_timestamp}_{self._camera_name}"
        start = time.time()
        urllib.request.urlretrieve(self._camera_image_url, f"{self._image_file_path}{filename}.jpeg")
        elapsed = time.time() - start
        self._logger.info(
            f"Capture image done for {self._camera_name} in {elapsed:.1f}s"
        )

    # def _keep_image(self):
    #     filename = f"{self._event_timestamp}_{self._camera_name}"
    #     start = datetime.now()
    #     while datetime.now() < start + timedelta(seconds=10):
    #         time.sleep(0.5)
    #         if os.path.isfile(f"{self._temp_file_path}{self._camera_name}_tmp.jpeg"):
    #             self._logger.info(
    #                 f"Keeping captured image file for {self._camera_name}"
    #             )
    #             os.rename(
    #                 f"{self._temp_file_path}{self._camera_name}_tmp.jpeg",
    #                 f"{self._image_file_path}{filename}.jpeg",
    #             )
    #             break

    def capture_start(self):
        if self._capturing:
            return
        self._capturing = True
        video_thread = threading.Thread(target=self._capture_video, args=(), kwargs={})
        # image_thread = threading.Thread(target=self._capture_image, args=(), kwargs={})

        video_thread.start()
        # image_thread.start()

    def capture_keep(self, timestamp):
        if not self._capturing:
            return
        self._event_timestamp = timestamp
        image_thread = threading.Thread(target=self._capture_image, args=(), kwargs={})
        image_thread.start()
        # keep_image_thread = threading.Thread(
        #     target=self._keep_image, args=(), kwargs={}
        # )
        # keep_image_thread.start()

    def capture_end(self):
        if not self._capturing:
            return
        self._logger.info(f"Terminating video process for {self._camera_name}")
        os.killpg(os.getpgid(self._capture_video_process.pid), signal.SIGTERM)
        if self._event_timestamp:
            self._logger.info(
                f"Keeping captured video file for {self._camera_name}"
            )
            filename = f"{self._event_timestamp}_{self._camera_name}"
            os.rename(
                f"{self._temp_file_path}{self._camera_name}_tmp.mp4",
                f"{self._video_file_path}{filename}.mp4",
            )
            self._event_timestamp = None
        else:
            self._logger.info(f"Discarding captured video file for {self._camera_name}")
            os.remove(f"{self._temp_file_path}{self._camera_name}_tmp.mp4")