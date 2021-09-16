import glob
import os
from datetime import datetime, timedelta
import threading
import time
import pytz


class FtpCamera(object):
    def __init__(
        self,
        logger,
        camera_name,
        ftp_upload_path,
        image_file_path,
        video_file_path,
        ftp_purge_days,
        event_timeout_seconds,
        image_max_age_seconds,
        video_timeout_seconds,
    ):
        self._logger = logger
        self._camera_name = camera_name
        self._ftp_upload_path = ftp_upload_path
        self._image_file_path = image_file_path
        self._video_file_path = video_file_path
        self._ftp_purge_days = ftp_purge_days
        self._event_timeout_seconds = event_timeout_seconds
        self._image_max_age_seconds = image_max_age_seconds
        self._video_timeout_seconds = video_timeout_seconds

    def event(self):
        event_timestamp = datetime.now()
        self._logger.info(f"Received event at {event_timestamp}")

        event_thread = threading.Thread(
            target=self._event_thread, args=(event_timestamp,), kwargs={}
        )

        event_thread.start()

    def _event_thread(self, event_timestamp):
        current_image = self._current_image(event_timestamp)
        while current_image is None and datetime.now() < event_timestamp + timedelta(
            seconds=self._event_timeout_seconds
        ):
            time.sleep(0.5)
            current_image = self._current_image(event_timestamp)

        if current_image is not None:
            new_filename = (
                f"{event_timestamp.strftime('%Y%m%d_%H%M%S')}_{self._camera_name}"
            )
            new_image_path = f"{self._image_file_path}{new_filename}.jpeg"
            self._logger.info(
                f"Found image {current_image}, moving to {new_image_path}"
            )
            os.rename(current_image, new_image_path)

            self._logger.info(f"Waiting for matching video file for {current_image}")
            matching_video = self._matching_video(current_image)
            while (
                matching_video is None
                and datetime.now()
                < event_timestamp + timedelta(seconds=self._video_timeout_seconds)
            ):
                time.sleep(1)
                matching_video = self._matching_video(current_image)

            if current_image is not None:
                new_video_path = f"{self._video_file_path}{new_filename}.mp4"
                self._logger.info(
                    f"Found video {matching_video}, moving to {new_video_path}"
                )
                os.rename(matching_video, new_video_path)
            else:
                self._logger.warn(
                    f"Did not find a matching video file for {current_image}"
                )
        else:
            self._logger.info(f"Did not find any image for event at {event_timestamp}")

    def _current_image(self, event_timestamp):
        earliest_timestamp = event_timestamp - timedelta(
            seconds=self._image_max_age_seconds
        )

        all_files = glob.iglob(self._ftp_upload_path + "**/**", recursive=True)
        image_files = list(filter(lambda x: x.endswith(".jpg"), all_files))
        if len(image_files) > 0:
            image_files.sort(reverse=True)
            image_file = image_files[0]

            image_timestamp = self._get_file_timestamp(image_file)

            if image_timestamp > earliest_timestamp:
                return image_files[0]

        return None

    def _get_file_timestamp(self, filename):
        filename_no_ext = os.path.splitext(filename)[0]
        timestamp_str = filename_no_ext[filename_no_ext.rindex("_") + 1 :]
        camera_tz = pytz.timezone("Europe/Stockholm")
        camera_naive = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        timestamp_localized = camera_tz.localize(camera_naive, is_dst=None)
        return timestamp_localized.astimezone(pytz.utc).replace(tzinfo=None)

    def _matching_video(self, image_file):
        filename_no_ext = os.path.splitext(image_file)[0]
        video_file = f"{filename_no_ext}.mp4"
        if os.path.isfile(video_file):
            return video_file

        # Sometimes the video timestamp is off by one second.
        base_str = filename_no_ext[: filename_no_ext.rindex("_") + 1]
        timestamp_str = filename_no_ext[filename_no_ext.rindex("_") + 1 :]
        timestamp_parsed = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        timestamp_decreased = timestamp_parsed - timedelta(seconds=1)
        video_file = f"{base_str}{timestamp_decreased.strftime('%Y%m%d%H%M%S')}.mp4"
        if os.path.isfile(video_file):
            return video_file

        return None

    def _remove_old_files(self, event_timestamp):
        all_files = glob.iglob(self._ftp_upload_path + "**/**", recursive=True)
        image_and_video_files = list(
            filter(lambda x: x.endswith(".jpg") or x.endswith(".mp4"), all_files)
        )
        for file in image_and_video_files:
            file_timestamp = self._get_file_timestamp(file)
            days = (datetime.now() - file_timestamp).days
            if days > self._ftp_purge_days:
                self._logger.info(f"Removing file {file}")
                os.remove(file)
