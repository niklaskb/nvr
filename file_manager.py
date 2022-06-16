from datetime import datetime
import os
import pytz


class FileManager(object):
    def __init__(self, logger, video_file_path, image_file_path, purge_video_days, purge_image_days):
        self._logger = logger
        self._video_file_path = video_file_path
        self._image_file_path = image_file_path
        self._purge_video_days = purge_video_days
        self._purge_image_days = purge_image_days

    def get_mapped_recordings(self):
        image_files = list(filter(lambda x: x.endswith(".jpeg"), os.listdir(self._image_file_path)))
        image_files.sort(reverse=True)
        video_files = list(filter(lambda x: x.endswith(".mp4"), os.listdir(self._video_file_path)))
        video_files.sort(reverse=True)

        recordings = []
        for video_file in video_files:
            timestamp = video_file[0:15]
            camera_name = os.path.splitext(video_file)[0][16:]
            matching_image_files = list(
                filter(lambda x: x.startswith(timestamp) and x.endswith(f"{camera_name}.jpeg"), image_files)
            )
            matching_image_files.sort(reverse=False)
            image_files = [image_file for image_file in image_files if image_file not in matching_image_files]

            image_file = None
            extra_images = []
            for matching_image_file in matching_image_files:
                image_timestamp = matching_image_file[16:31]
                if image_file is None:
                    image_file = matching_image_file
                else:
                    extra_images.append({
                        "timestamp": datetime.strptime(image_timestamp, "%Y%m%d_%H%M%S"),
                        "filename": matching_image_file,
                    })

            recordings.append({
                "camera_name": camera_name,
                "timestamp": datetime.strptime(timestamp, "%Y%m%d_%H%M%S"),
                "video_filename": video_file,
                "image_filename": image_file,
                "extra_images": extra_images,
            })
        orphan_images = []
        for image_file in image_files:
            orphan_image = {
                "camera_name": os.path.splitext(image_file)[0][32:],
                "timestamp": datetime.strptime(image_file[16:31], "%Y%m%d_%H%M%S"),
                "image_filename": image_file,
            }
            orphan_images.append(orphan_image)
            
        return recordings, orphan_images

    def remove_old_videos(self):
        files = list(
            filter(lambda x: x.endswith(".mp4"), os.listdir(self._video_file_path))
        )
        for file in files:
            time = datetime.strptime(file[0:15], "%Y%m%d_%H%M%S")
            days = (datetime.now() - time).days
            if days > self._purge_video_days:
                self._logger.info(f"Removing file {file}")
                os.remove(f"{self._video_file_path}/{file}")

    def remove_old_images(self):
        files = list(
            filter(lambda x: x.endswith(".jpeg"), os.listdir(self._image_file_path))
        )
        for file in files:
            time = datetime.strptime(file[0:15], "%Y%m%d_%H%M%S")
            days = (datetime.now() - time).days
            if days > self._purge_image_days:
                self._logger.info(f"Removing file {file}")
                os.remove(f"{self._image_file_path}/{file}")

    def get_latest_image(self, camera):
        return self._get_latest_file(f"_{camera}.jpeg", self._image_file_path)

    def get_latest_video(self, camera):
        return self._get_latest_file(f"_{camera}.mp4", self._video_file_path)

    def get_latest_image(self):
        return self._get_latest_file(".jpeg", self._image_file_path)

    def get_latest_video(self):
        return self._get_latest_file(".mp4", self._video_file_path)

    def _get_latest_file(self, endswith, file_path):
        files = list(filter(lambda x: x.endswith(endswith), os.listdir(file_path)))
        files.sort(reverse=True)
        if len(files) > 0:
            return files[0]
        else:
            return None
