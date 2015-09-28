#!/usr/bin/env python
import json
import xml.etree.ElementTree as ET
import argparse
import sys
import subprocess
from xml.dom.minidom import parseString
from xml.sax.saxutils import escape

import requests


def prettify(xml_string):
    xml = parseString(xml_string)
    formatted_but_with_blank_lines = xml.toprettyxml()
    non_blank_lines = [l for l in formatted_but_with_blank_lines.split('\n') if len(l.strip()) != 0]
    return '\n'.join(non_blank_lines)


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


class PossiblyMissingElement:
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

    def iterator(self):
        if self.__element is None:
            return []
        else:
            return self.__element

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


def Task(element):
    runif = runif_from(element)
    if element.tag == "exec":
        command_and_args = [element.attrib["command"]] + [e.text for e in element.findall('arg')]
        working_dir = element.attrib.get("workingdir", None)  # TODO not ideal to return "None" for working_dir
        return ExecTask(command_and_args, working_dir, runif)
    if element.tag == "fetchartifact":
        dest = element.attrib.get('dest', None)
        return FetchArtifactTask(element.attrib['pipeline'], element.attrib['stage'], element.attrib['job'], fetch_artifact_src_from(element), dest, runif)
    if element.tag == "rake":
        return RakeTask(element.attrib['target'])
    raise RuntimeError("Don't know task type %s" % element.tag)


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


class RakeTask(AbstractTask):
    def __init__(self, target, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__target = target

    def __repr__(self):
        return 'RakeTask("%s", "%s")' % (self.__target, self._runif)

    def type(self):
        return "rake"

    def target(self):
        return self.__target

    def append_to(self, element):
        new_element = ET.fromstring('<rake target="%s"></rake>' % self.__target)
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

    def append_to(self, element):
        element.append(ET.fromstring('<tab name="%s" path="%s" />' % (self.__name, self.__path)))


class Job(CommonEqualityMixin):
    def __init__(self, element):
        self.__element = element
        self.__thing_with_resources = ThingWithResources(element)

    def __repr__(self):
        return "Job('%s', %s)" % (self.name(), self.tasks())

    def name(self):
        return self.__element.attrib['name']

    def has_timeout(self):
        return 'timeout' in self.__element.attrib

    def timeout(self):
        if not self.has_timeout():
            raise RuntimeError("Job (%s) does not have timeout" % self)
        return self.__element.attrib['timeout']

    def set_timeout(self, timeout):
        self.__element.attrib['timeout'] = timeout
        return self

    def runs_on_all_agents(self):
        return self.__element.attrib.get('runOnAllAgents', 'false') == 'true'

    def set_runs_on_all_agents(self):
        self.__element.attrib['runOnAllAgents'] = 'true'
        return self

    def resources(self):
        return self.__thing_with_resources.resources()

    def ensure_resource(self, resource):
        self.__thing_with_resources.ensure_resource(resource)
        return self

    def artifacts(self):
        artifact_elements = PossiblyMissingElement(self.__element).possibly_missing_child("artifacts").iterator()
        return set([ArtifactFor(e) for e in artifact_elements])

    def ensure_artifacts(self, artifacts):
        artifacts_ensurance = Ensurance(self.__element).ensure_child("artifacts")
        artifacts_to_add = artifacts.difference(self.artifacts())
        for artifact in artifacts_to_add:
            artifact.append_to(artifacts_ensurance)
        return self

    def tabs(self):
        return [Tab(e.attrib['name'], e.attrib['path']) for e in PossiblyMissingElement(self.__element).possibly_missing_child('tabs').findall('tab')]

    def ensure_tab(self, tab):
        tab_ensurance = Ensurance(self.__element).ensure_child("tabs")
        if self.tabs().count(tab) == 0:
            tab.append_to(tab_ensurance)
        return self

    def tasks(self):
        return [Task(e) for e in PossiblyMissingElement(self.__element).possibly_missing_child("tasks").iterator()]

    def add_task(self, task):
        return task.append_to(self.__element)

    def ensure_task(self, task):
        if self.tasks().count(task) == 0:
            return task.append_to(self.__element)
        else:
            return task

    def without_any_tasks(self):
        PossiblyMissingElement(self.__element).possibly_missing_child("tasks").remove_all_children()
        return self

    def environment_variables(self):
        return ThingWithEnvironmentVariables(self.__element).environment_variables()

    def ensure_environment_variables(self, environment_variables):
        ThingWithEnvironmentVariables(self.__element).ensure_environment_variables(environment_variables)
        return self

    def without_any_environment_variables(self):
        ThingWithEnvironmentVariables(self.__element).remove_all()
        return self

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.__element, "environment_variables")
        move_all_to_end(self.__element, "tasks")
        move_all_to_end(self.__element, "tabs")
        move_all_to_end(self.__element, "resources")
        move_all_to_end(self.__element, "artifacts")

    def as_python_commands_applied_to_stage(self):
        result = 'job = stage.ensure_job("%s")' % self.name()

        if self.artifacts():
            if len(self.artifacts()) > 1:
                artifacts_sorted = list(self.artifacts())
                artifacts_sorted.sort(key=lambda artifact: str(artifact))
                result += '.ensure_artifacts(set(%s))' % artifacts_sorted
            else:
                result += '.ensure_artifacts({%s})' % self.artifacts().pop()

        result += ThingWithEnvironmentVariables(self.__element).as_python()

        for resource in self.resources():
            result += '.ensure_resource("%s")' % resource

        for tab in self.tabs():
            result += '.ensure_tab(%s)' % tab

        if self.has_timeout():
            result += '.set_timeout("%s")' % self.timeout()

        if self.runs_on_all_agents():
            result += '.set_runs_on_all_agents()'

        for task in self.tasks():
            # we add instead of ensure because we know it is starting off empty and need to handle duplicate tasks
            result += "\njob.add_task(%s)" % task

        return result


