import threading
import time
import subprocess, io
import signal
import os
import utils


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
        self._first_event_timestamp = None
        self._capturing = False

    def _capture_video(self):
        start = time.time()
        command = f'ffmpeg -loglevel warning -nostats -y -rtsp_transport tcp -i {self._camera_url} -t {self._capture_timeout} -metadata title="" {self._ffmpeg_options} {self._temp_file_path}{self._camera_name}_tmp.mp4'
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
        if self._capturing:
            self._logger.info(f"Capture video process timed out for {self._camera_name}")
            self.capture_end()

    def _capture_image(self):
        filename = f"{self._first_event_timestamp}_{self._event_timestamp}_{self._camera_name}"
        start = time.time()
        utils.urlopen_to_file(self._logger, self._camera_image_url, f"{self._image_file_path}{filename}.jpeg", 8)
        elapsed = time.time() - start
        self._logger.info(
            f"Capture image done for {self._camera_name} in {elapsed:.1f}s"
        )

    def capture_start(self):
        if self._capturing:
            return
        self._capturing = True
        video_thread = threading.Thread(target=self._capture_video, args=(), kwargs={})

        video_thread.start()

    def capture_keep(self, timestamp):
        if not self._capturing:
            return
        if self._first_event_timestamp is None:
            self._first_event_timestamp = timestamp
        self._event_timestamp = timestamp
        image_thread = threading.Thread(target=self._capture_image, args=(), kwargs={})
        image_thread.start()

    def capture_end(self):
        if not self._capturing:
            return
        self._capturing = False

        pgid = None
        try:
            pgid = os.getpgid(self._capture_video_process.pid)
        except Exception:
            self._logger.info(f"No running video process for {self._camera_name}")
        if pgid is not None:
            self._logger.info(f"Terminating video process for {self._camera_name}")
            os.killpg(pgid, signal.SIGTERM)
        
        
        if self._first_event_timestamp is not None:
            self._logger.info(
                f"Keeping captured video file ({self._first_event_timestamp}) for {self._camera_name}"
            )
            filename = f"{self._video_file_path}{self._first_event_timestamp}_{self._camera_name}.mp4"
            temp_file = f"{self._temp_file_path}{self._camera_name}_tmp.mp4"
            if os.path.isfile(temp_file):
                os.rename(temp_file, filename)
            else:
                 self._logger.error(f"No capture output produced ({self._first_event_timestamp}) for {self._camera_name}")

            self._event_timestamp = None
            self._first_event_timestamp = None
        else:
            self._logger.info(f"Discarding captured video file ({self._first_event_timestamp}) for {self._camera_name}")
            os.remove(f"{self._temp_file_path}{self._camera_name}_tmp.mp4")
