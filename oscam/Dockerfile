ARG BUILD_FROM=lscr.io/linuxserver/oscam:latest
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

RUN apk update
RUN echo #############################################
#RUN apk search pip
#RUN echo #############################################
RUN apk add --no-cache \
    git \
    patch \
    make \
    binutils \
    build-base \
    cmake \
    gcc \
    libusb-dev \
    musl-dev \
    linux-headers \
    openssl-dev \
    pcsc-lite-dev \
    ccid \
    libdvbcsa \
    libusb \
    openssl \
    pcsc-lite \
    pcsc-lite-libs


WORKDIR /app

RUN git clone --depth 1 --branch 11943 https://git.streamboard.tv/common/oscam.git

COPY /patch /app/patch/


WORKDIR /app/oscam

RUN patch -p1 < /app/patch/oscam-emu.patch
RUN make OSCAM_BIN=/usr/bin/oscam



# copy local files
COPY root/ /

RUN chmod a+x /etc/s6-overlay/s6-rc.d/svc-oscam/run

# Ports and volumes
EXPOSE 8888
EXPOSE 9999

VOLUME /config
