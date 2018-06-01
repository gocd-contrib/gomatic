from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin

from artifacts_legacy import ArtifactLegacy

from artifacts_new import ArtifactNew


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
    @classmethod
    def get_artifact_for(cls, element):
        artifacttype = element.attrib.get('type', None)
        if artifacttype is None:
            return ArtifactLegacy.get_artifact_for(element)
        else:
            return ArtifactNew.get_artifact_for(element)

    @classmethod
    def get_build_artifact(cls, src, dest=None, gocd_18_3_and_above=False):
        if gocd_18_3_and_above:
            return ArtifactNew.get_build_artifact(src, dest)
        else:
            return ArtifactLegacy.get_build_artifact(src, dest)

    @classmethod
    def get_test_artifact(cls, src, dest=None, gocd_18_3_and_above=False):
        if gocd_18_3_and_above:
            return ArtifactNew.get_test_artifact(src, dest)
        else:
            return ArtifactLegacy.get_test_artifact(src, dest)


ArtifactFor = Artifact.get_artifact_for
BuildArtifact = Artifact.get_build_artifact
TestArtifact = Artifact.get_test_artifact
