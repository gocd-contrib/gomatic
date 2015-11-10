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
    def __init__(self, tag, src, dest=None):
        self.__tag = tag
        self.__src = src
        self.__dest = dest

    def __repr__(self):
        if self.__dest is None:
            return '%s("%s")' % (self.constructor, self.__src)
        else:
            return '%s("%s", "%s")' % (self.constructor, self.__src, self.__dest)

    def append_to(self, element):
        if self.__dest is None:
            element.append(ET.fromstring('<%s src="%s" />' % (self.__tag, self.__src)))
        else:
            element.append(ET.fromstring('<%s src="%s" dest="%s" />' % (self.__tag, self.__src, self.__dest)))

    @property
    def constructor(self):
        if self.__tag == "artifact":
            return "BuildArtifact"
        if self.__tag == "test":
            return "TestArtifact"
        raise RuntimeError("Unknown artifact tag %s" % self.__tag)

    @classmethod
    def get_artifact_for(cls, element):
        dest = element.attrib.get('dest', None)
        return cls(element.tag, element.attrib['src'], dest)

    @classmethod
    def get_build_artifact(cls, src, dest=None):
        return cls('artifact', src, dest)

    @classmethod
    def get_test_artifact(cls, src, dest=None):
        return cls('test', src, dest)


ArtifactFor = Artifact.get_artifact_for
BuildArtifact = Artifact.get_build_artifact
TestArtifact = Artifact.get_test_artifact
