from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance, PossiblyMissingElement


class ResourceMixin(object):
    @property
    def resources(self):
        guarded_element = PossiblyMissingElement(self.element)
        return set([e.text for e in guarded_element.possibly_missing_child('resources').findall('resource')])

    def ensure_resource(self, resource):
        if resource not in self.resources:
            Ensurance(self.element).ensure_child('resources')\
                .append(ET.fromstring('<resource>%s</resource>' % resource))
        return self


class EnvironmentVariableMixin(object):
    """
    Mixin to add to pipelines, stages, and jobs to provide environment variable functionality.
    """
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
                value_element_name = self.__value_element_name(is_encrypted)
                if encrypted == is_encrypted:
                    result[variable_element.attrib['name']] = variable_element.find(value_element_name).text
        return result

    def __ensure_environment_variables(self, environment_variables, secure, encrypted):
        ensured_env_variables = Ensurance(self.element).ensure_child("environmentvariables")
        for env_variable in sorted(environment_variables.keys()):
            variable_element = ensured_env_variables.ensure_child_with_attribute("variable", "name", env_variable)
            if secure:
                variable_element.set("secure", "true")
            else:
                PossiblyMissingElement(variable_element.element).remove_attribute("secure")
            value_element = variable_element.ensure_child(self.__value_element_name(encrypted))
            value_element.set_text(environment_variables[env_variable])

        self.__sort_by_name_attribute(ensured_env_variables.element)

    def __value_element_name(self, encrypted):
        return "encryptedValue" if encrypted else "value"

    def __sort_by_name_attribute(self, env_variables_element):
        environment_variable_elements = env_variables_element.findall('variable')
        PossiblyMissingElement(env_variables_element).remove_all_children("variable")
        for environment_variable_element in sorted(environment_variable_elements, key=lambda e: e.attrib['name']):
            env_variables_element.append(environment_variable_element)

    def _remove(self, name):
        env_vars = self.environment_variables
        encrypted_env_vars = self.encrypted_environment_variables
        self._remove_all()
        if name in env_vars:
            del env_vars[name]
        self.ensure_environment_variables(env_vars)
        self.ensure_encrypted_environment_variables(encrypted_env_vars)

    def _remove_all(self):
        PossiblyMissingElement(self.element).possibly_missing_child("environmentvariables").remove_all_children()

    @property
    def environment_variables(self):
        return self.__environment_variables(secure=False)

    @property
    def encrypted_environment_variables(self):
        return self.__environment_variables(secure=True, encrypted=True)

    @property
    def unencrypted_secure_environment_variables(self):
        return self.__environment_variables(secure=True, encrypted=False)

    def ensure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=False, encrypted=False)
        return self

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=True, encrypted=True)
        return self

    def ensure_unencrypted_secure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, secure=True, encrypted=False)
        return self

    def without_any_environment_variables(self):
        self._remove_all()
        return self

    def remove_environment_variable(self, name):
        self._remove(name)
        return self

    def as_python(self):
        result = ""

        if self.environment_variables:
            result += '.ensure_environment_variables(%s)' % self.environment_variables

        if self.encrypted_environment_variables:
            result += '.ensure_encrypted_environment_variables(%s)' % self.encrypted_environment_variables

        if self.unencrypted_secure_environment_variables:
            result += '.ensure_unencrypted_secure_environment_variables(%s)' % self.unencrypted_secure_environment_variables

        return result
