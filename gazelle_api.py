import time
import requests

from collections import deque
from json.decoder import JSONDecodeError

SITE_URLS = {'RED': 'https://redacted.ch/',
             'OPS': 'https://orpheus.network/'}

TRACKER_URLS = {"RED": "https://flacsfor.me/",
                'OPS': "https://home.opsfet.ch/"}

REQUEST_LIMITS = {"RED": 10,
                  'OPS': 5}


class RequestFailure(Exception):
    pass

# noinspection PyTypeChecker
class GazelleApi:
    def __init__(self, site_id=None, key=None, report=lambda *x: None):
        assert site_id in SITE_URLS, f"{site_id} is not a valid id"
        self.id = site_id
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f'{key}'})
        self.last_x_reqs = deque([0], maxlen=REQUEST_LIMITS[site_id])
        self.url = SITE_URLS[site_id]
        self._announce = None
        self.report = report

    @property
    def announce(self):
        if self._announce:
            return self._announce
        else:
            accountinfo = self.request("GET", "index")
            passkey = accountinfo["passkey"]
            url = TRACKER_URLS[self.id] + passkey + '/announce'
            self._announce = url
            return url

    def _rate_limit(self):
        if (t := time.time() - self.last_x_reqs[0]) <= 10:
            self.report(f"sleeping {10-t}", 3)
            time.sleep(10 - t)

    def request(self, req_method, action, data=None, files=None, **kwargs):
        self.report(f"{self.id} {action=}, {kwargs=}", 4)
        self.report(f"{data=}", 5)
        ajaxpage = self.url + 'ajax.php'
        params = {'action': action}
        params.update(kwargs)

        self._rate_limit()
        r = self.session.request(req_method, ajaxpage, params=params, data=data, files=files)
        self.last_x_reqs.append(time.time())

        r.raise_for_status()

        try:
            r_dict = r.json()
            if r_dict["status"] == "success":
                return r_dict["response"]
            elif r_dict["status"] == "failure":
                raise RequestFailure(r_dict["error"])
        except JSONDecodeError:
            return r
