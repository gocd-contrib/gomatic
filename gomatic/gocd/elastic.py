import xml.etree.ElementTree as ET

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement, Ensurance


class Profile(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def properties(self):
        props = {}
        for prop in self.element.findall('property'):
            props[prop.find('key').text] = prop.find('value').text
        return props

    @property
    def profile_id(self):
        return self.element.get('id')

    @property
    def plugin_id(self):
        return self.element.get('pluginId')

    def __eq__(self, other):
        return self.profile_id == other.profile_id


class Profiles(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def profile(self):
        return [Profile(e) for e in self.element.findall('profile')]

    def ensure_profile(self, profile_id, plugin_id, properties):
        properties_xml = "".join(["<property><key>{}</key><value>{}</value></property>".format(k, v) for k, v in properties.items()])
        profile = ET.fromstring('<profile id="{}" pluginId="{}">{}</profile>'.format(profile_id,
            plugin_id,
            properties_xml))
        self.element.append(profile)
        return Profile(profile)

    def ensure_replacement_of_profile(self, profile_id, plugin_id, properties):
        current_profile = [ac for ac in self.profile if ac.profile_id == profile_id]
        if current_profile:
            self.element.remove(current_profile[0].element)
        return self.ensure_profile(profile_id, plugin_id, properties)

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise Exception("Profiles index must be an integer, got {}".format(type(index)))
        return self.profile[index]

    def __len__(self):
        return len(self.profile)


class Elastic(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def profiles(self):
        return Profiles(self.element.find('profiles'))

    def ensure_profiles(self):
        profile = Ensurance(self.element).ensure_child('profiles')
        return Profiles(profile.element)

    def ensure_replacement_of_profiles(self):
        profiles = self.ensure_profiles()
        profiles.make_empty()
        return profiles

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()
