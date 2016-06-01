#!/usr/bin/env python
import json
import xml.etree.ElementTree as ET
import argparse
import sys
import subprocess

from xml.dom.minidom import parseString
from xml.sax.saxutils import escape
from collections import OrderedDict

import requests
from decimal import Decimal

from gomatic.gocd.pipelines import Pipeline, PipelineGroup
from gomatic.gocd.agents import Agent
from gomatic.xml_operations import Ensurance, PossiblyMissingElement, move_all_to_end, prettify




class CommonEqualityMixin(object):
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self))

    def __repr__(self):
        keys = self.__dict__.keys()
        keys.sort()
        return "Some %s" % self.__class__ + " Fields[" + (
            ", ".join([str(k) + ":" + str(self.__dict__[k]) for k in keys]) + "]")


class Ensurance:
    def __init__(self, element):
        self._element = element

    def ensure_child(self, name):
        child = self._element.find(name)
        if child is None:
            result = ET.fromstring('<%s></%s>' % (name, name))
            self._element.append(result)
            return Ensurance(result)
        else:
            return Ensurance(child)

    def ensure_child_with_attribute(self, name, attribute_name, attribute_value):
        matching_elements = [e for e in self._element.findall(name) if e.attrib[attribute_name] == attribute_value]
        if len(matching_elements) == 0:
            new_element = ET.fromstring('<%s %s="%s"></%s>' % (name, attribute_name, attribute_value, name))
            self._element.append(new_element)
            return Ensurance(new_element)
        else:
            return Ensurance(matching_elements[0])

    def set(self, attribute_name, value):
        self._element.set(attribute_name, value)
        return self

    def append(self, element):
        self._element.append(element)
        return element

    def set_text(self, value):
        self._element.text = value




class ThingWithResources(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    def resources(self):
        return set([e.text for e in PossiblyMissingElement(self.element).possibly_missing_child('resources').findall('resource')])

    def ensure_resource(self, resource):
        if resource not in self.resources():
            Ensurance(self.element).ensure_child('resources').append(ET.fromstring('<resource>%s</resource>' % resource))


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
        variable_elements = PossiblyMissingElement(self.element).possibly_missing_child("environmentvariables").findall("variable")
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

    def environment_variables(self):
        return self.__environment_variables(False)

    def encrypted_environment_variables(self):
        return self.__environment_variables(True, True)

    def unencrypted_secure_environment_variables(self):
        return self.__environment_variables(True, False)

    def __ensure_environment_variables(self, environment_variables, secure, encrypted=None):
        if encrypted is None:
            encrypted = secure

        environment_variables_ensurance = Ensurance(self.element).ensure_child("environmentvariables")
        for environment_variable_name in sorted(environment_variables.keys()):
            variable_element = environment_variables_ensurance.ensure_child_with_attribute("variable", "name", environment_variable_name)
            if secure:
                variable_element.set("secure", "true")
            else:
                variable_element.set("secure", "false")
            if encrypted:
                value_element = variable_element.ensure_child("encryptedValue")
            else:
                value_element = variable_element.ensure_child("value")
            value_element.set_text(environment_variables[environment_variable_name])

    def ensure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, False)

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, True)

    def ensure_unencrypted_secure_environment_variables(self, environment_variables):
        self.__ensure_environment_variables(environment_variables, True, False)

    def remove_all(self):
        PossiblyMissingElement(self.element).possibly_missing_child("environmentvariables").remove_all_children()

    def as_python(self):
        result = ""
        environment_variables = self.environment_variables()
        if environment_variables:
            result += '.ensure_environment_variables(%s)' % environment_variables
        encrypted_environment_variables = self.encrypted_environment_variables()
        if encrypted_environment_variables:
            result += '.ensure_encrypted_environment_variables(%s)' % encrypted_environment_variables
        unencrypted_secure_environment_variables = self.unencrypted_secure_environment_variables()
        if unencrypted_secure_environment_variables:
            result += '.ensure_unencrypted_secure_environment_variables(%s)' % unencrypted_secure_environment_variables
        return result

    def remove(self, name):
        env_vars = self.environment_variables()
        encrypted_env_vars = self.encrypted_environment_variables()
        self.remove_all()
        if name in env_vars:
            del env_vars[name]
        self.ensure_environment_variables(env_vars)
        self.ensure_encrypted_environment_variables(encrypted_env_vars)


