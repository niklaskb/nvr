from datetime import datetime
import threading
import time
from os import listdir
import subprocess, io
import os


class FileManager(object):
    def __init__(self, logger, video_file_path, image_file_path, purge_days):
        self._logger = logger
        self._video_file_path = video_file_path
        self._image_file_path = image_file_path
        self._purge_days = purge_days

    def remove_old_videos(self):
        files = list(
            filter(lambda x: x.endswith(".mp4"), listdir(self._video_file_path))
        )
        for file in files:
            time = datetime.strptime(file[0:15], "%Y%m%d_%H%M%S")
            days = (datetime.now() - time).days
            if days > self._purge_days:
                self._logger.info(f"Removing file {file}")
                os.remove(f"{self._video_file_path}/{file}")

    def get_latest_image(self, camera):
        return self._get_latest_file(f"_{camera}.jpeg", self._image_file_path)

    def get_latest_video(self, camera):
        return self._get_latest_file(f"_{camera}.mp4", self._video_file_path)

    def get_latest_image(self):
        return self._get_latest_file(".jpeg", self._image_file_path)

    def get_latest_video(self):
        return self._get_latest_file(".mp4", self._video_file_path)

    def _get_latest_file(self, endswith, file_path):
        files = list(filter(lambda x: x.endswith(endswith), listdir(file_path)))
        files.sort(reverse=True)
        if len(files) > 0:
            return files[0]
        else:
            return None
