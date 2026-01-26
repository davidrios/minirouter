import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class ImageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.handle_index()
        elif self.path.startswith("/image"):
            self.handle_image()
        else:
            self.send_error(404, "Page Not Found")

    def handle_index(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: sans-serif; text-align: center; padding: 50px; background-color: black; }
                img { border: 5px solid #333; margin-top: 20px; }
            </style>
        </head>
        <body>
            <img src="/image" alt="Generated Content" />
            <script>
                const imgEl = document.querySelector('img')
                setInterval(() => {
                    imgEl.src = '/image?t=' + new Date()
                }, 200)
            </script>
        </body>
        </html>
        """
        self.wfile.write(html_content.encode("utf-8"))

    def handle_image(self):
        try:
            image_data = self.server.data_callback()
            self.send_response(200)
            self.send_header("Content-type", "image/bmp")
            # self.send_header("Content-length", str(len(image_data)))
            self.end_headers()
            self.wfile.write(image_data.getbuffer())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error generating image: {e}".encode())


class ImageServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, data_callback):
        super().__init__(server_address, RequestHandlerClass)
        self.data_callback = data_callback


HOST_NAME = os.environ.get("HOST_NAME", "localhost")
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))


def get_server(get_image):
    return ImageServer((HOST_NAME, SERVER_PORT), ImageHandler, data_callback=get_image)