class Stage(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    def __repr__(self):
        return 'Stage(%s)' % self.name()

    def name(self):
        return self.element.attrib['name']

    def jobs(self):
        return [Job(job_element) for job_element in PossiblyMissingElement(self.element).possibly_missing_child('jobs').findall('job')]

    def ensure_job(self, name):
        job_element = Ensurance(self.element).ensure_child("jobs").ensure_child_with_attribute("job", "name", name)
        return Job(job_element._element)

    def environment_variables(self):
        return ThingWithEnvironmentVariables(self.element).environment_variables()

    def ensure_environment_variables(self, environment_variables):
        ThingWithEnvironmentVariables(self.element).ensure_environment_variables(environment_variables)
        return self

    def without_any_environment_variables(self):
        ThingWithEnvironmentVariables(self.element).remove_all()
        return self

    def set_clean_working_dir(self):
        self.element.attrib['cleanWorkingDir'] = "true"
        return self

    def clean_working_dir(self):
        return PossiblyMissingElement(self.element).has_attribute('cleanWorkingDir', "true")

    def has_manual_approval(self):
        return PossiblyMissingElement(self.element).possibly_missing_child("approval").has_attribute("type", "manual")

    def fetch_materials(self):
        return not PossiblyMissingElement(self.element).has_attribute("fetchMaterials", "false")

    def set_fetch_materials(self, value):
        if value:
            PossiblyMissingElement(self.element).remove_attribute("fetchMaterials")
        else:
            Ensurance(self.element).set("fetchMaterials", "false")
        return self

    def set_has_manual_approval(self):
        Ensurance(self.element).ensure_child_with_attribute("approval", "type", "manual")
        return self

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "jobs")

        for job in self.jobs():
            job.reorder_elements_to_please_go()

    def as_python_commands_applied_to(self, receiver):
        result = 'stage = %s.ensure_stage("%s")' % (receiver, self.name())

        result += ThingWithEnvironmentVariables(self.element).as_python()

        if self.clean_working_dir():
            result += '.set_clean_working_dir()'

        if self.has_manual_approval():
            result += '.set_has_manual_approval()'

        if not self.fetch_materials():
            result += '.set_fetch_materials(False)'

        for job in self.jobs():
            result += '\n%s' % job.as_python_commands_applied_to_stage()

        return result


