import asyncio
import base64
import logging
import uvloop
from aiohttp import web
from aioprometheus import Service, Counter, Histogram, Gauge, render, timer, Summary, Registry
from datetime import datetime
from functools import wraps
from importlib import import_module
from typing import Any, List
from os import path, getenv
from psutil import cpu_percent, virtual_memory, swap_memory
from socket import gethostname
from yaml import load, SafeLoader
from pythonjsonlogger import jsonlogger
from xmltodict import unparse

api_type = getenv("API_TYPE") or "JSON"
url_token = ""
username = ""
password = ""

try:
    local_dir = path.abspath(path.dirname(__file__))
    read_auth = open(path.join(local_dir, "../../auth.yaml"), "r")
    auth = load(read_auth, Loader=SafeLoader)
    url_token = auth["token"]
    username = auth["username"]
    password = auth["password"]

except Exception as e:
    if "No such file or directory" in str(e):
        print("starting server with default credentials from ahttptemplate")
    else:
        print(repr(e))

    url_token = "2bb6d7c7-bc8b-40ea-a29e-75f7151cfa6d"
    username = "admin"
    password = "password"

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

logger = logging.getLogger()
logger.setLevel(getenv("LOG_LEVEL") or 10)
logHandler = logging.StreamHandler()
formatter = CustomJsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

prometheus_service = Service()
prometheus_service.registry = Registry()
prometheus_labels = {
    "host": gethostname(),
}
ping_counter = Counter(
    "health_check_counter", "total ping requests."
)
latency_metric = Histogram(
    "request_latency_seconds",
    "request latency in seconds.",
    const_labels=prometheus_labels,
    buckets=[0.1, 0.5, 1.0, 5.0],
)
ram_metric = Gauge(
    "memory_usage_bytes", "memory usage in bytes.", const_labels=prometheus_labels
)
cpu_metric = Gauge(
    "cpu_usage_percent", "cpu usage percent.", const_labels=prometheus_labels
)
metrics_request_time = Summary(
    "metrics_processing_seconds", "time spent processing request for metrics in seconds.", const_labels=prometheus_labels
)

prometheus_service.registry.register(ping_counter)
prometheus_service.registry.register(latency_metric)
prometheus_service.registry.register(ram_metric)
prometheus_service.registry.register(cpu_metric)
prometheus_service.registry.register(metrics_request_time)

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
                pkg = import_module(f"controllers.{controller_name}")
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
            web.route("GET", "/metrics", metrics),
            web.route("GET", "/metrics/", metrics),
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
    ping_counter.inc({"path": request.path})
    ping_resp = {"code": "SUCCESS", "info": "PONG"}
    if api_type.upper() == "JSON":
        resp = web.json_response(ping_resp, status=200)
    elif api_type.upper() == "XML":
        resp = xml_response(ping_resp, status=200)
    return resp

@timer(metrics_request_time)
async def metrics(request: web.Request) -> web.Response:
    ram_metric.set({"type": "virtual"}, virtual_memory().used)
    ram_metric.set({"type": "swap"}, swap_memory().used)

    for c, p in enumerate(cpu_percent(interval=0, percpu=False)):
        cpu_metric.set({"core": c}, p)

    return await prometheus_service.handle_metrics(request)

async def error_handler(request: web.Request) -> web.Response:
    err_resp = {"CODE": "ERROR", "info": "404 not found"}
    if api_type.upper() == "JSON":
        resp = web.json_response(err_resp, status=404)
    elif api_type.upper() == "XML":
        resp = xml_response(err_resp, status=404)
    return resp

def xml_response(input_dict: dict, status: int=200) -> web.Response:
    response = web.Response(status=status)
    response.body = unparse({"response": input_dict})
    return response
