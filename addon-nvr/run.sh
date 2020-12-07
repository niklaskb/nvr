#!/usr/bin/with-contenv bashio

CAMERA_URL_FULL="$(bashio::config 'camera_url_full')"
CAMERA_URL_LOW="$(bashio::config 'camera_url_low')"
MAX_UNREAD_FRAMES="$(bashio::config 'max_unread_frames')"
CAPTURE_TIMEOUT="$(bashio::config 'capture_timeout')"
FILE_PATH="$(bashio::config 'file_path')"

python3 nvr_server.py $CAMERA_URL_FULL $CAMERA_URL_LOW $MAX_UNREAD_FRAMES $CAPTURE_TIMEOUT $FILE_PATH
