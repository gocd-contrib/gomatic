from uuid import uuid4
from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance


class Repository(CommonEqualityMixin):
    def __init__(self, element):
        self.__element = element
        self.__properties = list(map((lambda e: Property(e)), element.findall("configuration/property")))
        self.__packages = list(map((lambda e: Package(e)), element.findall("packages/package")))

    @property
    def properties(self):
        return self.__properties

    @property
    def packages(self):
        return self.__packages

    @property
    def name(self):
        return self.__element.attrib['name']

    @property
    def id(self):
        return self.__element.attrib['id']

    @property
    def repo_url(self):
        return [p for p in self.__properties if p.key == 'REPO_URL'][0].value

    @property
    def type(self):
        return self.__element.find('pluginConfiguration').attrib['id']

    def ensure_type(self, type, version):
        plugin_configuration = Ensurance(self.__element).ensure_child_with_attribute('pluginConfiguration', 'id', type)
        plugin_configuration.set('version', version)
        return plugin_configuration.element

    def ensure_property(self, key, value):
        config_element = Ensurance(self.__element).ensure_child('configuration').element
        property_element = Ensurance(config_element).ensure_child_with_descendant('property', 'key', key).element
        value_tag = Ensurance(property_element).ensure_child('value')
        value_tag.set_text(value)
        return Property(property_element)

    def ensure_package(self, name):
        ens = Ensurance(self.__element).ensure_child('packages').ensure_child_with_attribute('package', 'name', name)
        if not ens.has_attribute('id'):
            ens.set('id', str(uuid4()))
        return Package(ens.element)


class Property(CommonEqualityMixin):
    def __init__(self, element):
        self.__element = element

    @property
    def key(self):
        return self.__element.find('key').text

    @property
    def value(self):
        return self.__element.find('value').text


class Package(CommonEqualityMixin):
    def __init__(self, element):
        self.__element = element
        self.__properties = list(map((lambda e: Property(e)), element.findall("configuration/property")))

    @property
    def name(self):
        return self.__element.attrib['name']

    @property
    def id(self):
        return self.__element.attrib['id']

    @property
    def properties(self):
        return self.__properties

    @property
    def package_spec(self):
        return [p for p in self.__properties if p.key == 'PACKAGE_SPEC'][0].value

    def ensure_property(self, key, value):
        config_element = Ensurance(self.__element).ensure_child('configuration').element
        property_element = Ensurance(config_element).ensure_child_with_descendant('property', 'key', key).element
        value_tag = Ensurance(property_element).ensure_child('value')
        value_tag.set_text(value)
        return Property(property_element)
