from xml.etree import ElementTree as ET
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import ignore_patterns_in


def Materials(element):
    if element.tag == "git":
        branch = element.attrib.get('branch', None)
        material_name = element.attrib.get('materialName', None)
        polling = element.attrib.get('autoUpdate', 'true') == 'true'
        destination_directory = element.attrib.get('dest', None)
        return GitMaterial(element.attrib['url'],
                           branch=branch,
                           material_name=material_name,
                           polling=polling,
                           ignore_patterns=ignore_patterns_in(element),
                           destination_directory=destination_directory)
    if element.tag == "pipeline":
        material_name = element.attrib.get('materialName', None)
        return PipelineMaterial(element.attrib['pipelineName'], element.attrib['stageName'], material_name)
    raise RuntimeError("don't know of material matching " + ET.tostring(element, 'utf-8'))


class GitMaterial(CommonEqualityMixin):
    def __init__(self, url, branch=None, material_name=None, polling=True, ignore_patterns=set(), destination_directory=None):
        self.__url = url
        self.__branch = branch
        self.__material_name = material_name
        self.__polling = polling
        self.__ignore_patterns = ignore_patterns
        self.__destination_directory = destination_directory

    def __repr__(self):
        branch_part = ""
        if not self.is_on_master:
            branch_part = ', branch="%s"' % self.__branch
        material_name_part = ""
        if self.__material_name is not None:
            material_name_part = ', material_name="%s"' % self.__material_name
        polling_part = ''
        if not self.__polling:
            polling_part = ', polling=False'
        ignore_patterns_part = ''
        if self.ignore_patterns:
            ignore_patterns_part = ', ignore_patterns=%s' % self.ignore_patterns
        destination_directory_part = ''
        if self.destination_directory:
            destination_directory_part = ', destination_directory="%s"' % self.destination_directory
        return ('GitMaterial("%s"' % self.__url) + branch_part + material_name_part + polling_part + ignore_patterns_part + destination_directory_part + ')'

    @property
    def __has_options(self):
        return (not self.is_on_master) or (self.material_name is not None) or (not self.polling) or self.ignore_patterns or self.destination_directory

    @property
    def is_on_master(self):
        return self.__branch is None or self.__branch == 'master'

    def as_python_applied_to_pipeline(self):
        if self.__has_options:
            return 'set_git_material(%s)' % str(self)
        else:
            return 'set_git_url("%s")' % self.__url

    is_git = True

    @property
    def url(self):
        return self.__url

    @property
    def polling(self):
        return self.__polling

    @property
    def branch(self):
        if self.is_on_master:
            return 'master'
        else:
            return self.__branch

    @property
    def material_name(self):
        return self.__material_name

    @property
    def ignore_patterns(self):
        return self.__ignore_patterns

    @property
    def destination_directory(self):
        return self.__destination_directory

    def append_to(self, element):
        branch_part = ""
        if not self.is_on_master:
            branch_part = ' branch="%s"' % self.__branch

        material_name_part = ""
        if self.__material_name is not None:
            material_name_part = ' materialName="%s"' % self.__material_name

        polling_part = ''
        if not self.__polling:
            polling_part = ' autoUpdate="false"'

        destination_directory_part= ''
        if self.__destination_directory:
            destination_directory_part = ' dest="%s"' % self.__destination_directory

        new_element = ET.fromstring(('<git url="%s"' % self.__url) + branch_part + material_name_part + polling_part + destination_directory_part + ' />')

        if self.ignore_patterns:
            filter_element = ET.fromstring("<filter/>")
            new_element.append(filter_element)
            sorted_ignore_patterns = list(self.ignore_patterns)
            sorted_ignore_patterns.sort()
            for ignore_pattern in sorted_ignore_patterns:
                filter_element.append(ET.fromstring('<ignore pattern="%s"/>' % ignore_pattern))

        element.append(new_element)


class PipelineMaterial(CommonEqualityMixin):
    def __init__(self, pipeline_name, stage_name, material_name=None):
        self.__pipeline_name = pipeline_name
        self.__stage_name = stage_name
        self.__material_name = material_name

    def __repr__(self):
        if self.__material_name is None:
            return 'PipelineMaterial("%s", "%s")' % (self.__pipeline_name, self.__stage_name)
        else:
            return 'PipelineMaterial("%s", "%s", "%s")' % (self.__pipeline_name, self.__stage_name, self.__material_name)

    is_git = False

    def append_to(self, element):
        if self.__material_name is None:
            new_element = ET.fromstring('<pipeline pipelineName="%s" stageName="%s" />' % (self.__pipeline_name, self.__stage_name))
        else:
            new_element = ET.fromstring(
                '<pipeline pipelineName="%s" stageName="%s" materialName="%s"/>' % (self.__pipeline_name, self.__stage_name, self.__material_name))

        element.append(new_element)