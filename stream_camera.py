from queue import Empty
import threading
import cv2
import time
import numpy
import multiprocessing
import os


class StreamCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        frame_sleep,
        width,
        height,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._frame_sleep = frame_sleep
        self._width = width
        self._height = height

        self._streaming_process = None
        self._queue = multiprocessing.Queue()

    def get_jpeg(self):
        frame = self.get_frame()
        return bytearray(cv2.imencode(".jpeg", frame)[1])

    def get_frame(self):
        self._start_streaming()

        return self._queue.get()

    def _start_streaming(self):
        if self._streaming_process is None or not self._streaming_process.is_alive():
            self._streaming_process = multiprocessing.Process(
                target=self._stream,
                args=(
                    self._logger,
                    self._camera_name,
                    self._camera_url,
                    self._frame_sleep,
                    self._width,
                    self._height,
                    self._queue,
                ),
            )
            self._streaming_process.start()

    def _stream(
        self,
        logger,
        camera_name,
        camera_url,
        frame_sleep,
        width,
        height,
        queue,
    ):
        camera = _InternalStreamCamera(
            logger,
            camera_name,
            camera_url,
            frame_sleep,
            width,
            height,
            queue,
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
        queue,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._frame_sleep = frame_sleep
        self._width = width
        self._height = height
        self._queue = queue

        self._is_streaming = False
        self._is_loading = False
        self._is_paused = False
        self._unread_frames = 0
        self._max_unread_frames = 100

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

    def _create_empty_image(self):
        return numpy.zeros((self._height, self._width, 3), numpy.uint8)

    def _put_frame(self, frame):
        if self._queue.empty():
            self._unread_frames = 0
        else:
            try:
                while not self._queue.empty():
                    self._queue.get_nowait()
                self._unread_frames = self._unread_frames + 1
            except Empty:
                self._unread_frames = 0
        self._queue.put(frame)

    def _show_static_frame(self):
        time.sleep(self._frame_sleep)  # Yield to other thread
        frame = self._static_frame
        while frame is not None:
            self._put_frame(frame)
            time.sleep(self._frame_sleep)
            frame = self._static_frame

    def stream(self):
        if self._is_streaming:
            return
        self._is_streaming = True
        self._is_loading = True
        self._unread_frames = 0

        self._logger.info(f"Starting camera stream for {self._camera_name}")

        self._static_frame = self._create_loading_image()

        self._show_static_frame_thread = threading.Thread(
            target=self._show_static_frame
        )
        self._show_static_frame_thread.start()

        self._video_capture = cv2.VideoCapture(self._camera_url)
        while True:
            success = self._video_capture.grab()

            if not success:
                self._logger.info(f"Failed to grab frame for {self._camera_name}")
                self._static_frame = self._create_fail_image()
                time.sleep(10)
                self._static_frame = None
                self._show_static_frame_thread.join()
                break

            if (
                not self._queue.empty()
                and self._unread_frames > self._max_unread_frames
            ):
                if not self._is_paused:
                    self._is_paused = True
                    self._put_frame(self._create_empty_image())
                    self._logger.info(f"Paused camera stream for {self._camera_name}")
            else:
                success, frame = self._video_capture.retrieve()

                if self._is_paused:
                    self._is_paused = False
                    self._logger.info(f"Resumed camera stream for {self._camera_name}")

                if self._is_loading:
                    self._is_loading = False
                    self._static_frame = None
                    self._show_static_frame_thread.join()
                    self._logger.info(f"Started camera stream for {self._camera_name}")

                self._put_frame(frame)
            time.sleep(0.01)

        self._video_capture.release()
        self._frame = None
        self._is_streaming = False
        self._is_loading = False
        try:
            self._queue.get_nowait()
        except Empty:
            pass
        self._logger.info(f"Camera stream stopped for {self._camera_name}")
