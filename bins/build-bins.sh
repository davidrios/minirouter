#!/bin/bash
mkdir tmp
cd ..
uv build
cp dist/minirouter-*.whl bins/tmp
cp config.template.json bins/tmp
cd bins
docker run --privileged --rm tonistiigi/binfmt --install linux/arm64
docker build -t minirouter-builder --platform linux/arm64 -f builder.Dockerfile .
docker run --rm -it -v $PWD:/code minirouter-builder sh -c '
set -e
DEST=/opt/minirouter
cd /code
mkdir -p $DEST/etc/default $DEST/etc/systemd/system
cp *.default $DEST/etc/default
cp *.service $DEST/etc/systemd/system/
cp tmp/*.whl $DEST/
cp tmp/config.template.json $DEST/etc/
make clean
make install DEST=$DEST -j4
cp scripts/* $DEST/bin/
cd /
tar cfvz /code/tmp/minirouter.tar.gz opt/minirouter
cd /code && make clean
'

echo
echo
echo Copy tmp/minirouter.tar.gz to the device and extract with: sudo tar xvfp minirouter.tar.gz -C /
