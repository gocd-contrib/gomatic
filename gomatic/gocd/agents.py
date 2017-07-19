from gomatic.gocd.generic import ResourceMixin
from gomatic.mixins import CommonEqualityMixin


class Agent(CommonEqualityMixin, ResourceMixin):
    def __init__(self, element):
        self.element = element

    @property
    def hostname(self):
        return self.element.attrib['hostname']