def move_all_to_end(parent_element, tag):
    elements = parent_element.findall(tag)
    for element in elements:
        parent_element.remove(element)
        parent_element.append(element)


def runif_from(element):
    runifs = [e.attrib['status'] for e in element.findall("runif")]
    if len(runifs) == 0:
        return 'passed'
    if len(runifs) == 1:
        return runifs[0]
    if len(runifs) == 2 and 'passed' in runifs and 'failed' in runifs:
        return 'any'
    raise RuntimeError("Don't know what multiple runif values (%s) means" % runifs)





class AbstractTask(CommonEqualityMixin):
    def __init__(self, runif):
        self._runif = runif
        valid_values = ['passed', 'failed', 'any']
        if runif not in valid_values:
            raise RuntimeError('Cannot create task with runif="%s" - it must be one of %s' % (runif, valid_values))

    def runif(self):
        return self._runif


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

    def as_xml_type_and_value(self):
        return "srcfile", self.__src_value


class FetchArtifactDir(CommonEqualityMixin):
    def __init__(self, src_value):
        self.__src_value = src_value

    def __repr__(self):
        return 'FetchArtifactDir("%s")' % self.__src_value

    def as_xml_type_and_value(self):
        return "srcdir", self.__src_value


class FetchArtifactTask(AbstractTask):
    def __init__(self, pipeline, stage, job, src, dest=None, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__pipeline = pipeline
        self.__stage = stage
        self.__job = job
        self.__src = src
        self.__dest = dest

    def __repr__(self):
        dest_parameter = ""
        if self.__dest is not None:
            dest_parameter = ', dest="%s"' % self.__dest

        runif_parameter = ""
        if self._runif != "passed":
            runif_parameter = ', runif="%s"' % self._runif

        return ('FetchArtifactTask("%s", "%s", "%s", %s' % (self.__pipeline, self.__stage, self.__job, self.__src)) + dest_parameter + runif_parameter + ')'

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type()
        result['runif'] = self.runif()
        result['pipeline'] = self.pipeline()
        result['stage'] = self.stage()
        result['job'] = self.job()
        result['src_type'] = self.src().as_xml_type_and_value()[0]
        result['src_value'] = self.src().as_xml_type_and_value()[1]
        result['dest'] = self.dest()
        return result

    def type(self):
        return "fetchartifact"

    def pipeline(self):
        return self.__pipeline

    def stage(self):
        return self.__stage

    def job(self):
        return self.__job

    def src(self):
        return self.__src

    def dest(self):
        return self.__dest

    def append_to(self, element):
        src_type, src_value = self.src().as_xml_type_and_value()
        if self.__dest is None:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" />' % (self.__pipeline, self.__stage, self.__job, src_type, src_value))
        else:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" dest="%s"/>' % (
                    self.__pipeline, self.__stage, self.__job, src_type, src_value, self.__dest))
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif()))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


class ScriptExecutorTask(AbstractTask):
    def __init__(self, script, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self._script = script

    def __repr__(self):
        return 'ScriptExecutorTask(runif="%s", script="%s")' % (self._runif, self._script)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type()
        result['runif'] = self.runif()
        result['script'] = self.script()
        return result

    def type(self):
        return "script"

    def script(self):
        return self._script

    def append_to(self, element):
        new_element = ET.fromstring('<task></task>')
        plugin_config = ET.fromstring(
            '<pluginConfiguration id="script-executor" version="1" />')
        script_xml_str = \
            ''' <configuration>
                      <property>
                        <key>script</key>
                        <value>%s</value>
                      </property>
                    </configuration>''' % escape(self._script)

        try:
            script_config = ET.fromstring(script_xml_str)
        except Exception as e:
            msg = '''
                Could not parse script as XML,
                reason: {0}
                script XML: {1}
            '''.format(e, script_xml_str)
            raise Exception(msg)

        new_element.append(plugin_config)
        new_element.append(script_config)
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif()))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)





