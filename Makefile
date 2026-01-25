CC = gcc

CFLAGS = -Wall -Wextra -O2 -I/opt/minirouter/include 

# Linker flags (Libraries):
# -lczmq      : Link against the high-level ZeroMQ library
# -lwiringPi  : Link against the WiringPi GPIO library
# -lpthread   : Link against the POSIX threading library (needed for mutexes)
LDFLAGS = -lczmq -lwiringPi -lpthread -L/opt/minirouter/lib -Wl,-rpath,'$$ORIGIN/../lib'

all: gpio_buttons_server 

gpio_buttons_server: gpio_buttons_server.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f gpio_buttons_server

.PHONY: all clean
