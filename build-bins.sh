#!/bin/bash
docker run --privileged --rm tonistiigi/binfmt --install linux/arm64
docker build -t minirouter-builder --platform linux/arm64 -f builder.Dockerfile .
docker run --rm -it -v $PWD:/code minirouter-builder sh -c '
set -e
DEST=/opt/minirouter
cd /code
make clean
make install DEST=$DEST -j4
cat <<'EOF' > $DEST/bin/install-deps.sh
#!/bin/bash
if test \$(id -u) != 0; then
	echo This program needs to be run as root
	exit 1
fi
apt-get update && apt-get install -y libczmq4 libfreetype6 ttf-bitstream-vera
EOF
chmod +x $DEST/bin/install-deps.sh
cd /
tar cfvz /code/minirouter.tar.gz opt/minirouter
cd /code && make clean
'

echo
echo
echo Copy minirouter.tar.gz to the device and extract with: sudo tar xvfp minirouter.tar.gz -C /