class ExecTask(AbstractTask):
    def __init__(self, command_and_args, working_dir=None, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__command_and_args = command_and_args
        self.__working_dir = working_dir

    def __repr__(self):
        working_dir_parameter = ""
        if self.__working_dir is not None:
            working_dir_parameter = ', working_dir="%s"' % self.__working_dir

        runif_parameter = ""
        if self._runif != "passed":
            runif_parameter = ', runif="%s"' % self._runif

        return ('ExecTask(%s' % self.command_and_args()) + working_dir_parameter + runif_parameter + ')'

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type()
        result['runif'] = self.runif()
        result['command'] = self.command_and_args()
        result['working_dir'] = self.working_dir()
        return result

    def type(self):
        return "exec"

    def command_and_args(self):
        return self.__command_and_args

    def working_dir(self):
        return self.__working_dir

    def append_to(self, element):
        if self.__working_dir is None:
            new_element = ET.fromstring('<exec command="%s"></exec>' % self.__command_and_args[0])
        else:
            new_element = ET.fromstring('<exec command="%s" workingdir="%s"></exec>' % (self.__command_and_args[0], self.__working_dir))

        for arg in self.__command_and_args[1:]:
            new_element.append(ET.fromstring('<arg>%s</arg>' % escape(arg)))

        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif()))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)





def ArtifactFor(element):
    dest = element.attrib.get('dest', None)
    return Artifact(element.tag, element.attrib['src'], dest)


def BuildArtifact(src, dest=None):
    return Artifact("artifact", src, dest)


def TestArtifact(src, dest=None):
    return Artifact("test", src, dest)


class Artifact(CommonEqualityMixin):
    def __init__(self, tag, src, dest=None):
        self.__tag = tag
        self.__src = src
        self.__dest = dest

    def __repr__(self):
        if self.__dest is None:
            return '%s("%s")' % (self.constructor(), self.__src)
        else:
            return '%s("%s", "%s")' % (self.constructor(), self.__src, self.__dest)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.__tag
        result['src'] = self.__src
        result['dest'] = self.__dest
        return result

    def append_to(self, element):
        if self.__dest is None:
            element.append(ET.fromstring('<%s src="%s" />' % (self.__tag, self.__src)))
        else:
            element.append(ET.fromstring('<%s src="%s" dest="%s" />' % (self.__tag, self.__src, self.__dest)))

    def constructor(self):
        if self.__tag == "artifact":
            return "BuildArtifact"
        if self.__tag == "test":
            return "TestArtifact"
        raise RuntimeError("Unknown artifact tag %s" % self.__tag)


class Tab(CommonEqualityMixin):
    def __init__(self, name, path):
        self.__name = name
        self.__path = path

    def __repr__(self):
        return 'Tab("%s", "%s")' % (self.__name, self.__path)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['name'] = self.__name
        result['path'] = self.__path
        return result

    def append_to(self, element):
        element.append(ET.fromstring('<tab name="%s" path="%s" />' % (self.__name, self.__path)))



def ignore_patterns_in(element):
    return set([e.attrib['pattern'] for e in PossiblyMissingElement(element).possibly_missing_child("filter").findall("ignore")])


def Materials(element):
    if element.tag == "git":
        branch = element.attrib.get('branch', None)
        material_name = element.attrib.get('materialName', None)
        polling = element.attrib.get('autoUpdate', 'true') == 'true'
        dest = element.attrib.get('dest')
        return GitMaterial(element.attrib['url'], branch, material_name,
                           polling, ignore_patterns_in(element), dest)
    if element.tag == "pipeline":
        material_name = element.attrib.get('materialName', None)
        return PipelineMaterial(element.attrib['pipelineName'], element.attrib['stageName'], material_name)
    raise RuntimeError("don't know of material matching " + ET.tostring(element, 'utf-8'))




