FROM debian:bookworm

RUN set -e \
 && apt-get update\
 && apt-get install -y sudo git curl build-essential libczmq-dev libfreetype6-dev fonts-freefont-ttf ttf-bitstream-vera autoconf automake libtool autotools-dev build-essential pkg-config libev-dev libunistring-dev\
 && cd ~\
 && git clone -b 2.61-1 https://github.com/WiringPi/WiringPi.git\
 && git clone -b 0.8 https://github.com/stealthylabs/libssd1306

RUN set -e \
 && cd ~/WiringPi/wiringPi\
 && make DESTDIR=/opt/minirouter PREFIX=/. install -j4

RUN set -e\
 && cd ~/libssd1306\
 && ./autogen.sh && ./configure --prefix=/opt/minirouter && make install -j4
