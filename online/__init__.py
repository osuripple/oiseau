import requests


class OnlineApiError(Exception):
    def __init__(self, request):
        self.request = request


class OnlineApiClient:
    API_BASE = "https://api.online.net"

    def __init__(self, api_key):
        self.api_key = api_key

    def request(self, handler, method="GET", data=None, json=None):
        method = method.lower()
        methods = {
            "get": requests.get,
            "post": requests.post,
            "put": requests.put,
            "patch": requests.patch,
            "delete": requests.delete
        }
        r = methods[method](
            url="{}/{}".format(self.API_BASE.rstrip("/"), handler.lstrip("/")),
            headers=self.auth_header,
            data=data,
            json=json
        )
        if not 200 <= r.status_code <= 299:
            raise OnlineApiError(r)

        try:
            return r.json()
        except:
            # Some online.net api handlers return non-json data or nothing at all
            return r.text

    @property
    def auth_header(self):
        return {
            "Authorization": "Bearer {}".format(self.api_key)
        }

    def auth_valid(self):
        try:
            return self.request("api/v1/user")
        except OnlineApiError:
            return False
