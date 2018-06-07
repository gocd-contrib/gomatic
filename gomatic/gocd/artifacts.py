from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin

def fetch_artifact_src_from(element):
    if 'srcfile' in element.attrib:
        return FetchArtifactFile(element.attrib['srcfile'])
    if 'srcdir' in element.attrib:
        return FetchArtifactDir(element.attrib['srcdir'])
    raise RuntimeError("Expected srcfile or srcdir. Do not know what src type to use for " + ET.tostring(element, 'utf-8'))


class FetchArtifactFile(CommonEqualityMixin):
    def __init__(self, src_value):
        self.__src_value = src_value

    def __repr__(self):
        return 'FetchArtifactFile("%s")' % self.__src_value

    @property
    def as_xml_type_and_value(self):
        return "srcfile", self.__src_value


class FetchArtifactDir(CommonEqualityMixin):
    def __init__(self, src_value):
        self.__src_value = src_value

    def __repr__(self):
        return 'FetchArtifactDir("%s")' % self.__src_value

    @property
    def as_xml_type_and_value(self):
        return "srcdir", self.__src_value


class Artifact(CommonEqualityMixin):
    def __init__(self, src, dest=None, artifact_type='build'):
        self._src = src
        self._dest = dest
        self._type = artifact_type

    def __repr__(self):
        if self._dest is None:
            return '%s("%s")' % (self.constructor, self._src)
        else:
            return '%s("%s", "%s")' % (self.constructor, self._src, self._dest)

    @property
    def constructor(self):
        if self._type == "build":
            return "BuildArtifact"
        if self._type == "test":
            return "TestArtifact"
        raise RuntimeError("Unknown artifact type %s" % self._type)

    def append_to(self, element, gocd_18_3_and_above=False):
        if gocd_18_3_and_above:
            self._append_to_gocd_18_3_and_above(element)
        else:
            self._append_to_gocd_18_2_and_below(element)

    def _append_to_gocd_18_3_and_above(self, element):
        if self._dest is None:
            element.append(ET.fromstring('<artifact src="%s" type="%s" />' % (self._src, self._type)))
        else:
            element.append(ET.fromstring('<artifact src="%s" dest="%s" type="%s" />' % (self._src, self._dest, self._type)))

    def _append_to_gocd_18_2_and_below(self, element):
        tag = 'artifact' if self._type == 'build' else 'test'
        if self._dest is None:
            element.append(ET.fromstring('<%s src="%s" />' % (tag, self._src)))
        else:
            element.append(ET.fromstring('<%s src="%s" dest="%s" />' % (tag, self._src, self._dest)))

    @classmethod
    def get_artifact_for(cls, element):
        artifact_type_attribute = element.attrib.get('type', None)
        dest = element.attrib.get('dest', None)
        if artifact_type_attribute is None:
            _type = 'build' if element.tag == 'artifact' else 'test'
            return cls(element.attrib['src'], dest, _type)
        else:
            return cls(element.attrib['src'], dest, artifact_type_attribute)

    @classmethod
    def get_build_artifact(cls, src, dest=None):
        return cls(src, dest, 'build')

    @classmethod
    def get_test_artifact(cls, src, dest=None):
        return cls(src, dest, 'test')


ArtifactFor = Artifact.get_artifact_for
BuildArtifact = Artifact.get_build_artifact
TestArtifact = Artifact.get_test_artifact
