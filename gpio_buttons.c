#include <czmq.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wiringPi.h>

zsock_t *publisher = NULL;

int last_state[32];
#define POLL_RATE_MS 50

int main(void) {
  const char *port_env = getenv("SERVER_PORT");
  const char *pins_env = getenv("GPIO_PINS");
  const char *pull_env = getenv("PULL_UPDOWN");

  int server_port = port_env ? atoi(port_env) : 5555;

  const char *pull_mode = pull_env ? pull_env : "up";

  if (strcmp(pull_mode, "up") != 0 && strcmp(pull_mode, "down") != 0) {
    fprintf(stderr, "Error: invalid PULL_UPDOWN value\n");
    exit(1);
  }

  if (!pins_env) {
    fprintf(stderr, "Error: GPIO_PINS environment variable is required\n");
    exit(1);
  }

  for (int i = 0; i < 32; i++)
    last_state[i] = -1;

  publisher = zsock_new_pub(NULL);
  if (!publisher) {
    fprintf(stderr, "Error: Could not create ZMQ socket\n");
    return 1;
  }

  int rc = zsock_bind(publisher, "tcp://*:%d", server_port);
  if (rc == -1) {
    fprintf(stderr, "Error: Could not bind ZMQ socket\n");
    return 1;
  }

  printf("Server started. Publishing button events on port %d...\n",
         server_port);

  if (wiringPiSetup() == -1) {
    fprintf(stderr, "Error: WiringPi setup failed. Are you running as root?\n");
    exit(1);
  }

  int monitored_pins[32];
  int pin_count = 0;

  char *pins_copy = strdup(pins_env);
  char *token = strtok(pins_copy, ",");
  while (token != NULL) {
    int pin = atoi(token);
    if (pin >= 0 && pin <= 31) {
      pinMode(pin, INPUT);
      if (strcmp(pull_mode, "down") == 0) {
        pullUpDnControl(pin, PUD_DOWN);
      } else {
        pullUpDnControl(pin, PUD_UP);
      }
      monitored_pins[pin_count++] = pin;

      last_state[pin] = digitalRead(pin);
    }
    token = strtok(NULL, ",");
  }
  free(pins_copy);

  while (!zsys_interrupted) {
    for (int i = 0; i < pin_count; i++) {
      int pin = monitored_pins[i];
      int current_val = digitalRead(pin);

      if (current_val != last_state[pin]) {
        int direction = 0;

        if (current_val == 1 && last_state[pin] == 0) {
          direction = 1;
        } else if (current_val == 0 && last_state[pin] == 1) {
          direction = -1;
        }

        int msg_val = pin * direction;

        zstr_sendf(publisher, "%d", msg_val);

        last_state[pin] = current_val;
      }
    }

    zclock_sleep(POLL_RATE_MS);
  }

  printf("Stopping GPIO Monitor...\n");

  zsock_destroy(&publisher);

  return 0;
}
