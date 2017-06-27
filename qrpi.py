import io
import base64

import asyncio
from aiohttp import web

import qrcode
from decouple import config
import time


class RateLimiterClient:
    def __init__(self, rate, per):
        """
        Initialise a rate limiter for a single client

        :param rate: rate limit
        :param per: check rate
        """
        self.rate = rate
        self.per = per
        self.allowance = self.rate  # requests
        self.last_check = time.time()

    def check(self, increase=True):
        """
        Checks if this client is above the rate limit

        :param increase: if True, increase the requests number
        :return: True if the client is allowed,
                 False if the client has surpassed the rate limit
        """
        if not CONFIG["RATE_LIMIT"]:
            return True
        current = time.time()
        time_passed = current - self.last_check
        if increase:
            self.last_check = current
        self.allowance += time_passed * (self.rate / self.per)
        if self.allowance > self.rate:
            self.allowance = self.rate  # throttle
        if self.allowance < 1.0:
            return False
        else:
            if increase:
                self.allowance -= 1.0
            return True


class RateLimiter:
    def __init__(self, rate, per):
        """
        Initialise a group of RateLimiterClient

        :param rate: rate limit
        :param per: check rate
        """
        self.rate = rate
        self.per = per
        self.clients = {}

    def check(self, client_id, increase=True):
        """
        Checks if a client is above the rate limit.
        If the client doesn't exist, a new RateLimiterClient object
        is created and added to clients dictionary.

        :param client_id: client identifier
        :param increase: if True, increase the requests number
        :return: True if the client is allowed,
                 False if the client has surpassed the rate limit
        """
        if client_id not in self.clients:
            self.clients[client_id] = RateLimiterClient(self.rate, self.per)
        return self.clients[client_id].check(increase)

CONFIG = {
    "WEB_HOST": config("WEB_HOST", default="127.0.0.1"),
    "WEB_PORT": config("WEB_PORT", default="8833", cast=int),
    "RATE_LIMIT": config("RATE_LIMIT", default="1", cast=bool),
    "RATE_LIMIT_RATE": config("RATE_LIMIT_RATE", default="60", cast=int),
    "RATE_LIMIT_PER": config("RATE_LIMIT_PER", default="60", cast=int),
}
RATE_LIMITER = RateLimiter(rate=CONFIG["RATE_LIMIT_RATE"], per=CONFIG["RATE_LIMIT_PER"])


class InvalidArgumentError(Exception):
    def __init__(self, arg_name):
        self.arg_name = arg_name


def async_run(func, _ioloop=None, *args):
    """
    Run a sychronous function asynchronously.
    Usage:
    ```
    await async_run(func, arg1, arg2, kwarg1=1)
    ```

    :param func: function object to run (not function call)
    :param _ioloop: IOLoop
    :param args: function arguments
    :param kwargs: function keyword arguments
    :return: future
    """
    if _ioloop is None:
        _ioloop = asyncio.get_event_loop()
    return _ioloop.run_in_executor(None, func, *args)


def get_arg(request, name, default, acceptable=None):
    """
    Checks if an argument is passed as a GET parameter
    to a `aiohttp.web.Request` object and if it is valid

    :param request: `aiohttp.web.Request` object
    :param name: name of the GET parameter
    :param default: default value if the parameter was not passed
    :param acceptable: acceptable values. Can be `int`, `bool` or a `list`.
                       - If `int`, digit-only strings will be considered valid and function
                       will return the parameter already casted to `int`;
                       - If `bool`, `1`, `yes`, `y`, and `true` will be treated as `True`
                       and `0`, `no`, `n`, and `false` will be treated as `False`.
                       All other values are be considered invalid;
                       - If `list`, all values inside `acceptable` are considered valid
                       (case insensitive)
    :return: GET argument (if provided), or default one if it's not present.
             Returns an `int` if `acceptable = int`, `bool` if `acceptable = bool`,
             otherwise `str`
    :raises: `InvalidArgumentError()` if the argument is not valid.
    """
    if name in request.GET:
        # Argument provided, check if it's valid
        if acceptable is not None:
            if acceptable is int:
                if request.GET[name].isdigit():
                    return int(request.GET[name])
                raise InvalidArgumentError(name)
            elif acceptable is list and request.GET[name].lower() not in acceptable:
                raise InvalidArgumentError(name)
            elif acceptable is bool and request.GET[name]:
                if request.GET[name].lower() in ["1", "yes", "0", "no", "y", "n", "true", "false"]:
                    return request.GET[name].lower() in ["1", "yes", "y", "true"]
                raise InvalidArgumentError(name)
        return request.GET[name]
    else:
        # Argument not provided, return the default one
        return default


def get_ip(request):
    """
    Get request's IP adddress

    :param request: aiohttp request
    :return:
    """
    if "CF-Connecting-IP" in request.headers:
        return request.headers["CF-Connecting-IP"]
    elif "X-Forwarded-For" in request.headers:
        return request.headers["X-Forwarded-For"]
    else:
        return request.transport.get_extra_info("peername"),

async def qr(request):
    """
    QR Code generator handler

    :param request:
    :return:
    """
    try:
        # Rate limit check
        if not RATE_LIMITER.check(get_ip(request)):
            return web.json_response({
                "status": 429,
                "message": "Rate limit exceeded, slow down!"
            })

        # Make sure `data` was passed
        if "data" not in request.GET:
            return web.json_response({
                "status": 400,
                "message": "Missing required `data` GET argument"
            }, status=400)

        # Get options
        version = get_arg(request, "version", None, int)
        error_correction = get_arg(request, "error_correction", "m", [
            "m", "h", "l", "q"
        ])
        error_correction = {
            "m": qrcode.constants.ERROR_CORRECT_M,
            "h": qrcode.constants.ERROR_CORRECT_H,
            "l": qrcode.constants.ERROR_CORRECT_L,
            "q": qrcode.constants.ERROR_CORRECT_Q,
        }[error_correction]
        box_size = get_arg(request, "box_size", 10, int)
        border = get_arg(request, "border", 4, int)
        as_base64 = get_arg(request, "base64", 0, bool)

        # Generate QR Code with provided options
        qr = qrcode.QRCode(
            version=version,
            error_correction=error_correction,
            box_size=box_size,
            border=border
        )
        qr.add_data(request.GET["data"])
        await async_run(qr.make, asyncio.get_event_loop(), True)

        # Make image
        img = await async_run(qr.make_image)
        output = io.BytesIO()
        img.save(output)
        image_data = output.getvalue()

        # Return qr code as base64
        if as_base64:
            data_url = "data:image/jpg;base64," + base64.b64encode(image_data).decode()
            return web.json_response({
                "status": 200,
                "data": data_url
            }, status=200)

        # Or return it as a normal image
        return web.Response(body=image_data, content_type="image/jpeg")
    except InvalidArgumentError as e:
        return web.json_response({
            "status": 400,
            "message": "Invalid argument value ({})".format(e.arg_name)
        }, status=400)


def main():
    app = web.Application()
    app.router.add_get("/", qr)
    web.run_app(app, host=CONFIG["WEB_HOST"], port=CONFIG["WEB_PORT"])


if __name__ == "__main__":
    main()
