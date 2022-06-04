from queue import Empty
import threading
import cv2
import time
import numpy
import multiprocessing
import os
from datetime import datetime
import logging
import sys


class StreamCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        frame_sleep,
        width,
        height,
        restart_threshold,
    ):
        self._logger = logger
        self._frame_sleep = frame_sleep

        self._return_frame_queue = multiprocessing.Queue()
        self._request_frame_queue = multiprocessing.Queue()

        self._streaming_process = multiprocessing.Process(
            target=self._stream,
            args=(
                camera_name,
                camera_url,
                frame_sleep,
                width,
                height,
                restart_threshold,
                self._return_frame_queue,
                self._request_frame_queue
            ),
        )
        self._streaming_process.start()

    def get_jpeg(self):
        frame = self.get_frame()
        return bytearray(cv2.imencode(".jpeg", frame)[1])

    def get_frame(self):
        time.sleep(self._frame_sleep)
        frame = None
        try:
            if not self._return_frame_queue.empty():
                frame = self._return_frame_queue.get_nowait()
        except Empty:
            pass
        if frame is None:
            self._request_frame_queue.put(True)
            frame = self._return_frame_queue.get()
        return frame

    def _stream(
        self,
        camera_name,
        camera_url,
        frame_sleep,
        width,
        height,
        restart_threshold,
        return_frame_queue,
        request_frame_queue,
    ):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        default_handler = logging.StreamHandler(sys.stdout)
        default_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        logger.addHandler(default_handler)
        camera = _InternalStreamCamera(
            logger,
            camera_name,
            camera_url,
            frame_sleep,
            width,
            height,
            restart_threshold,
            return_frame_queue,
            request_frame_queue,
        )
        os.nice(10)
        camera.stream()

class _InternalStreamCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        frame_sleep,
        width,
        height,
        restart_threshold,
        return_frame_queue,
        request_frame_queue,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._frame_sleep = frame_sleep
        self._width = width
        self._height = height
        self._restart_threshold = restart_threshold
        self._return_frame_queue = return_frame_queue
        self._request_frame_queue = request_frame_queue

        self._streaming = False
        self._loading = False
        self._last_init_timestamp = None
        self._static_frame = None
        self._frame_count = 0
    
    def _get_frame(self):
        if self._static_frame is not None:
            return self._static_frame
        success, frame = self._video_capture.retrieve()
        if not success:
            self._logger.warning(f"Failed to retrieve frame for {self._camera_name}")
        return frame

    def _init_stream(self):
        self._logger.info(f"Initializing camera stream for {self._camera_name}")
        self._video_capture = cv2.VideoCapture(self._camera_url)
        self._logger.info(f"Started camera stream for {self._camera_name}")
        self._streaming = True
        self._loading = False
        self._frame_count = 0

    def stream(self):
        while True:
            if not self._streaming:
                if not self._loading and (self._last_init_timestamp is None or (datetime.now() - self._last_init_timestamp).seconds > 30):
                    self._loading = True
                    self._static_frame = self._create_loading_image()
                    self._last_init_timestamp = datetime.now()
                    self._init_stream_thread = threading.Thread(
                        target=self._init_stream
                    )
                    self._init_stream_thread.start()
            
            if self._streaming:
                success = self._video_capture.grab()

                if not success:
                    self._logger.warning(f"Failed to grab frame for {self._camera_name}")
                    self._static_frame = self._create_fail_image()
                    self._streaming = False
                    self._video_capture.release()
                    self._video_capture = None
                else:
                    self._static_frame = None
                    self._frame_count = self._frame_count + 1
            else:
                time.sleep(self._frame_sleep)
            
            frame = None
            while not self._request_frame_queue.empty():
                if frame is None:
                    frame = self._get_frame()
                self._return_frame_queue.put(frame)
                self._request_frame_queue.get_nowait()

            if self._streaming and self._frame_count > self._restart_threshold:
                self._logger.info(f"Reloading stream for {self._camera_name}")
                self._streaming = False
                self._video_capture.release()
                self._video_capture = None

    def _empty_queue(self):
        try:
            while not self._return_frame_queue.empty():
                self._return_frame_queue.get_nowait()
        except Empty:
            pass

    def _create_loading_image(self):
        img = numpy.zeros((self._height, self._width, 3), numpy.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        bottom_left_corner_of_text = (int(self._width / 2) - 80, int(self._height / 2))
        font_scale = 1
        font_color = (255, 255, 255)
        line_type = 2

        cv2.putText(
            img,
            f"Startar",
            bottom_left_corner_of_text,
            font,
            font_scale,
            font_color,
            line_type,
        )

        return img

    def _create_fail_image(self):
        img = numpy.zeros((self._height, self._width, 3), numpy.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        bottom_left_corner_of_text = (int(self._width / 2) - 80, int(self._height / 2))
        font_scale = 1
        font_color = (255, 255, 255)
        line_type = 2

        cv2.putText(
            img,
            f"Kamerafel",
            bottom_left_corner_of_text,
            font,
            font_scale,
            font_color,
            line_type,
        )

        return img
