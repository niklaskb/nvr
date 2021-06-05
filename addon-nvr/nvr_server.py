import sys
from flask import Flask
from flask import request, send_from_directory
from flask import Response
import logging
from datetime import datetime
import time
import pytz
from os import listdir
import ipaddress
from stream_camera import StreamCamera
from capture_camera import CaptureCamera

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


@app.route("/videos")
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
    timezone = pytz.timezone("Europe/Stockholm")
    video_files = list(filter(lambda x: x.endswith(".mp4") and not x.endswith(".tmp.mp4"), listdir(file_path)))
    video_files.sort(reverse=True)
    for video_file in video_files:
        local_time = timezone.localize(
            datetime.strptime(video_file[0:15], "%Y%m%d_%H%M%S")
        ).strftime("%Y-%m-%d %H:%M:%S")
        html += (
            f'<li><a target="_blank" href="./videos/{video_file}">{local_time}</a></li>'
        )

    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/videos/<path:file>")
def get_videos_file(file):
    return send_from_directory(file_path, file, cache_timeout=0)


def latest_file(type):
    files = list(filter(lambda x: x.endswith(type), listdir(file_path)))
    files.sort(reverse=True)
    if len(files) > 0:
        return send_from_directory(file_path, files[0], cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/videos/latest")
def get_videos_latest():
    file = capture_camera.get_latest_video()
    if file:
        return send_from_directory(file_path, file, cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/images/latest")
def get_images_latest():
    file = capture_camera.get_latest_image()
    if file:
        return send_from_directory(file_path, file, cache_timeout=0)
    else:
        return "Not found", 404


@app.route("/capture/start")
@require_internal
def get_capture_start():
    capture_camera.capture_start()
    stream_camera.start_streaming()
    return "OK"


@app.route("/capture/end")
@require_internal
def get_capture_end():
    capture_camera.capture_end()
    return "OK"


def http_stream(camera):
    while True:
        frame = camera.get_frame()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


@app.route("/video/stream/mjpeg")
@require_internal
def get_video_stream_mjpeg():
    return Response(
        http_stream(stream_camera), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    camera_url_capture = sys.argv[1]
    camera_url_stream = sys.argv[2]
    video_file_path = sys.argv[3]
    image_file_path = sys.argv[4]
    max_unread_frames = int(sys.argv[5])
    capture_timeout = int(sys.argv[6])
    frame_sleep = float(sys.argv[7])
    stream_width = int(sys.argv[8])
    stream_height = int(sys.argv[9])
    purge_days = int(sys.argv[10])
    stream_camera = StreamCamera(
        app.logger,
        camera_url_stream,
        max_unread_frames,
        frame_sleep,
        stream_width,
        stream_height,
    )
    capture_camera = CaptureCamera(
        app.logger, camera_url_capture, video_file_path, image_file_path, capture_timeout, purge_days,
    )
    app.run(host="0.0.0.0")
