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


class PluginRole(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def name(self):
        return self.element.get('name')

    @property
    def auth_config_id(self):
        return self.element.get('authConfigId')

    @property
    def properties(self):
        props = {}
        for prop in self.element.findall('property'):
            props[prop.find('key').text] = prop.find('value').text
        return props


class Admins(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    def add_user(self, name):
        user_xml = '<user>{}</user>'.format(name)
        user_element = ET.fromstring(user_xml)
        self.element.append(user_element)
        return self

    def __getitem__(self, index):
        return [u.text for u in self.element.findall('user')][index]


class Roles(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def role(self):
        return [Role(r) for r in self.element.findall('role')]

    @property
    def plugin_role(self):
        return [PluginRole(r) for r in self.element.findall('pluginRole')]

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def ensure_role(self, name, users):
        users_xml = ''.join(['<user>{}</user>'.format(user) for user in users])
        role_xml = '<role name="{}"><users>{}</users></role>'.format(name, users_xml)
        role_element = ET.fromstring(role_xml)
        self.element.append(role_element)
        return self

    def ensure_plugin_role(self, name, auth_config_id, properties={}):
        properties_xml = ''.join(['<property><key>{0}</key><value>{1}</value></property>'.format(k, v) for k,v in
                                properties.items()])
        plugin_role_xml = '<pluginRole name="{0}" authConfigId="{1}">{2}</pluginRole>'.format(name, auth_config_id,
                                                                                              properties_xml)
        plugin_role_element = ET.fromstring(plugin_role_xml)
        self.element.append(plugin_role_element)
        return self

    # deprecated, since this only returns "Role" and now we can have both "Role" and "PluginRole"
    def __getitem__(self, index):
        if not isinstance(index, int):
            raise Exception("Roles index must be an integer, got {}".format(type(index)))
        return self.role[index]

    def __len__(self):
        return len(self.role)


class AuthConfig(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def properties(self):
        props = {}
        for prop in self.element.findall('property'):
            props[prop.find('key').text] = prop.find('value').text
        return props

    @property
    def auth_config_id(self):
        return self.element.get('id')
    
    @property
    def plugin_id(self):
        return self.element.get('pluginId')

    def __eq__(self, other):
        return self.auth_plugin_id == other.auth_plugin_id


class AuthConfigs(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def auth_config(self):
        return [AuthConfig(e) for e in self.element.findall('authConfig')]

    def ensure_auth_config(self, auth_config_id, plugin_id, properties):
        properties_xml = "".join(["<property><key>{}</key><value>{}</value></property>".format(k, v) for k, v in properties.items()])
        auth_config = ET.fromstring('<authConfig id="{}" pluginId="{}">{}</authConfig>'.format(auth_config_id,
                                                                                               plugin_id,
                                                                                               properties_xml))
        self.element.append(auth_config)
        return self

    def ensure_replacement_of_auth_config(self, auth_config_id, plugin_id, properties):
        current_auth_config = [ac for ac in self.auth_config if ac.auth_config_id == auth_config_id]
        if current_auth_config:
            self.element.remove(current_auth_config[0].element)
        return self.ensure_auth_config(auth_config_id, plugin_id, properties)

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise Exception("AuthConfig index must be an integer, got {}".format(type(index)))
        return self.auth_config[index]

    def __len__(self):
        return len(self.auth_config)


class Security(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def roles(self):
        return Roles(self.element.find('roles'))

    @property
    def auth_configs(self):
        return AuthConfigs(self.element.find('authConfigs'))

    @property
    def admins(self):
        return Admins(self.element.find('admins'))

    def ensure_admins(self):
        admins = Ensurance(self.element).ensure_child('admins')
        return Admins(admins.element)

    def ensure_roles(self):
        roles = Ensurance(self.element).ensure_child('roles')
        return Roles(roles.element)

    def ensure_auth_configs(self):
        auth_config = Ensurance(self.element).ensure_child('authConfigs')
        return AuthConfigs(auth_config.element)

    def ensure_replacement_of_auth_configs(self):
        auth_configs = self.ensure_auth_configs()
        auth_configs.make_empty()
        return auth_configs

    def ensure_replacement_of_roles(self):
        roles = self.ensure_roles()
        roles.make_empty()
        return roles

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()
