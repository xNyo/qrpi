# qrpi
**qrpi** is a little qr code generator web api written in Python with asyncio and
[qrcode](https://github.com/lincolnloop/python-qrcode), in a single file

## Requirements
- Python 3.6

## Installation
Check out [this asciinema](https://asciinema.org/a/fSdRROhNVRhm7U95jQosMM85O) or follow the instructions below
```bash
# get the source code
$ git clone ...
$ cd qrpi

# customize web server host, port and rate limit
# (optional, the api will use its default settings
# if settings.ini is not present in the current directory)
$ cp settings.sample.ini settings.ini
$ nano settings.ini
...

# create a virtualenv and install the required dependencies
$ virtualenv -p $(which python3.6) .pyenv
$ source .pyenv/bin/activate
(.pyenv) $ pip install -r requirements.txt

# start the web server (nohup/tmux needed for production)
(.pyenv) $ python3 qrpi.py
======== Running on http://0.0.0.0:8833 ========
(Press CTRL+C to quit)
```

## Usage
When you start the program, an aiohttp server will start on the port you've set in the config file (default: `8833`).
There's only one API handler (`/`), and it accepts there GET parameters:

### GET parameters
Name               | Description                                                       | Required? | Default
-------------------|-------------------------------------------------------------------|---------- | --------
`data`             | QR Code's content                                                 | Yes       | -
`version`          | QR Code version (size), from 1 to 40. 1 = smallest (21x21 matrix) | No        | Auto detected
`error_correction` | QR Code error correction (`l`,`m`,`q`,`h`)                        | No        | `m`
`box_size`         | Number of pixels of each QR Code 'box'                            | No        | Auto detected
`border`           | Number of 'boxes' empty from the border (min 4)                   | No        | `4`
`base64`           | Returns a base64 data URL if `1`, else it returns an image        | No        | `0`

### Response
The response can be either a JPG image (`Content-Type: image/jpeg;`) or a JSON Object (`Content-Type: application/json;`).
A JSON object will be returned if there's an error or if the `base64` parameter is `1`. In all other cases, a JPEG
image will be returned. In case of a JSON object, it'll always contain a `status` key, that complies with the HTTP
status code. If there's an error a `message` key that explains the error will be present in the JSON response too.

Name      | Description                  | Always present?
----------|------------------------------|--------------------------------
`status`  | Status code                  | Yes
`message` | Message explaining the error | No, only if there was an error
`data`    | Base64 data URL              | No, only if `base64 = 1`

### Status codes

Status code | Description
------------|--------------------------------
`200`       | Request processed successfully
`400`       | Missing or invalid parameter
`429`       | Rate limit exceeded
`500`       | Internal server error

## Rate limit
The default rate limit is 60 request per minute from a single IP address. The rate limit can be adjusted or entirely
disabled from the settings file.

## Deploying
One way of deploying the api is using nginx as a reverse proxy.
This is a sample nginx config for qrpi:
```
server {
    server_name qrpi.mydomain.com;
    listen 80;
    charset utf-8;

    location / {
        proxy_pass http://localhost:8833;
    }
}
```
The api checks the IP address from the `CF-Connecting-IP` and `X-Forwarded-For` headers if possible,
so you don't need any extra configuration if you're using Cloudflare.

## License
MIT