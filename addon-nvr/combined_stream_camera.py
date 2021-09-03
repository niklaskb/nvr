import threading
import cv2
import time
import numpy


class CombinedStreamCamera(object):
    def __init__(
        self,
        logger,
        stream_cameras,
        width,
        height,
        config
    ):
        self._logger = logger
        self._stream_cameras = stream_cameras
        self._width = width
        self._height = height
        self._config = config


    def get_jpeg(self):
        img = numpy.zeros((self._height, self._width, 3), numpy.uint8)
        for camera_name, camera_config in self._config.items():
            stream_camera = self._stream_cameras[camera_name]
            
            height = camera_config["height"]
            width = camera_config["width"]

            frame = stream_camera.get_frame()

            resized = cv2.resize(frame, (width, height))

            offset_height = camera_config["offset_height"]
            offset_width = camera_config["offset_width"]

            img[offset_height:offset_height+height, offset_width:offset_width+width] = resized
        return bytearray(cv2.imencode(".jpeg", img)[1])
