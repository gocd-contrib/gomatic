import xml.etree.ElementTree as ET

from gomatic.mixins import CommonEqualityMixin


class ConfigRepo(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def git_url(self):
        return self.element.find('git').get('url')

    @property
    def plugin(self):
        return self.element.get('plugin')

    def __repr__(self):
        return 'ConfigRepo(git_url={0}, plugin={1})'.format(self.git_url, self.plugin)

    def __eq__(self, other):
        return self.git_url == other.git_url and self.plugin == other.plugin


class ConfigRepos(CommonEqualityMixin):
    def __init__(self, element, configurator):
        self.element = element
        self.__configurator = configurator

    @property
    def config_repo(self):
        return [ConfigRepo(e) for e in self.element.findall('config-repo')]

    def ensure_config_repo(self, git_url, plugin):
        element = ET.fromstring('<config-repo plugin="{0}"><git url="{1}" /></config-repo>'.format(plugin, git_url))
        config_repo_element = ConfigRepo(element)

        if config_repo_element not in self.config_repo:
            self.element.append(element)
        return config_repo_element

    def ensure_yaml_config_repo(self, git_url):
        return self.ensure_config_repo(git_url, 'yaml.config.plugin')

    def ensure_json_config_repo(self, git_url):
        return self.ensure_config_repo(git_url, 'json.config.plugin')

    def __repr__(self):
        return 'ConfigRepos({})'.format(",".join(self.config_repos))
