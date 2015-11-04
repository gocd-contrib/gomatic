import json
from xml.dom.minidom import parseString
import requests


def prettify(xml_string):
    xml = parseString(xml_string)
    formatted_but_with_blank_lines = xml.toprettyxml()
    non_blank_lines = [l for l in formatted_but_with_blank_lines.split('\n') if len(l.strip()) != 0]
    return '\n'.join(non_blank_lines)


def then(s):
    return '\\\n\t.' + s


class HostRestClient:
    def __init__(self, host):
        self.__host = host

    def __repr__(self):
        return 'HostRestClient("%s")' % self.__host

    def __path(self, path):
        return ('http://%s' % self.__host) + path

    def get(self, path):
        return requests.get(self.__path(path))

    def post(self, path, data):
        url = self.__path(path)
        result = requests.post(url, data)
        if result.status_code != 200:
            try:
                result_json = json.loads(result.text.replace("\\'", "'"))
                message = result_json.get('result', result.text)
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s]:\n%s" % (url, result.status_code, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s] (and result was not json):\n%s" % (url, result.status_code, result))