import threading
import cv2
import time
import numpy


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
        self._unread_frames = 0
        self._is_streaming = False
        self._is_loading = False
        self._is_failing = False
        self._frame = None
        self._stream_video_thread = None
        self._width = width
        self._height = height

        self._camera_name = camera_name
        self._camera_url = camera_url
        self._max_unread_frames = max_unread_frames
        self._frame_sleep = frame_sleep

        self._animation_index = 0
        self._animation = [".", "..", "...", ".."]
        self._animation_speed = 0.5
        self._animation_last = None

    def __del__(self):
        self._is_streaming = False
        self._frame = None
        if self._stream_video_thread is not None:
            self._stream_video_thread.join()

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

    def get_jpeg(self):
        frame = self.get_frame()
        return bytearray(cv2.imencode(".jpeg", frame)[1])

    def get_frame(self):
        self.start_streaming()

        while True:
            if self._frame is not None:
                frame = self._frame
                self._frame = None
                self._unread_frames = 0
                return frame
            elif self._is_loading:
                time.sleep(self._frame_sleep)
                if (
                    self._animation_last == None
                    or time.time() - self._animation_last > self._animation_speed
                ):
                    self._animation_last = time.time()
                    if self._is_failing:
                        self._frame = self._create_fail_image()
                    else:
                        self._frame = self._create_loading_image()
            else:
                time.sleep(self._frame_sleep)

    def start_streaming(self):
        if self._is_streaming:
            return

        self._logger.info(f"Starting camera stream for {self._camera_name}")
        self._is_streaming = True
        self._unread_frames = 0
        self._is_loading = True

        self._stream_video_thread = threading.Thread(target=self._stream)
        self._stream_video_thread.start()

        self._frame = self._create_loading_image()

    def _stream(self):
        time.sleep(self._frame_sleep)  # Yield to other thread
        self._logger.info(f"Streaming starting for {self._camera_name}")
        self.video_capture = cv2.VideoCapture(self._camera_url)
        while True:
            if not self._is_streaming:
                self._logger.info(
                    f"Stopping camera stream for {self._camera_name} (shutdown)"
                )
                break
            if self._unread_frames > self._max_unread_frames:
                self._logger.info(
                    f"Stopping camera stream for {self._camera_name} (no consumer)"
                )
                break

            success, self._frame = self.video_capture.read()
            if not success:
                self._logger.info(f"Failed to read frame for {self._camera_name}")
                self._frame = self._create_fail_image()
                self._is_failing = True
                time.sleep(10)
                break

            if self._is_loading:
                self._is_loading = False
                self._is_failing = False
                self._animation_index = 0
                self._animation_last = None

            self._unread_frames = self._unread_frames + 1

        self.video_capture.release()
        self._is_streaming = False
        self._frame = None
        self._unread_frames = 0
        self._logger.info(f"Camera stream stopped for {self._camera_name}")
