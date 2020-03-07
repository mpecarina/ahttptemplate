import asyncio
import base64
import logging
import uvloop
from aiohttp import web
from datetime import datetime
from functools import wraps
from importlib import import_module
from typing import Any
from os import path, getenv
from yaml import load, SafeLoader
from pythonjsonlogger import jsonlogger
from xmltodict import unparse

api_type = getenv("API_TYPE") or "JSON"
url_token = ""
username = ""
password = ""

try:
    local_dir = path.abspath(path.dirname(__file__))
    read_auth = open(path.join(local_dir, "../../auth.yml"), "r")
    auth = load(read_auth, Loader=SafeLoader)
    url_token = auth["token"]
    username = auth["username"]
    password = auth["password"]

except Exception as e:
    if "No such file or directory" in str(e):
        print("starting server with default credentials from ahttptemplate")
    else:
        print(repr(e))

    url_token = "f56a0e72-9f11-43f2-a936-f948a29ecd95"
    username = "admin"
    password = "p@ssw0rd"

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname

def verify_url_token(f):
    @wraps(f)
    def handler(*args, **kwargs):
        if not "token" in args[0].query:
            return xml_response({"code": "ERROR", "info": "missing required token"}, status=422)
        elif args[0].query["token"] == url_token:
            return f(*args, **kwargs)
        else:
            return xml_response({"code": "ERROR", "info": "incorrect token string"}, status=401)
    return handler

def basic_auth(f):
    @wraps(f)
    def handler(*args, **kwargs):
        auth_header = args[0].headers.get("Authorization", None)
        if not auth_header or not auth_header.startswith("Basic "):
            return xml_response({"code": "ERROR", "info": "missing required authentication header"}, status=401)
        auth_header = auth_header.encode()
        auth_decoded = base64.decodestring(auth_header[6:])
        usr, pwd = auth_decoded.decode().split(":", 2)
        if not (usr == username and pwd == password):
            return xml_response({"code": "ERROR", "info": "incorrect username and password combination"}, status=401)
        return f(*args, **kwargs)
    return handler

def init_app(**kwargs: Any) -> web.Application:
    try:
        global logger
        logger = logging.getLogger()
        logger.setLevel(getenv("LOG_LEVEL") or logging.DEBUG)
        logHandler = logging.StreamHandler()
        formatter = CustomJsonFormatter()
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)

        middleware = kwargs.get("middleware") or []
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        return web.Application(middlewares=middleware)
    except:
        raise

def add_routes(app: web.Application, handlers: dict) -> None:
    try:
        controller_names = handlers.keys()
        for controller_name in controller_names:
            controllers = handlers[controller_name]
            for controller in controllers:
                handler_name = next(iter(controller.keys()))
                pkg = import_module(f".controllers.{controller_name}", __name__)
                imported_handler = eval(f"pkg.{handler_name}")
                path_no_slash = str(controller[handler_name]['paths'][0])
                path_trailing_slash = f"{controller[handler_name]['paths'][0]}/"
                app.add_routes([
                    web.route(controller[handler_name]["method"], path_no_slash, imported_handler),
                    web.route(controller[handler_name]["method"], path_trailing_slash, imported_handler)
                ])
        app.add_routes([
            web.route("GET", "/ping", ping),
            web.route("GET", "/ping/", ping),
            web.route("*", "/{tail:.*}", error_handler),
        ])
    except:
        raise

def listen_on_port(app: web.Application, port: int) -> None:
    try:
        web.run_app(app, port=port)
    except:
        raise

async def ping(request: web.Request) -> web.Response:
    ping_resp = {"code": "SUCCESS", "info": "PONG"}
    if api_type.upper() == "JSON":
        return web.json_response(ping_resp, status=200)
    elif api_type.upper() == "XML":
        return xml_response(ping_resp, status=200)

async def error_handler(request: web.Request) -> web.Response:
    err_resp = {"CODE": "ERROR", "info": "404 not found"}
    if api_type.upper() == "JSON":
        return web.json_response(err_resp, status=404)
    elif api_type.upper() == "XML":
        return xml_response(err_resp, status=404)

def xml_response(input_dict: dict, status: int=200) -> web.Response:
    response = web.Response(status=status)
    response.body = unparse({"response": input_dict})
    return response