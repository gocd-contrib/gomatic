from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance, PossiblyMissingElement

class User(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def username(self):
        return self.element.text


class Role(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def name(self):
        return self.element.text


class InnerAuthorization(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def users(self):
        return [User(e) for e in self.element.findall('user')]

    @property
    def roles(self):
        return [Role(e) for e in self.element.findall('role')]

    def add_user(self, username):
        Ensurance(self.element).ensure_child_with_text('user', username)
        return self

    def add_role(self, role):
        Ensurance(self.element).ensure_child_with_text('role', role)
        return self


class Authorization(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def view(self):
        return InnerAuthorization(self.element.find('view'))

    @property
    def operate(self):
        return InnerAuthorization(self.element.find('operate'))

    @property
    def admins(self):
        return InnerAuthorization(self.element.find('admins'))

    def ensure_view(self):
        view_element = Ensurance(self.element).ensure_child('view').element
        return InnerAuthorization(view_element)

    def ensure_operate(self):
        view_element = Ensurance(self.element).ensure_child('operate').element
        return InnerAuthorization(view_element)

    def ensure_admins(self):
        view_element = Ensurance(self.element).ensure_child('admins').element
        return InnerAuthorization(view_element)

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children()

