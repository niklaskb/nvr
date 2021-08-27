import sys
from flask import Flask
from flask import request, send_from_directory, abort
from flask import Response
import logging
from datetime import datetime
import pytz
import json
from os import listdir, path
import ipaddress
from stream_camera import StreamCamera
from capture_camera import CaptureCamera
from file_manager import FileManager

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


def require_internal(func):
    def wrapper_require_internal(*args, **kwargs):
        if ipaddress.ip_address(request.remote_addr) in ipaddress.ip_network(
            "172.0.0.0/8"
        ) or ipaddress.ip_address("127.0.0.1"):
            return func(*args, **kwargs)
        return ("Unauthorized", 401)

    wrapper_require_internal.__name__ = func.__name__ + "_wrapper"
    return wrapper_require_internal


@app.route("/recordings")
def get_videos():
    html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Recordings</title>
        <style>
            body {
                background: #FFF;
                color: #1c1c1c;
                font-family: Roboto,sans-serif;
                font-weight: 400;
            }
            a {
                color: #1c1c1c;
                text-decoration: none;
            }
            a:hover, a:active {
                text-decoration: underline;
            }
            @media (prefers-color-scheme: dark) {
                body, a {
                    background: #1c1c1c;
                    color: #FFF;
                }
            }
        </style>
    </head>
    <body>
        <ul>
"""

    file_manager.remove_old_videos()

    timezone = pytz.timezone("Europe/Stockholm")
    image_files = list(filter(lambda x: x.endswith(".jpeg"), listdir(image_file_path)))
    image_files_no_ext = [path.splitext(x)[0] for x in image_files]

    video_files = list(filter(lambda x: x.endswith(".mp4"), listdir(video_file_path)))
    video_files_no_ext = [path.splitext(x)[0] for x in video_files]

    image_files_no_ext.sort(reverse=True)

    unique_prefixes = []
    for name in image_files_no_ext:
        prefix = name[0:15]
        if prefix not in unique_prefixes:
            unique_prefixes.append(prefix)

    for unique_prefix in unique_prefixes:
        time = datetime.strptime(unique_prefix, "%Y%m%d_%H%M%S")
        local_time = (
            time.replace(tzinfo=pytz.utc)
            .astimezone(timezone)
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        matching_images = list(
            filter(lambda x: x.startswith(unique_prefix), image_files_no_ext)
        )
        matching_videos = list(
            filter(lambda x: x.startswith(unique_prefix), video_files_no_ext)
        )

        html += f"<li>{local_time}<br/>"
        first = True
        for matching_image in matching_images:
            camera_name = matching_image[16:]
            if first:
                first = False
            else:
                html += ", "

            if matching_image in matching_videos:
                html += f'<a target="_blank" href="./videos/{matching_image}.mp4">{camera_display_names[camera_name]}</a>'
            else:
                html += f'<a target="_blank" href="./images/{matching_image}.jpeg">{camera_display_names[camera_name]}</a>'
        html += "</li>"
    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/videos/<path:file>")
def get_videos_file(file):
    return send_from_directory(video_file_path, file, cache_timeout=0)


@app.route("/images/<path:file>")
def get_images_file(file):
    return send_from_directory(image_file_path, file, cache_timeout=0)


def latest_video(camera_name):
    files = list(
        filter(lambda x: x.endswith(f"_{camera_name}.mp4"), listdir(video_file_path))
    )
    files.sort(reverse=True)
    if len(files) > 0:
        return send_from_directory(video_file_path, files[0], cache_timeout=0)
    else:
        return "Not found", 404


def latest_image(camera_name):
    files = list(
        filter(lambda x: x.endswith(f"_{camera_name}.jpeg"), listdir(image_file_path))
    )
    files.sort(reverse=True)
    if len(files) > 0:
        return send_from_directory(image_file_path, files[0], cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/cameras/<path:camera_name>/videos/latest")
def get_videos_latest(camera_name):
    file = file_manager.get_latest_video(camera_name)
    if file:
        return send_from_directory(video_file_path, file, cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/cameras/<path:camera_name>/images/latest")
def get_images_latest(camera_name):
    file = file_manager.get_latest_image(camera_name)
    if file:
        return send_from_directory(image_file_path, file, cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/cameras/capture/start")
@require_internal
def get_capture_start_all():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for _, capture_camera in capture_cameras.items():
        capture_camera.capture_start(timestamp)
    for _, stream_camera in stream_cameras.items():
        stream_camera.start_streaming()
    return "OK"


@app.route("/cameras/capture/end")
@require_internal
def get_capture_end_all():
    for _, capture_camera in capture_cameras.items():
        capture_camera.capture_end()
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/start")
@require_internal
def get_capture_start(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_cameras[camera_name].capture_start(timestamp)
    stream_cameras[camera_name].start_streaming()
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/end")
@require_internal
def get_capture_end(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_end()
    return "OK"


def http_stream(stream_camera):
    while True:
        frame = stream_camera.get_frame()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


@app.route("/cameras/<path:camera_name>/stream/mjpeg")
@require_internal
def get_video_stream_mjpeg(camera_name):
    if camera_name not in stream_cameras:
        abort(404)
    return Response(
        http_stream(stream_cameras[camera_name]),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)

    video_file_path = config["video_file_path"]
    image_file_path = config["image_file_path"]

    stream_cameras = {}
    capture_cameras = {}
    camera_display_names = {}

    for camera_config in config["cameras"]:
        camera_display_names[camera_config["name"]] = camera_config["display_name"]
        stream_cameras[camera_config["name"]] = StreamCamera(
            app.logger,
            camera_config["stream"]["url"],
            camera_config["stream"]["max_unread_frames"],
            camera_config["stream"]["frame_sleep"],
            camera_config["stream"]["stream_width"],
            camera_config["stream"]["stream_height"],
        )

        capture_cameras[camera_config["name"]] = CaptureCamera(
            app.logger,
            camera_config["name"],
            camera_config["capture"]["url"],
            camera_config["capture"]["ffmpeg_options"],
            config["video_file_path"],
            config["image_file_path"],
            config["capture_timeout"],
        )

    file_manager = FileManager(
        app.logger,
        config["video_file_path"],
        config["image_file_path"],
        config["purge_days"],
    )

    app.run(host="0.0.0.0")
