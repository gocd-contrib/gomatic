empty_config_xml = """<?xml version="1.0" encoding="utf-8"?>
<cruise xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="cruise-config.xsd" schemaVersion="72">
  <server artifactsdir="artifacts" commandRepositoryLocation="default" serverId="96eca4bf-210e-499f-9dc9-0cefdae38d0c" />
</cruise>"""


class FakeResponse(object):
    def __init__(self, text):
        self.text = text
        self.headers = {'x-cruise-config-md5': '42'}


class FakeHostRestClient:
    def __init__(self, config_string, thing_to_recreate_itself=None):
        self.config_string = config_string
        self.thing_to_recreate_itself = thing_to_recreate_itself

    def __repr__(self):
        if self.thing_to_recreate_itself is None:
            return 'FakeConfig(whatever)'
        else:
            return self.thing_to_recreate_itself

    def get(self, path):
        # sorry for the duplication/shared knowledge of code but this is easiest way to test
        # what we want in a controlled way
        if path == "/go/admin/restful/configuration/file/GET/xml":
            return FakeResponse(self.config_string)
        raise RuntimeError("not expecting to be asked for anything else")


def config(config_name):
    return FakeHostRestClient(open('test-data/' + config_name + '.xml').read())


def empty_config():
    return FakeHostRestClient(empty_config_xml, "empty_config()")