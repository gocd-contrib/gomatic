import codecs
import json

empty_config_xml = """<?xml version="1.0" encoding="utf-8"?>
<cruise xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="cruise-config.xsd" schemaVersion="72">
  <server artifactsdir="artifacts" commandRepositoryLocation="default" serverId="96eca4bf-210e-499f-9dc9-0cefdae38d0c" />
</cruise>"""

# This is the oldest version we currently support. Ideally we can make this more automagic in the future
DEFAULT_VERSION='16.3.0'

class FakeResponse(object):
    def __init__(self, text):
        self.text = text
        self.headers = {'x-cruise-config-md5': '42'}
        self.status_code = 200
    def json(self):
        return json.loads(self.text)

class FakeHostRestClient(object):
    def __init__(self, config_string, thing_to_recreate_itself=None, version=DEFAULT_VERSION):

        self.config_string = config_string
        self.thing_to_recreate_itself = thing_to_recreate_itself
        self.version = version

    def __repr__(self):
        if self.thing_to_recreate_itself is None:
            return 'FakeConfig(whatever)'
        else:
            return self.thing_to_recreate_itself

    def get(self, path):
        # sorry for the duplication/shared knowledge of code but this is easiest way to test
        # what we want in a controlled way
        if path == "/go/api/admin/config.xml":
            return FakeResponse(self.config_string)
        if path == "/go/api/version":
            return FakeResponse('{{"version": "{}"}}'.format(self.version))
        raise RuntimeError("not expecting to be asked for anything else")


def load_file(config_name):
    with codecs.open('test-data/' + config_name + '.xml', encoding='utf-8') as xml_file:
        xml_data = xml_file.read()
    return xml_data


def config(config_name):
    return FakeHostRestClient(load_file(config_name))


def empty_config():
    return FakeHostRestClient(empty_config_xml, "empty_config()")
