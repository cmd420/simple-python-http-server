from simple_http_server import HTTPServer, HTTPRequest, HTTPResponseBuilder


server = HTTPServer("127.0.0.1", 8080)


@server.route("/")
def index(request: HTTPRequest):
    name = request.params.get("name", "Unknown")
    age = request.params.get("age", "idk")

    return f"Hey {name}, you're {age} years old."


@server.route("/template")
def template(request: HTTPRequest):
    return HTTPResponseBuilder().from_template("./templates/index.html")


if __name__ == "__main__":
    server.run()
