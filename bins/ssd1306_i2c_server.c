#include <czmq.h>
#include <ssd1306_i2c.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

zsock_t *server = NULL;

int main(void) {
  const char *port_env = getenv("SERVER_PORT");
  const char *i2c_dev_env = getenv("PULL_UPDOWN");

  int server_port = port_env ? atoi(port_env) : 5555;

  const char *i2c_dev = i2c_dev_env ? i2c_dev_env : "/dev/i2c-3";

  int count = 0;

  ssd1306_i2c_t *oled = ssd1306_i2c_open(i2c_dev, 0x3c, 128, 32, NULL);
  if (!oled) {
    return 1;
  }
  if (ssd1306_i2c_display_initialize(oled) < 0) {
    fprintf(stderr, "ERROR: Failed to initialize the display. Check if it is "
                    "connected !\n");
    ssd1306_i2c_close(oled);
    return 1;
  }
  ssd1306_framebuffer_t *fbp =
      ssd1306_framebuffer_create(oled->width, oled->height, oled->err);
  if (!fbp) {
    fprintf(stderr, "Error: Could not create ssd1306 framebuffer\n");
    return 1;
  }
  ssd1306_i2c_display_clear(oled);
  ssd1306_framebuffer_box_t bbox;
  ssd1306_framebuffer_draw_text(fbp, "Display started", 0, 0, 16,
                                SSD1306_FONT_DEFAULT, 3, &bbox);
  ssd1306_i2c_display_update(oled, fbp);

  server = zsock_new_rep(NULL);
  if (!server) {
    fprintf(stderr, "Error: Could not create ZMQ socket\n");
    return 1;
  }

  int rc = zsock_bind(server, "tcp://*:%d", server_port);
  if (rc == -1) {
    fprintf(stderr, "Error: Could not bind ZMQ socket\n");
    return 1;
  }

  printf("Server started. Waiting for display frames on port %d...\n",
         server_port);

  zpoller_t *poller = zpoller_new(server, NULL);

  while (!zsys_interrupted) {
    void *which = zpoller_wait(poller, 1000);

    if (zpoller_terminated(poller)) {
      break;
    }

    if (which == server) {
      zmsg_t *msg = zmsg_recv(server);
      if (!msg) {
        break;
      }

      zframe_t *frame = zmsg_first(msg);

      byte *data = zframe_data(frame);
      size_t size = zframe_size(frame);

      ssd1306_framebuffer_clear(fbp);
      size_t written = 0;
      for (uint8_t y = 0; y < fbp->height; ++y) {
        if (written > size) {
          break;
        }
        for (uint8_t x = 0; x < fbp->width; ++x) {
          if (written > size) {
            break;
          }
          int idx = y * fbp->width + x;
          ssd1306_framebuffer_put_pixel(fbp, x, y, data[idx] > 0);
          written += 1;
        }
      }
      ssd1306_i2c_run_cmd(oled, SSD1306_I2C_CMD_POWER_ON, 0, 0);
      ssd1306_i2c_display_update(oled, fbp);

      byte ack_data[] = {0x61};
      zsock_send(server, "b", ack_data, 1);
      zmsg_destroy(&msg);

      count = 0;
    } else {
      count += 1;
      if (count == 60) {
        printf("no message received for a while, clearing screen...\n");
        ssd1306_i2c_run_cmd(oled, SSD1306_I2C_CMD_POWER_OFF, 0, 0);
      }
    }
  }

  printf("Stopping...\n");

  zpoller_destroy(&poller);
  zsock_destroy(&server);

  ssd1306_i2c_run_cmd(oled, SSD1306_I2C_CMD_POWER_OFF, 0, 0);
  ssd1306_framebuffer_destroy(fbp);
  ssd1306_i2c_close(oled);

  return rc;
}
