#!/bin/bash

FILE_PATH="$1"

sudo docker build -t nvr .
sudo docker stop nvr
sudo docker rm nvr
sudo docker run -p 5000:5000 -v $FILE_PATH/mnt/camera:/camera --name nvr --restart=always -d nvr
sudo docker attach --sig-proxy=false nvr
