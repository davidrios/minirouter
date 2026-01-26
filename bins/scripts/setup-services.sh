#!/bin/bash
set -e
DEST=/opt/minirouter
if test $(id -u) != 0; then
	echo This program needs to be run as root
	exit 1
fi
test -f /etc/default/gpio_buttons_server || cp $DEST/etc/default/gpio_buttons_server.default /etc/default/gpio_buttons_server
test -f /etc/default/ssd1306_i2c_server || cp $DEST/etc/default/ssd1306_i2c_server.default /etc/default/ssd1306_i2c_server
cp $DEST/etc/systemd/system/* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gpio_buttons_server
systemctl enable --now ssd1306_i2c_server
