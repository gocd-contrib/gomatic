from xml.etree import ElementTree as ET
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement, Ensurance


class ThingWithResources(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def resources(self):
        guarded_element = PossiblyMissingElement(self.element)
        return set([e.text for e in guarded_element.possibly_missing_child('resources').findall('resource')])

    def ensure_resource(self, resource):
        if resource not in self.resources:
            Ensurance(self.element).ensure_child('resources')\
                .append(ET.fromstring('<resource>%s</resource>' % resource))


class ThingWithEnvironmentVariables:
    def __init__(self, element):
        self.element = element

    @staticmethod
    def __is_secure(variable_element):
        return 'secure' in variable_element.attrib and variable_element.attrib['secure'] == 'true'

    @staticmethod
    def __is_encrypted(variable_element):
        return variable_element.find('encryptedValue') is not None

    def __environment_variables(self, secure, encrypted=False):
        guarded_element = PossiblyMissingElement(self.element)
        variable_elements = guarded_element.possibly_missing_child("environmentvariables").findall("variable")
        result = {}
        for variable_element in variable_elements:
            if secure == self.__is_secure(variable_element):
                is_encrypted = self.__is_encrypted(variable_element)
                if is_encrypted:
                    value_attribute = "encryptedValue"
                else:
                    value_attribute = "value"
                if encrypted == is_encrypted:
                    result[variable_element.attrib['name']] = variable_element.find(value_attribute).text
        return result

    @property
    def environment_variables(self):
        return self.__environment_variables(secure=False)

    @property
    def encrypted_environment_variables(self):
        return self.__environment_variables(secure=True, encrypted=True)

    @property
    def unencrypted_secure_environment_variables(self):
        return self.__environment_variables(secure=True, encrypted=False)

    def __ensure_environment_variables(self, environment_variables, secure, encrypted):
        ensured_env_variables = Ensurance(self.element).ensure_child("environmentvariables")
        for env_variable in sorted(environment_variables.keys()):
            variable_element = ensured_env_variables.ensure_child_with_attribute("variable", "name", env_variable)
            if secure:
                variable_element.set("secure", "true")
            else:
                PossiblyMissingElement(variable_element.element).remove_attribute("secure")
            if encrypted:
                value_element = variable_element.ensure_child("encryptedValue")
            else:
                value_element = variable_element.ensure_child("value")
            value_element.set_text(environment_variables[env_variable])

    def ensure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=False, encrypted=False)

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=True, encrypted=True)

    def ensure_unencrypted_secure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=True, encrypted=False)

    def remove_all(self):
        PossiblyMissingElement(self.element).possibly_missing_child("environmentvariables").remove_all_children()

    def as_python(self):
        result = ""

        if self.environment_variables:
            result += '.ensure_environment_variables(%s)' % self.environment_variables

        if self.encrypted_environment_variables:
            result += '.ensure_encrypted_environment_variables(%s)' % self.encrypted_environment_variables

        if self.unencrypted_secure_environment_variables:
            result += '.ensure_unencrypted_secure_environment_variables(%s)' % self.unencrypted_secure_environment_variables

        return result

    def remove(self, name):
        env_vars = self.environment_variables
        encrypted_env_vars = self.encrypted_environment_variables
        self.remove_all()
        if name in env_vars:
            del env_vars[name]
        self.ensure_environment_variables(env_vars)
        self.ensure_encrypted_environment_variables(encrypted_env_vars)