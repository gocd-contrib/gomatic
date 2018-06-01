from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin

class ArtifactLegacy(CommonEqualityMixin):
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