def ignore_patterns_in(element):
    return set([e.attrib['pattern'] for e in PossiblyMissingElement(element).possibly_missing_child("filter").findall("ignore")])


def Materials(element):
    if element.tag == "git":
        branch = element.attrib.get('branch', None)
        material_name = element.attrib.get('materialName', None)
        polling = element.attrib.get('autoUpdate', 'true') == 'true'
        return GitMaterial(element.attrib['url'], branch, material_name, polling, ignore_patterns_in(element))
    if element.tag == "pipeline":
        material_name = element.attrib.get('materialName', None)
        return PipelineMaterial(element.attrib['pipelineName'], element.attrib['stageName'], material_name)
    raise RuntimeError("don't know of material matching " + ET.tostring(element, 'utf-8'))


class GitMaterial(CommonEqualityMixin):
    def __init__(self, url, branch=None, material_name=None, polling=True, ignore_patterns=set()):
        self.__url = url
        self.__branch = branch
        self.__material_name = material_name
        self.__polling = polling
        self.__ignore_patterns = ignore_patterns

    def __repr__(self):
        branch_part = ""
        if not self.is_on_master():
            branch_part = ', branch="%s"' % self.__branch
        material_name_part = ""
        if self.__material_name is not None:
            material_name_part = ', material_name="%s"' % self.__material_name
        polling_part = ''
        if not self.__polling:
            polling_part = ', polling=False'
        ignore_patterns_part = ''
        if self.ignore_patterns():
            ignore_patterns_part = ', ignore_patterns=%s' % self.ignore_patterns()
        return ('GitMaterial("%s"' % self.__url) + branch_part + material_name_part + polling_part + ignore_patterns_part + ')'

    def __has_options(self):
        return (not self.is_on_master()) or (self.__material_name is not None) or (not self.__polling)

    def is_on_master(self):
        return self.__branch is None or self.__branch == 'master'

    def as_python_applied_to_pipeline(self):
        if self.__has_options():
            return 'set_git_material(%s)' % str(self)
        else:
            return 'set_git_url("%s")' % self.__url

    def is_git(self):
        return True

    def url(self):
        return self.__url

    def polling(self):
        return self.__polling

    def branch(self):
        if self.is_on_master():
            return 'master'
        else:
            return self.__branch

    def material_name(self):
        return self.__material_name

    def ignore_patterns(self):
        return self.__ignore_patterns

    def append_to(self, element):
        branch_part = ""
        if not self.is_on_master():
            branch_part = ' branch="%s"' % self.__branch
        material_name_part = ""
        if self.__material_name is not None:
            material_name_part = ' materialName="%s"' % self.__material_name
        polling_part = ''
        if not self.__polling:
            polling_part = ' autoUpdate="false"'
        new_element = ET.fromstring(('<git url="%s"' % self.__url) + branch_part + material_name_part + polling_part + ' />')
        if self.ignore_patterns():
            filter_element = ET.fromstring("<filter/>")
            new_element.append(filter_element)
            sorted_ignore_patterns = list(self.ignore_patterns())
            sorted_ignore_patterns.sort()
            for ignore_pattern in sorted_ignore_patterns:
                filter_element.append(ET.fromstring('<ignore pattern="%s"/>' % ignore_pattern))
        element.append(new_element)


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

    def is_git(self):
        return False

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


