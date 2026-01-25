CC = gcc
DEST?= /opt/minirouter

CFLAGS = -Wall -Wextra -O2 -I$(DEST)/include 

LDFLAGS = -lczmq -L$(DEST)/lib -Wl,-rpath,'$(DEST)/lib'

all: gpio_buttons_server ssd1306_i2c_server

gpio_buttons_server: gpio_buttons_server.c
	$(CC) $(CFLAGS) -o $@ $^ -lwiringPi $(LDFLAGS) 

ssd1306_i2c_server: ssd1306_i2c_server.c
	$(CC) $(CFLAGS) -o $@ $^ -lssd1306_i2c $(LDFLAGS)

clean:
	rm -f gpio_buttons_server ssd1306_i2c_server

install: all
	mkdir -p $(DEST)/bin
	cp gpio_buttons_server ssd1306_i2c_server $(DEST)/bin/
	chown root:root -R $(DEST)/bin
	chmod +s $(DEST)/bin/*

.PHONY: all clean install
