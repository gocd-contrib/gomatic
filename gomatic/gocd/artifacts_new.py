from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin

class ArtifactNew(CommonEqualityMixin):
    def __init__(self, src, dest=None, artifacttype='build'):
        self.__src = src
        self.__dest = dest
        self.__type = artifacttype

    def __repr__(self):
        if self.__dest is None:
            return '%s("%s", "%s")' % (self.constructor, self.__src, self.__type)
        else:
            return '%s("%s", "%s", "%s")' % (self.constructor, self.__src, self.__dest, self.__type)

    def append_to(self, element):
        if self.__dest is None:
            element.append(ET.fromstring('<artifact src="%s" type="%s" />' % (self.__src, self.__type)))
        else:
            element.append(ET.fromstring('<artifact src="%s" dest="%s" type="%s" />' % (self.__src, self.__dest, self.__type)))

    @property
    def constructor(self):
        if self.__type == "build":
            return "BuildArtifact"
        if self.__type == "test":
            return "TestArtifact"
        raise RuntimeError("Unknown artifact type %s" % self.__type)

    @classmethod
    def get_artifact_for(cls, element):
        dest = element.attrib.get('dest', None)
        artifacttype = element.attrib.get('type', 'build')
        return cls(element.attrib['src'], dest, artifacttype)

    @classmethod
    def get_build_artifact(cls, src, dest=None):
        return cls(src, dest, 'build')

    @classmethod
    def get_test_artifact(cls, src, dest=None):
        return cls(src, dest, 'test')
