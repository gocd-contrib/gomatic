from xml.dom.minidom import parseString
from xml.etree import ElementTree as ET


class Ensurance(object):
    def __init__(self, element):
        assert element is not None
        self.element = element

    def ensure_child(self, name):
        child = self.element.find(name)
        if child is None:
            result = ET.fromstring('<%s></%s>' % (name, name))
            self.element.append(result)
            return Ensurance(result)
        else:
            return Ensurance(child)

    def ensure_child_with_text(self, name, text):
        matching_elements = [e for e in self.element.findall(name) if e.text == text]
        if len(matching_elements) == 0:
            new_element = ET.fromstring('<%s>%s</%s>' % (name, text, name))
            self.element.append(new_element)
            return Ensurance(new_element)
        else:
            return Ensurance(matching_elements[0])

    def ensure_child_with_attribute(self, name, attribute_name, attribute_value):
        matching_elements = [e for e in self.element.findall(name) if e.attrib[attribute_name] == attribute_value]
        if len(matching_elements) == 0:
            new_element = ET.fromstring('<%s %s="%s"></%s>' % (name, attribute_name, attribute_value, name))
            self.element.append(new_element)
            return Ensurance(new_element)
        else:
            return Ensurance(matching_elements[0])

    def ensure_child_with_descendant(self, name, descendant_name, descendant_value):
        matching_elements = [e for e in self.element.findall(name)]
        if len(matching_elements) == 0:
            new_element = ET.fromstring('<%s><%s>%s</%s></%s>' % (name, descendant_name, descendant_value, descendant_name,  name))
            self.element.append(new_element)
            return Ensurance(new_element)
        else:
            for e in matching_elements:
                value = PossiblyMissingElement(e).possibly_missing_child(descendant_name).text
                if value is not None and value == descendant_value:
                    return Ensurance(e)
            new_element = ET.fromstring('<%s><%s>%s</%s></%s>' % (name, descendant_name, descendant_value, descendant_name,  name))
            self.element.append(new_element)
            return Ensurance(new_element)

    def set(self, attribute_name, value):
        self.element.set(attribute_name, value)
        return self

    def has_attribute(self, name):
        if self.element is None:
            return False
        else:
            return name in self.element.attrib

    def append(self, element):
        self.element.append(element)
        return element

    def set_text(self, value):
        self.element.text = value


class PossiblyMissingElement(object):
    def __init__(self, element):
        self.__element = element

    def possibly_missing_child(self, name):
        if self.__element is None:
            return PossiblyMissingElement(None)
        else:
            return PossiblyMissingElement(self.__element.find(name))

    def findall(self, name):
        if self.__element is None:
            return []
        else:
            return self.__element.findall(name)

    @property
    def iterator(self):
        if self.__element is None:
            return []
        else:
            return self.__element

    def attribute(self, name):
        return self.__element.attrib[name] if self.__element is not None and name in self.__element.attrib else None

    @property
    def text(self):
        return self.__element.text if self.__element is not None else None

    def has_attribute(self, name, value):
        if self.__element is None:
            return False
        else:
            return name in self.__element.attrib and self.__element.attrib[name] == value

    def remove_all_children(self, tag_name_to_remove=None):
        children = []
        if self.__element is not None:
            for child in self.__element:
                if tag_name_to_remove is None or child.tag == tag_name_to_remove:
                    children.append(child)

        for child in children:
            self.__element.remove(child)

        return self

    def remove_attribute(self, attribute_name):
        if self.__element is not None:
            if attribute_name in self.__element.attrib:
                del self.__element.attrib[attribute_name]

        return self


def move_all_to_end(parent_element, tag):
    elements = parent_element.findall(tag)
    for element in elements:
        parent_element.remove(element)
        parent_element.append(element)


def ignore_patterns_in(element):
    children = PossiblyMissingElement(element).possibly_missing_child("filter").findall("ignore")
    return set([e.attrib['pattern'] for e in children])


def prettify(xml_string):
    xml = parseString(xml_string)
    formatted_but_with_blank_lines = xml.toprettyxml()
    non_blank_lines = [l for l in formatted_but_with_blank_lines.split('\n') if len(l.strip()) != 0]
    return '\n'.join(non_blank_lines)
