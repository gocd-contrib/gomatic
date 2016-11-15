from xml.etree import ElementTree as ET
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement, Ensurance

import uuid
import urllib

class GenericArtifactoryRepositoryPackage(CommonEqualityMixin):
    pass


class GenericArtifactoryRepository(CommonEqualityMixin):
    def __init__(self, element, configurator):
        self.element = element
        self.configuration = configurator

        if not self.has_id:
            self.__set_id()

    def __repr__(self):
        return 'GenericArtifactoryRepository("%s")' % self.name

    @property
    def name(self):
        return self.element.attrib['name']

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def make_configuration_empty(self):
        for child in self.element.findall('configuration'):
            PossiblyMissingElement(child).remove_all_children()

    @property
    def has_id(self):
        return 'id' in self.element.attrib

    def __set_id(self):
        Ensurance(self.element).set('id', str(uuid.uuid1()))

    def set_configuration_property(self, name, value, encrypted=False):
        Ensurance(self.element).ensure_child_with_attribute('pluginConfiguration', 'id', 'generic-artifactory').set('version', '1')

        config = Ensurance(self.element).ensure_child('configuration')
        if encrypted:
            new_element = ET.fromstring('<property><key>%s</key><encryptedValue>%s</encryptedValue></property>' % (name, value))
        else:
            new_element = ET.fromstring('<property><key>%s</key><value>%s</value></property>' % (name, value))
        config.append(new_element)

    def set_encrypted_configuration_property(self, name, encrypted_value):
        self.set_configuration_property(name, encrypted_value, encrypted=True)

    def set_repository_url(self, repository_url):
        self.set_configuration_property('REPO_URL', repository_url)
        return self

    def set_credentials(self, username, password):
        self.set_configuration_property('USERNAME', urllib.quote(username, safe=''))
        self.set_encrypted_configuration_property('PASSWORD', password)
        return self