class PipelineMaterial(CommonEqualityMixin):
    def __init__(self, pipeline_name, stage_name, material_name=None):
        self.__pipeline_name = pipeline_name
        self.__stage_name = stage_name
        self.__material_name = material_name

    def __repr__(self):
        if self.__material_name is None:
            return 'PipelineMaterial("%s", "%s")' % (self.__pipeline_name, self.__stage_name)
        else:
            return 'PipelineMaterial("%s", "%s", "%s")' % (self.__pipeline_name, self.__stage_name, self.__material_name)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = 'pipeline'
        result['name'] = self.material_name()
        result['pipeline_name'] = self.pipeline_name()
        result['stage_name'] = self.stage_name()
        return result

    def is_git(self):
        return False

    def pipeline_name(self):
        return self.__pipeline_name

    def stage_name(self):
        return self.__stage_name

    def material_name(self):
        return self.__material_name

    def append_to(self, element):
        if self.__material_name is None:
            new_element = ET.fromstring('<pipeline pipelineName="%s" stageName="%s" />' % (self.__pipeline_name, self.__stage_name))
        else:
            new_element = ET.fromstring(
                '<pipeline pipelineName="%s" stageName="%s" materialName="%s"/>' % (self.__pipeline_name, self.__stage_name, self.__material_name))

        element.append(new_element)


def then(s):
    return '\\\n\t.' + s


