import xml.etree.ElementTree as ET
import uuid

from distutils.version import LooseVersion

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement


ATTR_NAME_CHANGE_VERSION = LooseVersion("17.9.0")
ID_INTRODUCED_VERSION = LooseVersion("17.8.0")


def has_new_attr_name(version):
    return LooseVersion(version) >= ATTR_NAME_CHANGE_VERSION


def has_id(version):
    return LooseVersion(version) >= ID_INTRODUCED_VERSION


class ConfigRepo(CommonEqualityMixin):
    valid_cvs = ['git', 'svn', 'hg', 'p4', 'tfs']

    def __init__(self, element, version):
        self.element = element
        self.version = version

    @property
    def url(self):
        return self.element.find(self.cvs).get('url')

    @property
    def branch(self):
        return self.element.find(self.cvs).get('branch')

    @property
    def cvs(self):
        for c in self.element.getchildren():
            if c.tag in ConfigRepo.valid_cvs:
                return c.tag

    @property
    def configuration(self):
        config = {}
        for p in self.element.find('configuration').getchildren():
            config[p.find('key').text] = p.find('value').text
        return config

    @property
    def plugin(self):
        key = 'pluginId' if has_new_attr_name(self.version) else 'plugin'
        return self.element.get(key)

    @property
    def repo_id(self):
        if has_id(self.version):
            return self.element.get('id')
        else:
            return None

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def __repr__(self):
        return 'ConfigRepo(url={0}, plugin={1}, cvs={2}, configuration={3})'.format(
            self.url, self.plugin, self.cvs, self.configuration)

    def __eq__(self, other):
        return self.url == other.url and self.plugin == other.plugin


class ConfigRepos(CommonEqualityMixin):

    def __init__(self, element, configurator):
        self.element = element
        self.__configurator = configurator

    @property
    def config_repo(self):
        return [ConfigRepo(e, self.__configurator.server_version) for e in self.element.findall('config-repo')]

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

    def ensure_config_repo(self, url, plugin, cvs='git', configuration=None, repo_id=None, branch=None):
        configuration_xml_string = ""
        if configuration:
            configuration_xml_string = '<configuration>{}</configuration>'.format(
                "".join("<property><key>{0}</key><value>{1}</value></property>".format(k, v) for k, v in
                        configuration.items()))
        branch_entry = ''
        if branch:
            branch_entry = ' branch="{}"'.format(branch)
        if has_id(self.__configurator.server_version):
            if not repo_id:
                repo_id = str(uuid.uuid4())
            attr_name = 'pluginId' if has_new_attr_name(self.__configurator.server_version) else 'plugin'
            element = ET.fromstring('<config-repo {5}="{0}" id="{4}"><{2} url="{1}"{6} />{3}</config-repo>'.format(
                plugin, url, cvs, configuration_xml_string, repo_id, attr_name, branch_entry))
        else:
            element = ET.fromstring('<config-repo plugin="{0}"><{2} url="{1}"{4} />{3}</config-repo>'.format(
                plugin, url, cvs, configuration_xml_string, branch_entry))

        config_repo_element = ConfigRepo(element, self.__configurator.server_version)

        if config_repo_element not in self.config_repo:
            self.element.append(element)
        return config_repo_element

    def ensure_replacement_of_config_repo(self, url, plugin, cvs='git', configuration=None):
        for repo in self.config_repo:
            if repo.url == url:
                self.element.remove(repo.element)

        self.ensure_config_repo(url, plugin, cvs, configuration)

    def ensure_yaml_config_repo(self, git_url):
        return self.ensure_config_repo(git_url, 'yaml.config.plugin', cvs='git', configuration=None)

    def ensure_json_config_repo(self, git_url):
        return self.ensure_config_repo(git_url, 'json.config.plugin', cvs='git', configuration=None)

    def __repr__(self):
        return 'ConfigRepos({})'.format(",".join(self.config_repo))
