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
from timelapse_camera import TimelapseCamera
import schedule
import threading
import time
from datetime import timezone
import urllib.request, json 

app = Flask(__name__)


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
    files = list(filter(lambda x: x.endswith(".jpeg"), listdir(image_file_path)))
    files.extend(list(filter(lambda x: x.endswith(".mp4"), listdir(video_file_path))))
    files.sort(reverse=True)
    return files[0]

@app.route("/recordings/lastchanged")
def get_recordings_lastchanged():
    return _get_lastchanged()

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

    tz = pytz.timezone(config["timezone"])

    recordings, orphan_images = file_manager.get_mapped_recordings()

    for orphan_image in orphan_images:
        local_timestamp = orphan_image["timestamp"].replace(tzinfo=pytz.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        camera_display_name = camera_display_names[orphan_image["camera_name"]]
        html += f"<li>{local_timestamp}<br/>"
        html += f'<img style="width:90%; border: 2px solid red;" src="./images/{orphan_image["image_filename"]}" alt="{camera_display_name} - {local_timestamp}" />'
        html += "</li>"

    for recording in recordings:
        local_timestamp = recording["timestamp"].replace(tzinfo=pytz.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        camera_display_name = camera_display_names[recording["camera_name"]]

        html += f"<li>{local_timestamp}<br/>"
        html += f'<a target="_blank" href="./videos/{recording["video_filename"]}"><img style="width:90%;" src="./images/{recording["image_filename"]}" alt="{camera_display_name} - {local_timestamp}" /></a>'
        for extra_images in recording["extra_images"]:
            image_local_time = extra_images["timestamp"].replace(tzinfo=pytz.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            html += f'<img style="width:45%;" src="./images/{extra_images["filename"]}" alt="{camera_display_name} - {image_local_time}" />'
        html += "</li>"
    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/events")
def get_events():
    html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Events</title>
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
    </head>
    <body>
        <ul>
"""

    with urllib.request.urlopen(f"{frigate_base_url}/api/events?include_thumbnails=0") as url:
        events = json.load(url)
        tz = pytz.timezone(config["timezone"])
        for event in events:
            if event["label"] == "person":
                local_timestamp = datetime.fromtimestamp(event["start_time"]).replace(tzinfo=pytz.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
                camera_display_name = camera_display_names[event["camera"].removeprefix("camera_")]

                html += f"<li>{local_timestamp}<br/>"
                if event["has_clip"] and event["has_snapshot"]:
                    html += f'<a target="_blank" href="./clips/{event["id"]}"><img style="width:90%;" src="./snapshots/{event["id"]}" alt="{camera_display_name} - {local_timestamp}" /></a>'
                elif event["has_snapshot"]:
                    html += f'<img style="width:90%; border: 2px solid red;" src="./snapshots/{event["id"]}" alt="{camera_display_name} - {local_timestamp}" />'
                else:
                    html += f'{camera_display_name} - {local_timestamp}'
                html += "</li>"
    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/timelapses")
def get_timelapses():
    html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Timelapses</title>
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
    </head>
    <body>
        <ul>
"""
    timelapse_files = list(filter(lambda x: x.endswith(".mp4"), listdir(timelapse_video_file_path)))
    timelapse_files.sort(reverse=True)



    for timelapse_file in timelapse_files:
        timelapse_file_no_ext = path.splitext(timelapse_file)[0]
        year = timelapse_file_no_ext[0:4]
        hour = timelapse_file_no_ext[5:7]
        camera_name = timelapse_file_no_ext[8:]

        html += f'<li><a target="_blank" href="./timelapses/{timelapse_file}">{year}: {camera_display_names[camera_name]} {hour} UTC</a></li>'

    html += """
        </ul>
    </body>
</html>
"""
    return html


@app.route("/clips/<path:event_id>")
def get_clips(event_id):
    with urllib.request.urlopen(f"{frigate_base_url}/api/events/{event_id}/clip.mp4") as response:
        contents = response.read()
        info = response.info()
        return Response(contents, mimetype=info.get_content_type())


@app.route("/snapshots/<path:event_id>")
def get_snapshots(event_id):
    with urllib.request.urlopen(f"{frigate_base_url}/api/events/{event_id}/snapshot.jpg") as response:
        contents = response.read()
        info = response.info()
        return Response(contents, mimetype=info.get_content_type())


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

@app.route("/timelapses/<path:file>")
def get_timelapses_file(file):
    return send_from_directory(timelapse_video_file_path, file, max_age=604800)

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
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    capture_cameras[camera_name].capture_keep(timestamp)
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/start")
@require_internal
def get_cameras_camera_capture_start(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_start()
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    capture_cameras[camera_name].capture_keep(timestamp)
    return "OK"


@app.route("/cameras/<path:camera_name>/capture/end")
@require_internal
def get_cameras_camera_capture_end(camera_name):
    if camera_name not in capture_cameras:
        abort(404)
    capture_cameras[camera_name].capture_end()
    return "OK"

def _replace_secrets(secrets, value):
    for secret_key, secret_value in secrets.items():
        value = value.replace(f"{{{secret_key}}}", secret_value)
    return value

def _schedule(timelapse_camera, i):
    schedule.every().hour.at(":00").do(timelapse_camera.capture_image_async)
    schedule.every().day.at(f"{i:02}:01:00").do(timelapse_camera.build_videos)

def _run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    app.logger.setLevel(logging.INFO)
    handler = logging.FileHandler("nvr.log")
    handler.setFormatter(app.logger.handlers[0].formatter)
    app.logger.addHandler(handler)

    with open("config.json", "r") as f:
        config = json.load(f)

    with open("secrets.json", "r") as f:
        secrets = json.load(f)

    video_file_path = config["video_file_path"]
    timelapse_video_file_path = config["timelapse_video_file_path"]
    image_file_path = config["image_file_path"]
    frigate_base_url = config["frigate_base_url"]

    stream_cameras = {}
    capture_cameras = {}
    camera_display_names = {}
    timelapse_cameras = {}

    i = 0
    for camera_config in config["cameras"]:
        camera_display_names[camera_config["name"]] = camera_config["display_name"]
        stream_cameras[camera_config["name"]] = StreamCamera(
            app.logger,
            camera_config["name"],
            _replace_secrets(secrets, camera_config["stream"]["url"]),
            camera_config["stream"]["frame_sleep"],
            camera_config["stream"]["width"],
            camera_config["stream"]["height"],
            camera_config["stream"]["restart_threshold"],
            camera_config["stream"]["compression"],
        )

        capture_cameras[camera_config["name"]] = CaptureCamera(
            app.logger,
            camera_config["name"],
            _replace_secrets(secrets, camera_config["capture"]["url"]),
            _replace_secrets(secrets, camera_config["capture"]["image_url"]),
            camera_config["capture"]["ffmpeg_options"],
            config["video_file_path"],
            config["image_file_path"],
            config["temp_video_file_path"],
            config["capture_timeout"],
        )

        timelapse_camera = TimelapseCamera(
            app.logger,
            camera_config["name"],
            _replace_secrets(secrets, camera_config["timelapse"]["image_url"]),
            camera_config["timelapse"]["ffmpeg_options"],
            config["timelapse_video_file_path"],
            config["timelapse_image_file_path"],
            config["timelapse_hours"],
        )

        timelapse_cameras[camera_config["name"]] = timelapse_camera

        _schedule(timelapse_camera, i)
        i = i + 1

    file_manager = FileManager(
        app.logger,
        config["video_file_path"],
        config["image_file_path"],
        config["purge_video_days"],
        config["purge_image_days"],
    )

    schedule_thread = threading.Thread(
        target=_run_schedule
    )
    schedule_thread.start()

    app.run(host="0.0.0.0")