class PipelineGroup(CommonEqualityMixin):
    def __init__(self, element, configurator):
        self.element = element
        self.__configurator = configurator

    def __repr__(self):
        return 'PipelineGroup("%s")' % self.name()

    def name(self):
        return self.element.attrib['group']

    def templates(self):
        return self.__configurator.templates()

    def pipelines(self):
        return [Pipeline(e, self) for e in self.element.findall('pipeline')]

    def _matching_pipelines(self, name):
        return [p for p in self.pipelines() if p.name() == name]

    def has_pipeline(self, name):
        return len(self._matching_pipelines(name)) > 0

    def find_pipeline(self, name):
        if self.has_pipeline(name):
            return self._matching_pipelines(name)[0]
        else:
            raise RuntimeError('Cannot find pipeline with name "%s" in %s' % (name, self.pipelines()))

    def ensure_pipeline(self, name):
        pipeline_element = Ensurance(self.element).ensure_child_with_attribute('pipeline', 'name', name)._element
        return Pipeline(pipeline_element, self)

    def ensure_removal_of_pipeline(self, name):
        for pipeline in self._matching_pipelines(name):
            self.element.remove(pipeline.element)
        return self

    def ensure_replacement_of_pipeline(self, name):
        pipeline = self.ensure_pipeline(name)
        pipeline.make_empty()
        return pipeline


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
                raise RuntimeError("Could not post config to Go server (%s):\n%s" % (url, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) (and result was not json):\n%s" % (url, result))


class GoCdConfigurator:
    def __init__(self, host_rest_client):
        self.__host_rest_client = host_rest_client
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

        for pipeline in self.pipelines():
            pipeline.reorder_elements_to_please_go()
        for template in self.templates():
            template.reorder_elements_to_please_go()

    def config(self):
        self.reorder_elements_to_please_go()
        return ET.tostring(self.__xml_root, 'utf-8')

    def pipeline_groups(self):
        return [PipelineGroup(e, self) for e in self.__xml_root.findall('pipelines')]

    def ensure_pipeline_group(self, group_name):
        pipeline_group_element = Ensurance(self.__xml_root).ensure_child_with_attribute("pipelines", "group", group_name)
        return PipelineGroup(pipeline_group_element._element, self)

    def ensure_removal_of_pipeline_group(self, group_name):
        matching = [g for g in self.pipeline_groups() if g.name() == group_name]
        for group in matching:
            self.__xml_root.remove(group.element)
        return self

    def remove_all_pipeline_groups(self):
        for e in self.__xml_root.findall('pipelines'):
            self.__xml_root.remove(e)
        return self

    def agents(self):
        return [Agent(e) for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('agents').findall('agent')]

    def pipelines(self):
        result = []
        groups = self.pipeline_groups()
        for group in groups:
            result.extend(group.pipelines())
        return result

    def templates(self):
        return [Pipeline(e, 'templates') for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('templates').findall('pipeline')]

    def ensure_template(self, template_name):
        pipeline_element = Ensurance(self.__xml_root).ensure_child('templates').ensure_child_with_attribute('pipeline', 'name', template_name)._element
        return Pipeline(pipeline_element, 'templates')

    def ensure_replacement_of_template(self, template_name):
        template = self.ensure_template(template_name)
        template.make_empty()
        return template

    def git_urls(self):
        return [pipeline.git_url() for pipeline in self.pipelines() if pipeline.has_single_git_material()]

    def has_changes(self):
        return prettify(self.__initial_config) != prettify(self.config())

    def save_updated_config(self, save_config_locally=False, dry_run=False):
        config_before = prettify(self.__initial_config)
        config_after = prettify(self.config())
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
            'xmlFile': self.config(),
            'md5': self._initial_md5
        }

        if not dry_run and config_before != config_after:
            self.__host_rest_client.post('/go/admin/restful/configuration/file/POST/xml', data)


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

    matching_pipelines = [p for p in go_server.pipelines() if p.name() == args.pipeline]
    if len(matching_pipelines) != 1:
        raise RuntimeError("Should have found one matching pipeline but found %s" % matching_pipelines)
    pipeline = matching_pipelines[0]

    print go_server.as_python(pipeline)
