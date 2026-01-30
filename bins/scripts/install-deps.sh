#!/bin/bash
set -e
if test $(id -u) != 0; then
	echo This program needs to be run as root
	exit 1
fi
apt-get update && apt-get install -y libczmq4 libfreetype6 ttf-bitstream-vera curl
curl -L https://github.com/astral-sh/uv/releases/download/0.9.26/uv-aarch64-unknown-linux-gnu.tar.gz | tar xvz -C /usr/local/bin --strip-components=1 --no-same-owner --no-same-permissions
