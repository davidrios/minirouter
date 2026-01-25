#!/bin/bash
docker run --privileged --rm tonistiigi/binfmt --install linux/arm64
docker build -t minirouter-builder --platform linux/arm64 -f builder.Dockerfile .
docker run --rm -it -v $PWD:/code minirouter-builder sh -c '
set -e
DEST=/opt/minirouter
cd /code
make clean
make
mkdir -p $DEST/bin
cp gpio_buttons $DEST/bin/
chown root:root $DEST/bin/*
chmod +s $DEST/bin/*
cd /
tar cfvz /code/minirouter.tar.gz opt/minirouter
cd /code && make clean
'

echo
echo
echo Copy minirouter.tar.gz to the device and extract with: sudo tar xvfp minirouter.tar.gz -C /
