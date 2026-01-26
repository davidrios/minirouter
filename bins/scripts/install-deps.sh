#!/bin/bash
set -e
if test $(id -u) != 0; then
	echo This program needs to be run as root
	exit 1
fi
apt-get update && apt-get install -y libczmq4 libfreetype6 ttf-bitstream-vera
