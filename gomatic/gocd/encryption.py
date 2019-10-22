from gomatic.mixins import CommonEqualityMixin
from distutils.version import LooseVersion as Version

API_PATH = '/go/api/admin/encrypt'
ENDPOINT_INTRODUCED_VERSION = Version('17.1.0')

class Encryption(CommonEqualityMixin):
    def __init__(self, version, client):
        self.version = version
        self.client = client

    def __supported(self):
        return Version(self.version) >= ENDPOINT_INTRODUCED_VERSION

    def encrypt(self, value):
        if not self.__supported():
            raise RuntimeError("Your server does not support the encrypt endpoint, which was introduced in 17.1")

        headers = {'Accept': 'application/vnd.go.cd.v1+json',
                   'Content-Type': 'application/json'}
        data = '{{"value": "{}"}}'.format(value)
        response = self.client.post(API_PATH, data, headers)
        return response.json()['encrypted_value']
