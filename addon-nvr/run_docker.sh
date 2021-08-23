#!/bin/bash

CAMERA_URL_CAPTURE="$1"
CAMERA_URL_STREAM="$2"

sudo docker build -t nvr .
sudo docker stop nvr
sudo docker rm nvr
sudo docker run -e CAMERA_URL_CAPTURE="$CAMERA_URL_CAPTURE" -e CAMERA_URL_STREAM="$CAMERA_URL_STREAM" -p 5000:5000 -v $(pwd)/camera:/camera --name nvr --restart=always -d nvr
sudo docker attach --sig-proxy=false nvr
