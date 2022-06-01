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
from ftp_camera import FtpCamera

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


def _get_lastchanged():
    image_files = list(filter(lambda x: x.endswith(".jpeg"), listdir(image_file_path)))
    image_files.sort(reverse=True)
    image_file_no_ext = path.splitext(image_files[0])[0]
    return image_file_no_ext;

@app.route("/recordings/lastchanged")
def get_recordings_lastchanged():
    return _get_lastchanged();

@app.route("/recordings")
def get_recordings():
    html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Recordings</title>
        <style>
            body {{
                background: #FFF;
                color: #1c1c1c;
                font-family: Roboto,sans-serif;
                font-weight: 400;
            }}
            a {{
                color: #1c1c1c;
                text-decoration: none;
            }}
            a:hover, a:active {{
                text-decoration: underline;
            }}
            @media (prefers-color-scheme: dark) {{
                body, a {{
                    background: #1c1c1c;
                    color: #FFF;
                }}
            }}
        </style>
        <script>
            var blurred = false;
            window.onblur = function() {{ blurred = true; }};
            window.onfocus = function() {{
                if (blurred) {{
                    var xhr = new XMLHttpRequest ();
                    xhr.open ( "GET", "/recordings/lastchanged");
                    xhr.onreadystatechange = function () {{
                        if ( xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {{
                            if (xhr.response != "{_get_lastchanged()}") {{
                                location.reload();
                            }}
                        }}
                    }}
                    xhr.send ();
                }}
            }};
        </script>
    </head>
    <body>
        <ul>
"""

    file_manager.remove_old_videos()
    file_manager.remove_old_images()

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
                html += f'<a target="_blank" href="./videos/{matching_image}.mp4"><img style="width:90%;" src="./images/{matching_image}.jpeg" alt="{camera_display_names[camera_name]}" /></a>'
            else:
                html += f'<a target="_blank" href="./images/{matching_image}.jpeg"><img style="width:90%;" src="./images/{matching_image}.jpeg" alt="{camera_display_names[camera_name]}" /></a>'
        html += "</li>"
    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/videos/<path:file>")
def get_videos_file(file):
    return send_from_directory(video_file_path, file, max_age=604800)


@app.route("/images/<path:file>")
def get_images_file(file):
    return send_from_directory(image_file_path, file, max_age=604800)


@app.route("/images/latest")
def get_cameras_images_latest():
    file = file_manager.get_latest_image()
    if file:
        return send_from_directory(image_file_path, file, max_age=0)
    else:
        return "Not found", 404


def http_stream(stream_camera):
    while True:
        frame = stream_camera.get_jpeg()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


@app.route("/cameras/<path:camera_name>/stream/mjpeg")
@require_internal
def get_cameras_camera_stream_mjpeg(camera_name):
    if camera_name not in stream_cameras:
        abort(404)
    return Response(
        http_stream(stream_cameras[camera_name]),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/cameras/<path:camera_name>/event/start")
@require_internal
def get_cameras_camera_event_start(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_start()
    return "OK"


@app.route("/cameras/<path:camera_name>/event/end")
@require_internal
def get_cameras_camera_event_end(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_end()
    return "OK"


@app.route("/cameras/<path:camera_name>/event/keep")
@require_internal
def get_cameras_camera_event_keep(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_cameras[camera_name].capture_keep(timestamp)
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/start")
@require_internal
def get_cameras_camera_capture_start(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_start()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_cameras[camera_name].capture_keep(timestamp)
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/end")
@require_internal
def get_cameras_camera_capture_end(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_end()
    return "OK"


if __name__ == "__main__":
    app.logger.info(f"log logger 222")
    with open("config.json", "r") as f:
        config = json.load(f)

    video_file_path = config["video_file_path"]
    image_file_path = config["image_file_path"]

    stream_cameras = {}
    capture_cameras = {}
    ftp_cameras = {}
    camera_display_names = {}

    for camera_config in config["cameras"]:
        camera_display_names[camera_config["name"]] = camera_config["display_name"]
        stream_cameras[camera_config["name"]] = StreamCamera(
            app.logger,
            camera_config["name"],
            camera_config["stream"]["url"],
            camera_config["stream"]["frame_sleep"],
            camera_config["stream"]["width"],
            camera_config["stream"]["height"],
        )

        capture_cameras[camera_config["name"]] = CaptureCamera(
            app.logger,
            camera_config["name"],
            camera_config["capture"]["url"],
            camera_config["capture"]["image_url"],
            camera_config["capture"]["ffmpeg_options"],
            config["video_file_path"],
            config["image_file_path"],
            config["temp_file_path"],
            config["capture_timeout"],
        )

        ftp_cameras[camera_config["name"]] = FtpCamera(
            app.logger,
            camera_config["name"],
            camera_config["ftp_upload_path"],
            config["image_file_path"],
            config["video_file_path"],
            config["ftp_purge_days"],
            config["ftp_image_timeout_seconds"],
            config["ftp_video_timeout_seconds"],
        )

    file_manager = FileManager(
        app.logger,
        config["video_file_path"],
        config["image_file_path"],
        config["purge_video_days"],
        config["purge_image_days"],
    )

    app.run(host="0.0.0.0")
