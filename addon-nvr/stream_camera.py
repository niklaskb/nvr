from queue import Empty
import threading
import cv2
import time
import numpy
import multiprocessing


class StreamCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        max_unread_frames,
        frame_sleep,
        width,
        height,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._max_unread_frames = max_unread_frames
        self._frame_sleep = frame_sleep
        self._width = width
        self._height = height

        self._streaming_process = None
        self._queue = multiprocessing.Queue()

    def get_jpeg(self):
        frame = self.get_frame()
        return bytearray(cv2.imencode(".jpeg", frame)[1])

    def get_frame(self):
        if self._streaming_process is None or not self._streaming_process.is_alive():
            self._streaming_process = multiprocessing.Process(
                target=self._stream,
                args=(
                    self._logger,
                    self._camera_name,
                    self._camera_url,
                    self._max_unread_frames,
                    self._frame_sleep,
                    self._width,
                    self._height,
                    self._queue,
                ),
            )
            self._streaming_process.start()

        return self._queue.get()

    def _stream(
        self,
        logger,
        camera_name,
        camera_url,
        max_unread_frames,
        frame_sleep,
        width,
        height,
        queue,
    ):
        camera = _InternalStreamCamera(
            logger,
            camera_name,
            camera_url,
            max_unread_frames,
            frame_sleep,
            width,
            height,
            queue,
        )
        camera.stream()


class _InternalStreamCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        camera_url,
        max_unread_frames,
        frame_sleep,
        width,
        height,
        queue,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._camera_url = camera_url
        self._max_unread_frames = max_unread_frames
        self._frame_sleep = frame_sleep
        self._width = width
        self._height = height
        self._queue = queue

        self._is_streaming = False
        self._is_loading = False
        self._is_failing = False
        self._unread_frames = 0

        self._animation_index = 0
        self._animation = [".", "..", "...", ".."]
        self._animation_speed = 0.5
        self._animation_last = None

    def _create_loading_image(self):
        img = numpy.zeros((self._height, self._width, 3), numpy.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        bottom_left_corner_of_text = (int(self._width / 2) - 80, int(self._height / 2))
        font_scale = 1
        font_color = (255, 255, 255)
        line_type = 2

        cv2.putText(
            img,
            f"Startar {self._animation[self._animation_index]}",
            bottom_left_corner_of_text,
            font,
            font_scale,
            font_color,
            line_type,
        )

        self._animation_index = self._animation_index + 1
        if self._animation_index == len(self._animation):
            self._animation_index = 0
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

    def _put_frame(self, frame):
        if self._queue.empty():
            self._unread_frames = 0
        else:
            try:
                self._queue.get_nowait()
                self._unread_frames = self._unread_frames + 1
            except Empty:
                self._unread_frames = 0
        self._queue.put(frame)

    def _loading(self):
        time.sleep(self._frame_sleep)  # Yield to other thread
        while self._is_loading:
            time.sleep(self._frame_sleep)
            if (
                self._animation_last == None
                or time.time() - self._animation_last > self._animation_speed
            ):
                self._animation_last = time.time()
                if self._is_failing:
                    self._put_frame(self._create_fail_image())
                else:
                    self._put_frame(self._create_loading_image())

    def stream(self):
        if self._is_streaming:
            return
        self._is_streaming = True
        self._is_loading = True
        self._animation_index = 0
        self._animation_last = None
        self._unread_frames = 0

        self._logger.info(f"Starting camera stream for {self._camera_name}")

        self._load_video_thread = threading.Thread(target=self._loading)
        self._load_video_thread.start()

        self._video_capture = cv2.VideoCapture(self._camera_url)
        while True:
            if self._unread_frames > self._max_unread_frames:
                self._logger.info(
                    f"Stopping camera stream for {self._camera_name} (no consumer)"
                )
                break

            success, frame = self._video_capture.read()

            if not success:
                self._logger.info(f"Failed to read frame for {self._camera_name}")
                self._is_failing = True
                time.sleep(10)
                self._is_loading = False
                self._is_failing = False
                break

            if self._is_loading:
                self._is_loading = False
                self._is_failing = False
                self._load_video_thread.join()
                self._logger.info(f"Started camera stream for {self._camera_name}")

            self._put_frame(frame)

        self._video_capture.release()
        self._frame = None
        self._unread_frames = 0
        self._is_streaming = False
        try:
            self._queue.get_nowait()
        except Empty:
            pass
        self._logger.info(f"Camera stream stopped for {self._camera_name}")
