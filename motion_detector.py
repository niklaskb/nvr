import cv2
import numpy
from datetime import datetime, timedelta


class MotionDetector(object):
    def __init__(
        self,
        logger,
        camera_name,
        width,
        height,
        debug_frame,
        motion_callback
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._width = width
        self._height = height
        self._debug_frame = debug_frame
        self._motion_callback = motion_callback

        self._motion_last_timestamp = None
        self.motion = False

    def start(self):
        self._background_subtractor = cv2.createBackgroundSubtractorMOG2(history = 200, varThreshold = 25, detectShadows=False)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))

    def detect_motion(self, frame):
        motion = False

        resized_frame = self._resize(frame, 4)
        visualize_frame_boxes = resized_frame.copy()
        visualize_frame_mask = resized_frame.copy()

        motion_mask_raw = self._background_subtractor.apply(image = resized_frame)
        
        motion_mask = motion_mask_raw
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, self._kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, self._kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_DILATE, self._kernel)
        
        motion_contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        total_area = 0
        for c in motion_contours:
            area = cv2.contourArea(c)
            total_area += area
        
        area_ratio = self._area_ratio(total_area, resized_frame)
        print(area_ratio)
        if area_ratio > 0 and area_ratio < 0.2:
            motion = True

        if motion:
            if self._motion_last_timestamp is None:
                self._motion_callback(self._camera_name, True)
            
            self._motion_last_timestamp = datetime.now()

            for c in motion_contours:
                (x, y, w, h)=cv2.boundingRect(c)
                cv2.rectangle(visualize_frame_boxes, (x, y), (x+w, y+h), (255, 0, 0), 1)

                b,g,r = cv2.split(resized_frame)
                r = cv2.add(r, 100, dst = r, mask = motion_mask, dtype = cv2.CV_8U)
                g = cv2.subtract(g, 50, dst = g, mask = motion_mask, dtype = cv2.CV_8U)
                b = cv2.subtract(b, 50, dst = b, mask = motion_mask, dtype = cv2.CV_8U)
                cv2.merge((b,g,r), visualize_frame_mask)
        
        if not motion and self._motion_last_timestamp is not None and datetime.now() > self._motion_last_timestamp + timedelta(seconds=20):
            self._motion_callback(self._camera_name, False)
            self._motion_last_timestamp = None

        if self._debug_frame:
            debug_frame = self._draw_on_frame([resized_frame, visualize_frame_boxes, motion_mask_raw, visualize_frame_mask], self._height, self._width)
            return debug_frame
        else:
            return None

    def _area_ratio(self, area, image):
        height, width = image.shape[:2]
        return area / (height*width)

    def _resize(self, frame, factor):
        resized_width = int(self._width/factor)
        resized_height = int(self._height/factor)
        return cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)

    def _draw_on_frame(self, frames, height, width):
        img = numpy.zeros((height, width, 3), numpy.uint8)
        position = 0
        for frame in frames:
            resized_width = int(width/2)
            resized_height = int(height/2)
            if frame is None:
                resized = numpy.ones((resized_height, resized_width, 3), numpy.uint8)
            else:
                resized = cv2.resize(frame, (resized_width, resized_height))

            if(len(resized.shape)<3):
                resized = cv2.cvtColor(resized,cv2.COLOR_GRAY2RGB)

            if (position == 0):
                offset_height = 0
                offset_width = 0
            elif (position == 1):
                offset_height = resized_height
                offset_width = 0
            elif (position == 2):
                offset_height = 0
                offset_width = resized_width
            elif (position == 3):
                offset_height = resized_height
                offset_width = resized_width
            
            img[
                offset_height : offset_height + resized_height,
                offset_width : offset_width + resized_width,
            ] = resized
            position = position + 1
        
        return img
