import xml.etree.ElementTree as ET

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement, Ensurance


class Role(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def name(self):
        return self.element.get('name')

    @property
    def users(self):
        return [u.text for u in self.element.find('users').findall('user')]


class Roles(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def role(self):
        return [Role(r) for r in self.element.findall('role')]

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def ensure_role(self, name, users):
        users_xml = ''.join(['<user>{}</user>'.format(user) for user in users])
        role_xml = '<role name="{}"><users>{}</users></role>'.format(name, users_xml)
        role_element = ET.fromstring(role_xml)
        self.element.append(role_element)
        return self

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise Exception("Roles index must be an integer, got {}".format(type(index)))
        return self.role[index]

    def __len__(self):
        return len(self.role)


class Security(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def roles(self):
        return Roles(self.element.find('roles'))

    def ensure_roles(self):
        roles = Ensurance(self.element).ensure_child('roles')
        return Roles(roles.element)

    def ensure_replacement_of_roles(self):
        roles = self.ensure_roles()
        roles.make_empty()
        return roles

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()
