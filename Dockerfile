FROM ubuntu:22.04

RUN apt update && apt upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt install -y \
    ffmpeg \
    python3-opencv \
    python3-pip \
    git

COPY requirements.txt /

RUN pip3 install -r requirements.txt

EXPOSE 5000

CMD /run.sh

COPY __init__.py \
    capture_camera.py \
    config.json \
    file_manager.py \
    nvr_server.py \
    run.sh \
    secrets.json \
    stream_camera.py \
    timelapse_camera.py \
    utils.py \
    /

RUN chmod a+x /run.sh