class Pipeline(CommonEqualityMixin):
    def __init__(self, element, parent):
        self.element = element
        self.parent = parent

    def to_dict(self, group_name, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['name'] = self.name()
        result['group'] = group_name
        if self.has_label_template():
            result['label_template'] = self.label_template()
        result['automatic_pipeline_locking'] = \
            self.has_automatic_pipeline_locking()
        result['cron_timer_spec'] = self.timer() if self.has_timer() else None
        if self.has_timer():
            result['cron_timer_run_only_on_new_material'] = \
                self.timer_triggers_only_on_changes()
        result['materials'] = [m.to_dict(ordered=ordered)
                               for m in self.materials()]
        if self.__template_name():
            result['template'] = self.__template_name()
        result['stages'] = [s.to_dict(ordered=ordered) for s in self.stages()]
        result['environment_variables'] = self.environment_variables()
        result['encrypted_environment_variables'] = \
            self.encrypted_environment_variables()
        result['parameters'] = self.parameters()

        return result

    def name(self):
        return self.element.attrib['name']

    def as_python_commands_applied_to_server(self):
        result = (
                     then('ensure_pipeline_group("%s")') +
                     then('ensure_replacement_of_pipeline("%s")')
                 ) % (self.parent.name(), self.name())
        return self.__appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(result, 'pipeline')

    def __as_python_commands_to_create_template_applied_to_configurator(self):
        result = 'template = configurator.ensure_replacement_of_template("%s")' % self.name()
        return self.__appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(result, 'template')

    def __appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(self, result, receiver):
        if self.is_based_on_template():
            result += then('set_template_name("%s")' % self.__template_name())

        if self.has_timer():
            result += then('set_timer("%s")' % self.timer())

        if self.has_label_template():
            if self.label_template() == DEFAULT_LABEL_TEMPLATE:
                result += then('set_default_label_template()')
            else:
                result += then('set_label_template("%s")' % self.label_template())

        if self.has_automatic_pipeline_locking():
            result += then('set_automatic_pipeline_locking()')

        if self.has_single_git_material():
            result += then(self.git_material().as_python_applied_to_pipeline())

        for material in self.materials():
            if not (self.has_single_git_material() and material.is_git()):
                result += then('ensure_material(%s)' % material)

        result += ThingWithEnvironmentVariables(self.element).as_python()

        if len(self.parameters()) != 0:
            result += then('ensure_parameters(%s)' % self.parameters())

        if self.is_based_on_template():
            result += "\n" + self.template().__as_python_commands_to_create_template_applied_to_configurator()

        for stage in self.stages():
            result += "\n" + stage.as_python_commands_applied_to(receiver)

        return result

    def is_template(self):
        return self.parent == 'templates'  # but for a pipeline, parent is the pipeline group

    def __eq__(self, other):
        return isinstance(other, self.__class__) and ET.tostring(self.element, 'utf-8') == ET.tostring(other.element, 'utf-8') and self.parent == other.parent

    def __repr__(self):
        return 'Pipeline("%s", "%s")' % (self.name(), self.parent)

    def has_label_template(self):
        return 'labeltemplate' in self.element.attrib

    def set_automatic_pipeline_locking(self):
        self.element.attrib['isLocked'] = 'true'
        return self

    def clear_automatic_pipeline_locking(self):
        try:
            del self.element.attrib['isLocked']
        except Exception:
            pass

    def has_automatic_pipeline_locking(self):
        return 'isLocked' in self.element.attrib and self.element.attrib['isLocked'] == 'true'

    def label_template(self):
        if self.has_label_template():
            return self.element.attrib['labeltemplate']
        else:
            raise RuntimeError("Does not have a label template")

    def set_label_template(self, label_template):
        self.element.attrib['labeltemplate'] = label_template
        return self

    def set_default_label_template(self):
        return self.set_label_template(DEFAULT_LABEL_TEMPLATE)

    def set_template_name(self, template_name):
        self.element.attrib['template'] = template_name
        return self

    def materials(self):
        return [Materials(element) for element in PossiblyMissingElement(self.element).possibly_missing_child('materials').iterator()]

    def __add_material(self, material):
        material.append_to(Ensurance(self.element).ensure_child('materials'))

    def ensure_material(self, material):
        if self.materials().count(material) == 0:
            self.__add_material(material)
        return self

    def git_materials(self):
        return [m for m in self.materials() if m.is_git()]

    def git_material(self):
        gits = self.git_materials()

        if len(gits) == 0:
            raise RuntimeError("pipeline %s has no git" % self)

        if len(gits) > 1:
            raise RuntimeError("pipeline %s has more than one git" % self)

        return gits[0]

    def has_single_git_material(self):
        return len(self.git_materials()) == 1

    def git_url(self):
        return self.git_material().url()

    def git_branch(self):
        return self.git_material().branch()

    def set_git_url(self, git_url):
        return self.set_git_material(GitMaterial(git_url))

    def set_git_material(self, git_material):
        if len(self.git_materials()) > 1:
            raise RuntimeError('Cannot set git url for pipeline that already has multiple git materials. Use "ensure_material(GitMaterial(..." instead')
        PossiblyMissingElement(self.element).possibly_missing_child('materials').remove_all_children('git')
        self.__add_material(git_material)
        return self

    def __template_name(self):
        return self.element.attrib.get('template', None)

    def is_based_on_template(self):
        return self.__template_name() is not None

    def template(self):
        return next(template for template in self.parent.templates() if template.name() == self.__template_name())

    def environment_variables(self):
        return ThingWithEnvironmentVariables(self.element).environment_variables()

    def encrypted_environment_variables(self):
        return ThingWithEnvironmentVariables(self.element).encrypted_environment_variables()

    def unencrypted_secure_environment_variables(self):
        return ThingWithEnvironmentVariables(self.element).unencrypted_secure_environment_variables()

    def ensure_environment_variables(self, environment_variables):
        ThingWithEnvironmentVariables(self.element).ensure_environment_variables(environment_variables)
        return self

    def ensure_encrypted_environment_variables(self, environment_variables):
        ThingWithEnvironmentVariables(self.element).ensure_encrypted_environment_variables(environment_variables)
        return self

    def ensure_unencrypted_secure_environment_variables(self, environment_variables):
        ThingWithEnvironmentVariables(self.element).ensure_unencrypted_secure_environment_variables(environment_variables)
        return self

    def without_any_environment_variables(self):
        ThingWithEnvironmentVariables(self.element).remove_all()
        return self

    def remove_environment_variable(self, name):
        ThingWithEnvironmentVariables(self.element).remove(name)
        return self

    def parameters(self):
        param_elements = PossiblyMissingElement(self.element).possibly_missing_child("params").findall("param")
        result = {}
        for param_element in param_elements:
            result[param_element.attrib['name']] = param_element.text
        return result

    def ensure_parameters(self, parameters):
        parameters_ensurance = Ensurance(self.element).ensure_child("params")
        for key, value in parameters.iteritems():
            parameters_ensurance.ensure_child_with_attribute("param", "name", key).set_text(value)
        return self

    def without_any_parameters(self):
        PossiblyMissingElement(self.element).possibly_missing_child("params").remove_all_children()
        return self

    def stages(self):
        return [Stage(stage_element) for stage_element in self.element.findall('stage')]

    def ensure_stage(self, name):
        stage_element = Ensurance(self.element).ensure_child_with_attribute("stage", "name", name)
        return Stage(stage_element._element)

    def ensure_removal_of_stage(self, name):
        matching_stages = [s for s in self.stages() if s.name() == name]
        for matching_stage in matching_stages:
            self.element.remove(matching_stage.element)
        return self

    def ensure_initial_stage(self, name):
        stage = self.ensure_stage(name)
        for stage_element in self.element.findall('stage'):
            if stage_element.attrib['name'] != name:
                self.element.remove(stage_element)
                self.element.append(stage_element)
        return stage

    def reorder_elements_to_please_go(self):
        materials = self.materials()
        self.__remove_materials()
        for material in self.__reordered_materials_to_reduce_thrash(materials):
            self.__add_material(material)

        move_all_to_end(self.element, "params")
        move_all_to_end(self.element, "timer")
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "materials")
        move_all_to_end(self.element, "stage")

        for stage in self.stages():
            stage.reorder_elements_to_please_go()

    def timer(self):
        if self.has_timer():
            return self.element.find('timer').text
        else:
            raise RuntimeError("%s has no timer" % self)

    def has_timer(self):
        return self.element.find('timer') is not None

    def set_timer(self, timer):
        Ensurance(self.element).ensure_child('timer').set_text(timer)
        return self

    def remove_timer(self):
        PossiblyMissingElement(self.element).remove_all_children('timer')
        return self

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children().remove_attribute('labeltemplate')

    def timer_triggers_only_on_changes(self):
        element = self.element.find('timer')
        return "true" == element.attrib.get('onlyOnChanges')

    def set_timer_triggers_only_on_changes(self):
        element = self.element.find('timer')
        element.attrib['onlyOnChanges'] = 'true'

    def __remove_materials(self):
        PossiblyMissingElement(self.element).remove_all_children('materials')

    def __reordered_materials_to_reduce_thrash(self, materials):
        def cmp_materials(m1, m2):
            if m1.is_git():
                if m2.is_git():
                    return cmp(m1.url(), m2.url())
                else:
                    return -1
            else:
                if m2.is_git():
                    return 1
                else:
                    return cmp(str(m1), str(m2))

        return sorted(materials, cmp_materials)


