CC = gcc

CFLAGS = -Wall -Wextra -O2

# Linker flags (Libraries):
# -lczmq      : Link against the high-level ZeroMQ library
# -lwiringPi  : Link against the WiringPi GPIO library
# -lpthread   : Link against the POSIX threading library (needed for mutexes)
LDFLAGS = -lczmq -lwiringPi -lpthread

all: gpio_buttons 

gpio_buttons: gpio_buttons.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f gpio_buttons

.PHONY: all clean
