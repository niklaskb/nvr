#!/usr/bin/with-contenv bashio

CAMERA_URL_CAPTURE="$(bashio::config 'camera_url_capture')"
CAMERA_URL_STREAM="$(bashio::config 'camera_url_stream')"
VIDEO_FILE_PATH="$(bashio::config 'video_file_path')"
IMAGE_FILE_PATH="$(bashio::config 'image_file_path')"
MAX_UNREAD_FRAMES="$(bashio::config 'max_unread_frames')"
CAPTURE_TIMEOUT="$(bashio::config 'capture_timeout')"
FRAME_SLEEP="$(bashio::config 'frame_sleep')"
STREAM_WIDTH="$(bashio::config 'stream_width')"
STREAM_HEIGHT="$(bashio::config 'stream_height')"
PURGE_DAYS="$(bashio::config 'purge_days')"

mkdir -p $VIDEO_FILE_PATH
mkdir -p $IMAGE_FILE_PATH

python3 nvr_server.py $CAMERA_URL_CAPTURE $CAMERA_URL_STREAM $VIDEO_FILE_PATH $IMAGE_FILE_PATH $MAX_UNREAD_FRAMES $CAPTURE_TIMEOUT $FRAME_SLEEP $STREAM_WIDTH $STREAM_HEIGHT $PURGE_DAYS
