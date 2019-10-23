import xml.etree.ElementTree as ET

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement


class ArtifactStore(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def id(self):
        return self.element.attrib['id']

    @property
    def plugin_id(self):
        return self.element.attrib['pluginId']

    @property
    def properties(self):
        props = {}
        for prop in self.element.findall('property'):
            props[prop.find('key').text] = prop.find('value').text
        return props

    def __eq__(self, other):
        return self.id == other.id


class ArtifactStores(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def artifact_store(self):
        return [ArtifactStore(e) for e in PossiblyMissingElement(self.element).findall('artifactStore')]

    def ensure_artifact_store(self, id, plugin_id, properties):
        properties_xml = "".join(["<property><key>{}</key><value>{}</value></property>".format(k, str(v or '')) for k, v in properties.items()])
        new_element = ET.fromstring('<artifactStore id="{}" pluginId="{}">{}</artifactStore>'.format(id, plugin_id, properties_xml))
        self.element.append(new_element)
        return ArtifactStore(new_element)

    def ensure_replacement_of_artifact_store(self, id, plugin_id, properties):
        for artifact_store in self.artifact_store:
            if artifact_store.id == id and artifact_store.plugin_id == plugin_id:
                self.element.remove(artifact_store.element)
        return self.ensure_artifact_store(id, plugin_id, properties)

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise Exception("ArtifactStores index must be an integer, got {}".format(type(index)))
        return self.artifact_store[index]

    def __len__(self):
        return len(self.artifact_store)
