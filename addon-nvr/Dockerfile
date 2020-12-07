ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

ARG OPENCV_VERSION=4.4.0

RUN apk add --no-cache \
        ffmpeg \
        openblas \
        ffmpeg-libs \
        libjpeg \
        libpng \
        python3 \
        py3-pip && \
    pip3 install \
        flask \
        pytz

# Build OpenCV with FFMPEG for Python 3
RUN apk add --update --no-cache \
        build-base cmake wget \
        py3-numpy-dev \
        openblas-dev \
        ffmpeg-dev \
        libjpeg-turbo-dev \
        libpng-dev \
        python3-dev \
        linux-headers && \
    wget -P /tmp/ https://github.com/opencv/opencv/archive/$OPENCV_VERSION.tar.gz && \
    tar -xvzf /tmp/$OPENCV_VERSION.tar.gz -C /tmp/ && \
    rm -vrf /tmp/$OPENCV_VERSION.tar.gz && \
    mkdir -vp /tmp/opencv-$OPENCV_VERSION/build && \
    cd /tmp/opencv-$OPENCV_VERSION/build && \
    cmake \
        -D CMAKE_BUILD_TYPE=RELEASE \
        -D CMAKE_INSTALL_PREFIX=/usr \
        -D OPENCV_ENABLE_NONFREE=ON \
        -D WITH_JPEG=ON \
        -D WITH_PNG=ON \
        -D WITH_TIFF=OFF \
        -D WITH_WEBP=OFF \
        -D WITH_JASPER=OFF \
        -D WITH_EIGEN=OFF \
        -D WITH_TBB=OFF \
        -D WITH_LAPACK=OFF \
        -D WITH_PROTOBUF=OFF \
        -D WITH_1394=OFF \
        -D WITH_LIBV4L=OFF \
        -D WITH_V4L=ON \
        -D WITH_GSTREAMER=OFF \
        -D WITH_GTK=OFF \
        -D WITH_QT=OFF \
        -D WITH_CUDA=OFF \
        -D WITH_VTK=OFF \
        -D WITH_OPENEXR=OFF \
        -D WITH_FFMPEG=ON \
        -D WITH_OPENCL=OFF \
        -D WITH_OPENNI=OFF \
        -D WITH_XINE=OFF \
        -D WITH_GDAL=OFF \
        -D WITH_IPP=OFF \
        -D BUILD_OPENCV_PYTHON3=ON \
        -D BUILD_OPENCV_PYTHON2=OFF \
        -D BUILD_OPENCV_JAVA=OFF \
        -D BUILD_TESTS=OFF \
        -D BUILD_IPP_IW=OFF \
        -D BUILD_PERF_TESTS=OFF \
        -D BUILD_EXAMPLES=OFF \
        -D BUILD_ANDROID_EXAMPLES=OFF \
        -D BUILD_DOCS=OFF \
        -D BUILD_ITT=OFF \
        -D INSTALL_PYTHON_EXAMPLES=OFF \
        -D INSTALL_C_EXAMPLES=OFF \
        -D INSTALL_TESTS=OFF \
        -D PYTHON3_LIBRARY=`find /usr -name libpython3.so` \
        -D PYTHON_EXECUTABLE=`which python3` \
        -D PYTHON3_EXECUTABLE=`which python3` \
        -D PYTHON3_NUMPY_INCLUDE_DIRS=/usr/lib/python3.8/site-packages/numpy/core/include/ \
        /tmp/opencv-${OPENCV_VERSION}/ && \
    make -j1 && \
    make install && \
    apk del -q --no-cache \
        build-base cmake wget \
        openblas-dev \
        ffmpeg-dev \
        libjpeg-turbo-dev \
        libpng-dev \
        python3-dev \
        linux-headers && \
    rm -rf /tmp/opencv-${OPENCV_VERSION} && \
    rm -vrf /var/cache/apk/*

COPY nvr_server.py /

RUN mkdir -p /media/videos

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
