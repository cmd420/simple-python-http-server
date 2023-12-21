import json
import socket
import logging


CRLF = "\r\n"
DBL_CRLF = CRLF * 2

_logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)


class HTTPRequest:
    def __init__(self, raw_request: str) -> None:
        self.raw_request: str = raw_request
        self.params: dict = {}
        self.headers: dict = {}
        self.form: dict = {}
        self.body: str | None = None
        self.method: str = None
        self.route: str = None

        self.__parse()

    def json_body(self):
        return json.loads(self.body)

    def __prase_params(self):
        tokens = self.route.split("?")
        self.route = tokens[0]
        if len(tokens) > 1:
            params = tokens[1].split("&")

            for param in params:
                key, value = param.split("=")
                self.params[key] = value

    def __parse_form(self):
        params = self.body.split("&")
        for param in params:
            key, value = param.split("=")
            self.form[key] = value

    def __parse(self):
        tokens = self.raw_request.split(DBL_CRLF)
        headers = tokens[0]
        self.body = tokens[1]

        headers_lines = headers.split(CRLF)
        self.method, self.route, _ = headers_lines[0].split(" ")

        is_form_req = False
        for header in headers_lines[1:]:
            key, value = header.split(": ")

            if (
                key.lower() == "content-type"
                and value.lower() == "application/x-www-form-urlencoded"
            ):
                is_form_req = True

            self.headers[key] = value

        self.__prase_params()
        if is_form_req:
            self.__parse_form()


class HTTPResponse:
    def __init__(self) -> None:
        self.headers: dict = {}
        self.body: str | None = None
        self.response_code: int = 204

    def __str__(self) -> str:
        headers = ""
        headers += f"Content-Length: {len(self.body)}{CRLF}"

        for hname, hval in self.headers.items():
            if hname.lower() == "content-length":
                continue

            headers += f"{hname}: {hval}"

        return f"HTTP/1.0 {self.response_code}{CRLF}" f"{headers}{CRLF}" (f"{self.body}" if self.body else "") 


class HTTPResponseBuilder:
    def __init__(self) -> None:
        self.response = HTTPResponse()

    def build(self) -> HTTPResponse:
        return self.response

    def from_template(self, path: str):
        with open(path, "r") as file:
            self.status(200)
            self.set_body(file.read())

        return self

    def set_header(self, name: str, value: str):
        self.response.headers[name] = value
        return self

    def delete_header(self, name: str) -> bool:
        if name in self.response.headers:
            del self.response.headers[name]

        return self

    def status(self, code: int):
        self.response.response_code = code
        return self

    def set_body(self, body: str):
        self.response.body = body
        return self


class HTTPServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.routes = {}

    def route(self, path: str, methods: list[str] = ["GET"]):
        def inner(f):
            if path not in self.routes:
                self.routes[path] = {}
            for method in methods:
                self.routes[path][method] = f
            return f

        return inner

    def run(self, backlog: int = 5):
        _logger.debug(f"Binding TCP server at {self.host} port {self.port}")
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(backlog)

        _logger.debug("Listening for incomming requests")
        while True:
            client, addr = self.sock.accept()
            _logger.debug(f"Got new client: {addr}")
            self.__handle_client(client)

    def __handle_client(self, client: socket.socket):
        raw_request = client.recv(1024).decode()
        try:
            request = HTTPRequest(raw_request)
        except:
            client.close()
            return

        if request.route in self.routes:
            if not request.method in self.routes[request.route]:
                response = (405, "Method Not Allowed")
            else:
                response: HTTPResponse | HTTPResponseBuilder | tuple[
                    int, str
                ] | dict | str = self.routes[request.route][request.method](request)

            response_payload = ""
            if isinstance(response, HTTPResponse):
                response_payload = str(response)
            elif isinstance(response, HTTPResponseBuilder):
                response_payload = str(response.build())
            elif (
                isinstance(response, tuple)
                and isinstance(response[0], int)
                and isinstance(response[1], str)
            ):
                _builder = HTTPResponseBuilder()
                _response = _builder.status(response[0]).set_body(response[1]).build()
                response_payload = str(_response)
            elif isinstance(response, dict):
                _builder = HTTPResponseBuilder()
                _response_body = json.dumps(response)
                _response = _builder.status(200).set_body(_response_body).build()
                response_payload = str(_response)
            elif isinstance(response, str):
                _builder = HTTPResponseBuilder()
                _response = _builder.status(200).set_body(response).build()
                response_payload = str(_response)
            else:
                raise ValueError(
                    "Invalid Response. Response should be of type `HTTPResponseBuilder` or `HTTPResponse` or `tuple[int, str]` or `dict` or `str`"
                )
            
            client.sendall(response_payload.encode())
            client.close()
            return

        response = HTTPResponseBuilder().status(404).set_body("Not Found").build()

        client.sendall(str(response).encode())
        client.close()
