CC = gcc
DEST?= /opt/minirouter

CFLAGS = -Wall -Wextra -O2 -I$(DEST)/include 

LDFLAGS = -lczmq -L$(DEST)/lib -Wl,-rpath,'$(DEST)/lib'

BINARIES=gpio_buttons_server ssd1306_i2c_server wificonnect

all: gpio_buttons_server ssd1306_i2c_server wificonnect

gpio_buttons_server: gpio_buttons_server.c
	$(CC) $(CFLAGS) -o $@ $^ -lwiringPi $(LDFLAGS) 

ssd1306_i2c_server: ssd1306_i2c_server.c
	$(CC) $(CFLAGS) -o $@ $^ -lssd1306_i2c $(LDFLAGS)

wificonnect: wificonnect.c
	$(CC) $(CFLAGS) -o $@ $^

clean:
	rm -f gpio_buttons_server ssd1306_i2c_server wificonnect

install: all
	mkdir -p $(DEST)/bin
	cp gpio_buttons_server ssd1306_i2c_server wificonnect $(DEST)/bin/
	chown root:root -R $(DEST)/bin
	(cd $(DEST)/bin && chmod +s gpio_buttons_server ssd1306_i2c_server wificonnect)

.PHONY: all clean install