DEFAULT_LABEL_TEMPLATE = "0.${COUNT}"  # TODO confirm what default really is. I am pretty sure this is mistaken!




class Agent:
    def __init__(self, element):
        self.__element = element
        self.__thing_with_resources = ThingWithResources(element)

    def hostname(self):
        return self.__element.attrib['hostname']

    def resources(self):
        return self.__thing_with_resources.resources()

    def ensure_resource(self, resource):
        self.__thing_with_resources.ensure_resource(resource)


class HostRestClient:
    def __init__(self, host):
        self.__host = host if host.startswith('http://') else 'http://%s' % host

    def __repr__(self):
        return 'HostRestClient("%s")' % self.__host

    def __path(self, path):
        return self.__host + path

    def get(self, path):
        return requests.get(self.__path(path))

    def post(self, path, data):
        url = self.__path(path)
        result = requests.post(url, data)
        if result.status_code != 200:
            try:
                result_json = json.loads(result.text.replace("\\'", "'"))
                message = result_json.get('result', result.text)
                raise RuntimeError("Could not post config to Go server (%s):\n%s" % (url, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) (and result was not json):\n%s" % (url, result))


class GoCdConfigurator(object):
    def __init__(self, host_rest_client):
        self.__host_rest_client = host_rest_client
        self.__set_initial_config_xml()

    def __set_initial_config_xml(self):
        self.__initial_config, self._initial_md5 = self.__current_config_response()
        self.__xml_root = ET.fromstring(self.__initial_config)

    def __repr__(self):
        return "GoCdConfigurator(%s)" % self.__host_rest_client

    def as_python(self, pipeline, with_save=True):
        result = "#!/usr/bin/env python\nfrom gomatic import *\n\nconfigurator = " + str(self) + "\n"
        result += "pipeline = configurator"
        result += pipeline.as_python_commands_applied_to_server()
        save_part = ""
        if with_save:
            save_part = "\n\nconfigurator.save_updated_config(save_config_locally=True, dry_run=True)"
        return result + save_part

    @property
    def current_config(self):
        return self.__current_config_response()[0]

    def __current_config_response(self):
        response = self.__host_rest_client.get("/go/admin/restful/configuration/file/GET/xml")
        return response.text, response.headers['x-cruise-config-md5']

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.__xml_root, 'pipelines')
        move_all_to_end(self.__xml_root, 'templates')
        move_all_to_end(self.__xml_root, 'environments')
        move_all_to_end(self.__xml_root, 'agents')

        for pipeline in self.pipelines:
            pipeline.reorder_elements_to_please_go()
        for template in self.templates:
            template.reorder_elements_to_please_go()

    @property
    def config(self):
        self.reorder_elements_to_please_go()
        return ET.tostring(self.__xml_root, 'utf-8')

    @property
    def artifacts_dir(self):
        return self.__possibly_missing_server_element().attribute('artifactsdir')

    @artifacts_dir.setter
    def artifacts_dir(self, artifacts_dir):
        self.__server_element_ensurance().set('artifactsdir', artifacts_dir)

    @property
    def site_url(self):
        return self.__possibly_missing_server_element().attribute('siteUrl')

    @site_url.setter
    def site_url(self, site_url):
        self.__server_element_ensurance().set('siteUrl', site_url)

    @property
    def agent_auto_register_key(self):
        return self.__possibly_missing_server_element().attribute('agentAutoRegisterKey')

    @agent_auto_register_key.setter
    def agent_auto_register_key(self, agent_auto_register_key):
        self.__server_element_ensurance().set('agentAutoRegisterKey', agent_auto_register_key)

    @property
    def purge_start(self):
        return self.__server_decimal_attribute('purgeStart')

    @purge_start.setter
    def purge_start(self, purge_start_decimal):
        assert isinstance(purge_start_decimal, Decimal)
        self.__server_element_ensurance().set('purgeStart', str(purge_start_decimal))

    @property
    def purge_upto(self):
        return self.__server_decimal_attribute('purgeUpto')

    @purge_upto.setter
    def purge_upto(self, purge_upto_decimal):
        assert isinstance(purge_upto_decimal, Decimal)
        self.__server_element_ensurance().set('purgeUpto', str(purge_upto_decimal))

    def __server_decimal_attribute(self, attribute_name):
        attribute = self.__possibly_missing_server_element().attribute(attribute_name)
        return Decimal(attribute) if attribute else None

    def __possibly_missing_server_element(self):
        return PossiblyMissingElement(self.__xml_root).possibly_missing_child('server')

    def __server_element_ensurance(self):
        return Ensurance(self.__xml_root).ensure_child('server')

    @property
    def pipeline_groups(self):
        return [PipelineGroup(e, self) for e in self.__xml_root.findall('pipelines')]

    def ensure_pipeline_group(self, group_name):
        pipeline_group_element = Ensurance(self.__xml_root).ensure_child_with_attribute("pipelines", "group", group_name)
        return PipelineGroup(pipeline_group_element._element, self)

    def ensure_removal_of_pipeline_group(self, group_name):
        matching = [g for g in self.pipeline_groups if g.name == group_name]
        for group in matching:
            self.__xml_root.remove(group.element)
        return self

    def remove_all_pipeline_groups(self):
        for e in self.__xml_root.findall('pipelines'):
            self.__xml_root.remove(e)
        return self

    @property
    def agents(self):
        return [Agent(e) for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('agents').findall('agent')]

    def ensure_removal_of_agent(self, hostname):
        matching = [agent for agent in self.agents if agent.hostname == hostname]
        for agent in matching:
            Ensurance(self.__xml_root).ensure_child('agents').element.remove(agent._element)
        return self

    @property
    def pipelines(self):
        result = []
        groups = self.pipeline_groups
        for group in groups:
            result.extend(group.pipelines)
        return result

    @property
    def templates(self):
        return [Pipeline(e, 'templates') for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('templates').findall('pipeline')]

    def ensure_template(self, template_name):
        pipeline_element = Ensurance(self.__xml_root).ensure_child('templates').ensure_child_with_attribute('pipeline', 'name', template_name)._element
        return Pipeline(pipeline_element, 'templates')

    def ensure_replacement_of_template(self, template_name):
        template = self.ensure_template(template_name)
        template.make_empty()
        return template

    def ensure_removal_of_template(self, template_name):
        matching = [template for template in self.templates if template.name == template_name]
        root = Ensurance(self.__xml_root)
        templates_element = root.ensure_child('templates').element
        for template in matching:
            templates_element.remove(template.element)
        if len(self.templates) == 0:
            root.element.remove(templates_element)
        return self

    @property
    def git_urls(self):
        return [pipeline.git_url for pipeline in self.pipelines if pipeline.has_single_git_material]

    @property
    def has_changes(self):
        return prettify(self.__initial_config) != prettify(self.config)

    def save_updated_config(self, save_config_locally=False, dry_run=False):
        config_before = prettify(self.__initial_config)
        config_after = prettify(self.config)
        if save_config_locally:
            open('config-before.xml', 'w').write(config_before.encode('utf-8'))
            open('config-after.xml', 'w').write(config_after.encode('utf-8'))

            def has_kdiff3():
                try:
                    return subprocess.call(["kdiff3", "-version"]) == 0
                except:
                    return False

            if dry_run and config_before != config_after and has_kdiff3():
                subprocess.call(["kdiff3", "config-before.xml", "config-after.xml"])

        data = {
            'xmlFile': self.config,
            'md5': self._initial_md5
        }

        if not dry_run and config_before != config_after:
            self.__host_rest_client.post('/go/admin/restful/configuration/file/POST/xml', data)
            self.__set_initial_config_xml()


class HostRestClient(object):
    def __init__(self, host):
        self.__host = host

    def __repr__(self):
        return 'HostRestClient("%s")' % self.__host

    def __path(self, path):
        return ('http://%s' % self.__host) + path

    def get(self, path):
        return requests.get(self.__path(path))

    def post(self, path, data):
        url = self.__path(path)
        result = requests.post(url, data)
        if result.status_code != 200:
            try:
                result_json = json.loads(result.text.replace("\\'", "'"))
                message = result_json.get('result', result.text)
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s]:\n%s" % (url, result.status_code, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s] (and result was not json):\n%s" % (url, result.status_code, result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gomatic is an API for configuring GoCD. '
                                                 'Run python -m gomatic.go_cd_configurator to reverse engineer code to configure an existing pipeline.')
    parser.add_argument('-s', '--server', help='the go server (e.g. "localhost:8153" or "my.gocd.com")')
    parser.add_argument('-p', '--pipeline', help='the name of the pipeline to reverse-engineer the config for')

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    go_server = GoCdConfigurator(HostRestClient(args.server))

    matching_pipelines = [p for p in go_server.pipelines if p.name == args.pipeline]
    if len(matching_pipelines) != 1:
        raise RuntimeError("Should have found one matching pipeline but found %s" % matching_pipelines)
    pipeline = matching_pipelines[0]

    print(go_server.as_python(pipeline))
