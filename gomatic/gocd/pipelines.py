from functools import cmp_to_key
from xml.etree import ElementTree as ET

from gomatic.gocd.authorization import Authorization
from gomatic.gocd.artifacts import Artifact
from gomatic.gocd.generic import EnvironmentVariableMixin, ResourceMixin
from gomatic.gocd.materials import GitMaterial, Materials, PackageMaterial
from gomatic.gocd.tasks import Task
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance, PossiblyMissingElement, move_all_to_end

DEFAULT_LABEL_TEMPLATE = "0.${COUNT}"  # TODO confirm what default really is. I am pretty sure this is mistaken!


class Tab(CommonEqualityMixin):
    def __init__(self, name, path):
        self.__name = name
        self.__path = path

    def __repr__(self):
        return 'Tab("%s", "%s")' % (self.__name, self.__path)

    def append_to(self, element):
        element.append(ET.fromstring('<tab name="%s" path="%s" />' % (self.__name, self.__path)))


class Job(CommonEqualityMixin, EnvironmentVariableMixin, ResourceMixin):
    def __init__(self, element, parent_stage):
        self.element = element
        self.parent_stage = parent_stage

    def __repr__(self):
        return "Job('%s', %s)" % (self.name, self.tasks)

    @property
    def name(self):
        return self.element.attrib['name']

    @property
    def has_timeout(self):
        return 'timeout' in self.element.attrib

    @property
    def timeout(self):
        if not self.has_timeout:
            raise RuntimeError("Job (%s) does not have timeout" % self)
        return self.element.attrib['timeout']

    @timeout.setter
    def timeout(self, timeout):
        self.element.attrib['timeout'] = timeout

    def set_timeout(self, timeout):
        self.timeout = timeout
        return self

    @property
    def runs_on_all_agents(self):
        return self.element.attrib.get('runOnAllAgents', 'false') == 'true'

    @runs_on_all_agents.setter
    def runs_on_all_agents(self, run_on_all_agents):
        self.element.attrib['runOnAllAgents'] = 'true' if run_on_all_agents else 'false'

    def set_runs_on_all_agents(self, run_on_all_agents=True):
        self.runs_on_all_agents = run_on_all_agents
        return self

    @property
    def has_elastic_profile_id(self):
        return 'elasticProfileId' in self.element.attrib

    @property
    def elastic_profile_id(self):
        if not self.has_elastic_profile_id:
            raise RuntimeError("Job (%s) does not have elasticProfileId" % self)
        return self.element.attrib['elasticProfileId']

    @elastic_profile_id.setter
    def elastic_profile_id(self, elastic_profile_id):
        self.element.attrib['elasticProfileId'] = elastic_profile_id

    def set_elastic_profile_id(self, elastic_profile_id):
        self.elastic_profile_id = elastic_profile_id
        return self

    @property
    def has_run_instance_count(self):
        return 'runInstanceCount' in self.element.attrib        

    @property
    def run_instance_count(self):            
        if not self.has_run_instance_count:
            raise RuntimeError("Job (%s) does not have runInstanceCount" % self)
        return self.element.attrib['runInstanceCount']

    @run_instance_count.setter
    def run_instance_count(self, run_instance_count):
        self.element.attrib['runInstanceCount'] = run_instance_count       

    def set_run_instance_count(self, run_instance_count):
        self.run_instance_count = run_instance_count
        return self         

    def __get_gocd_version_string(self):
        if self.parent_stage is not None \
                and self.parent_stage.parent_pipeline is not None \
                and self.parent_stage.parent_pipeline.parent is not None \
                and type(self.parent_stage.parent_pipeline.parent) is not str \
                and self.parent_stage.parent_pipeline.parent.configurator is not None:
            return self.parent_stage.parent_pipeline.parent.configurator.server_version
        return '17.11.0'

    def is_gocd_18_3_and_above(self):
        version = self.__get_gocd_version_string()
        gocd_major_version = int(version.split('.')[0])
        gocd_minor_version = int(version.split('.')[1])

        return (gocd_major_version == 18 and gocd_minor_version >= 3) or \
               (gocd_major_version >= 19)

    @property
    def artifacts(self):
        artifact_elements = PossiblyMissingElement(self.element).possibly_missing_child("artifacts").iterator
        return set([Artifact.get_artifact_for(e) for e in artifact_elements])

    def ensure_artifacts(self, artifacts):
        if artifacts:
            artifacts_ensurance = Ensurance(self.element).ensure_child("artifacts")
            artifacts_to_add = artifacts.difference(self.artifacts)
            for artifact in artifacts_to_add:
                artifact.append_to(artifacts_ensurance, self.is_gocd_18_3_and_above())
        return self

    @property
    def tabs(self):
        return [Tab(e.attrib['name'], e.attrib['path']) for e in PossiblyMissingElement(self.element).possibly_missing_child('tabs').findall('tab')]

    def ensure_tab(self, tab):
        tab_ensurance = Ensurance(self.element).ensure_child("tabs")
        if self.tabs.count(tab) == 0:
            tab.append_to(tab_ensurance)
        return self

    @property
    def tasks(self):
        return [Task(e) for e in PossiblyMissingElement(self.element).possibly_missing_child("tasks").iterator]

    def add_task(self, task):
        return task.append_to(self.element)

    def ensure_task(self, task):
        if self.tasks.count(task) == 0:
            return task.append_to(self.element)
        else:
            return task

    def without_any_tasks(self):
        PossiblyMissingElement(self.element).possibly_missing_child("tasks").remove_all_children()
        return self

    def reorder_elements_to_please_go(self):
        # see https://github.com/SpringerSBM/gomatic/issues/6
        move_all_to_end(self.element, "environment_variables")
        move_all_to_end(self.element, "tasks")
        move_all_to_end(self.element, "tabs")
        move_all_to_end(self.element, "resources")
        move_all_to_end(self.element, "artifacts")

    def as_python_commands_applied_to_stage(self):
        result = 'job = stage.ensure_job("%s")' % self.name

        if self.artifacts:
            if len(self.artifacts) > 1:
                artifacts_sorted = list(self.artifacts)
                artifacts_sorted.sort(key=lambda artifact: str(artifact))
                result += '.ensure_artifacts(set(%s))' % artifacts_sorted
            else:
                artifact, = self.artifacts
                result += '.ensure_artifacts({%s})' % artifact

        result += self.as_python()

        for resource in self.resources:
            result += '.ensure_resource("%s")' % resource

        for tab in self.tabs:
            result += '.ensure_tab(%s)' % tab

        if self.has_timeout:
            result += '.set_timeout("%s")' % self.timeout

        if self.runs_on_all_agents:
            result += '.set_runs_on_all_agents()'

        if self.has_elastic_profile_id:
            result += '.set_elastic_profile_id("%s")' % self.elastic_profile_id

        for task in self.tasks:
            # we add instead of ensure because we know it is starting off empty and need to handle duplicate tasks
            result += "\njob.add_task(%s)" % task

        return result


class Stage(CommonEqualityMixin, EnvironmentVariableMixin):
    def __init__(self, element, parent_pipeline):
        self.element = element
        self.parent_pipeline = parent_pipeline

    def __repr__(self):
        return 'Stage(%s)' % self.name()

    @property
    def name(self):
        return self.element.attrib['name']

    @property
    def jobs(self):
        job_elements = PossiblyMissingElement(self.element).possibly_missing_child('jobs').findall('job')
        return [Job(job_element, self) for job_element in job_elements]

    def ensure_job(self, name):
        job_element = Ensurance(self.element).ensure_child("jobs").ensure_child_with_attribute("job", "name", name)
        return Job(job_element.element, self)

    def set_clean_working_dir(self):
        self.element.attrib['cleanWorkingDir'] = "true"
        return self

    @property
    def clean_working_dir(self):
        return PossiblyMissingElement(self.element).has_attribute('cleanWorkingDir', "true")

    @property
    def has_manual_approval(self):
        return PossiblyMissingElement(self.element).possibly_missing_child("approval").has_attribute("type", "manual")

    @property
    def fetch_materials(self):
        return not PossiblyMissingElement(self.element).has_attribute("fetchMaterials", "false")

    @property
    def _approval_authorization(self):
        return PossiblyMissingElement(self.element).possibly_missing_child('approval').possibly_missing_child('authorization')

    @property
    def authorized_users(self):
        return [u.text for u in self._approval_authorization.findall('user')]

    @property
    def authorized_roles(self):
        return [r.text for r in self._approval_authorization.findall('role')]

    @fetch_materials.setter
    def fetch_materials(self, value):
        if value:
            PossiblyMissingElement(self.element).remove_attribute("fetchMaterials")
        else:
            Ensurance(self.element).set("fetchMaterials", "false")

    def set_fetch_materials(self, value):
        self.fetch_materials = value
        return self

    def set_has_manual_approval(self, authorize_users=None, authorize_roles=None):
        approval_element = Ensurance(self.element).ensure_child_with_attribute("approval", "type", "manual").element
        if authorize_users or authorize_roles:
            auth_element = Ensurance(approval_element).ensure_child('authorization').element
            PossiblyMissingElement(auth_element).remove_all_children()
            for user in (authorize_users or []):
                auth_element.append(ET.fromstring('<user>{}</user>'.format(user)))
            for role in (authorize_roles or []):
                auth_element.append(ET.fromstring('<role>{}</role>'.format(role)))

        return self

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "jobs")

        for job in self.jobs:
            job.reorder_elements_to_please_go()

    def as_python_commands_applied_to(self, receiver):
        result = 'stage = %s.ensure_stage("%s")' % (receiver, self.name)

        result += self.as_python()

        if self.clean_working_dir:
            result += '.set_clean_working_dir()'

        if self.has_manual_approval:
            result += '.set_has_manual_approval()'

        if not self.fetch_materials:
            result += '.set_fetch_materials(False)'

        for job in self.jobs:
            result += '\n%s' % job.as_python_commands_applied_to_stage()

        return result


class Pipeline(CommonEqualityMixin, EnvironmentVariableMixin):
    def __init__(self, element, parent):
        self.element = element
        self.parent = parent

    @property
    def name(self):
        return self.element.attrib['name']

    def as_python_commands_applied_to_server(self):
        result = (
                     then('ensure_pipeline_group("%s")') +
                     then('ensure_replacement_of_pipeline("%s")')
                 ) % (self.parent.name, self.name)
        return self.__appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(result, 'pipeline')

    def __as_python_commands_to_create_template_applied_to_configurator(self):
        result = 'template = configurator.ensure_replacement_of_template("%s")' % self.name
        return self.__appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(result, 'template')

    def __appended_python_commands_to_create_pipeline_or_template_applied_to_configurator(self, result, receiver):
        if self.is_based_on_template:
            result += then('set_template_name("%s")' % self.__template_name)

        if self.has_timer:
            if self.timer_triggers_only_on_changes:
                result += then('set_timer("%s", only_on_changes=True)' % self.timer)
            else:
                result += then('set_timer("%s")' % self.timer)

        if self.has_label_template:
            if self.label_template == DEFAULT_LABEL_TEMPLATE:
                result += then('set_default_label_template()')
            else:
                result += then('set_label_template("%s")' % self.label_template)

        if self.has_automatic_pipeline_locking:
            result += then('set_automatic_pipeline_locking()')

        if self.has_lock_behavior:
            result += then('set_lock_behavior("%s")' % self.lock_behavior)

        if self.has_single_git_material:
            result += then(self.git_material.as_python_applied_to_pipeline())

        for material in self.materials:
            if not (self.has_single_git_material and material.is_git):
                result += then('ensure_material(%s)' % material)

        result += self.as_python()

        if len(self.parameters) != 0:
            result += then('ensure_parameters(%s)' % self.parameters)

        if self.is_based_on_template:
            result += "\n" + self.template.__as_python_commands_to_create_template_applied_to_configurator()

        for stage in self.stages:
            result += "\n" + stage.as_python_commands_applied_to(receiver)

        return result

    @property
    def is_template(self):
        return self.parent == 'templates'  # but for a pipeline, parent is the pipeline group

    def __eq__(self, other):
        return isinstance(other, self.__class__) and ET.tostring(self.element, 'utf-8') == ET.tostring(other.element, 'utf-8') and self.parent == other.parent

    def __repr__(self):
        return 'Pipeline("%s", "%s")' % (self.name, self.parent)

    def set_automatic_pipeline_locking(self):
        self.element.attrib['isLocked'] = 'true'
        return self

    @property
    def has_automatic_pipeline_locking(self):
        return 'isLocked' in self.element.attrib and self.element.attrib['isLocked'] == 'true'

    @property
    def has_lock_behavior(self):
        return 'lockBehavior' in self.element.attrib

    @property
    def lock_behavior(self):
        if self.has_lock_behavior:
            return self.element.attrib['lockBehavior']
        else:
            raise RuntimeError("Does not have a lock behavior")

    @lock_behavior.setter
    def lock_behavior(self, lock_behavior):
        self.element.attrib['lockBehavior'] = lock_behavior

    def set_lock_behavior(self, lock_behavior):
        self.lock_behavior = lock_behavior
        return self

    @property
    def has_label_template(self):
        return 'labeltemplate' in self.element.attrib

    @property
    def label_template(self):
        if self.has_label_template:
            return self.element.attrib['labeltemplate']
        else:
            raise RuntimeError("Does not have a label template")

    @label_template.setter
    def label_template(self, label_template):
        self.element.attrib['labeltemplate'] = label_template

    def set_label_template(self, label_template):
        self.label_template = label_template
        return self

    def set_default_label_template(self):
        self.label_template = DEFAULT_LABEL_TEMPLATE
        return self

    @property
    def __template_name(self):
        return self.element.attrib.get('template', None)

    @__template_name.setter
    def __template_name(self, template_name):
        self.element.attrib['template'] = template_name

    def set_template_name(self, template_name):
        self.__template_name = template_name
        return self

    @property
    def materials(self):
        elements = PossiblyMissingElement(self.element).possibly_missing_child('materials').iterator
        return [Materials(element) for element in elements]

    def __add_material(self, material):
        material.append_to(Ensurance(self.element).ensure_child('materials'))

    def ensure_material(self, material):
        if self.materials.count(material) == 0:
            self.__add_material(material)
        return self

    @property
    def git_materials(self):
        return [m for m in self.materials if m.is_git]

    @property
    def package_materials(self):
        return [m for m in self.materials if m.is_package]

    @property
    def git_material(self):
        gits = self.git_materials

        if len(gits) == 0:
            raise RuntimeError("pipeline %s has no git" % self)

        if len(gits) > 1:
            raise RuntimeError("pipeline %s has more than one git" % self)

        return gits[0]

    @property
    def has_single_git_material(self):
        return len(self.git_materials) == 1

    @property
    def has_single_package_material(self):
        return len(self.package_materials) == 1

    @property
    def package_material(self):
        packages = self.package_materials

        if len(packages) == 0:
            raise RuntimeError("pipeline %s has no package" % self)

        if len(packages) > 1:
            raise RuntimeError("pipeline %s has more than one package" % self)

        return packages[0]

    def set_package_ref(self, package_ref):
        return self.set_package_material(PackageMaterial(package_ref))

    def set_package_material(self, package_material):
        if len(self.package_materials) > 1:
            raise RuntimeError('Cannot set package ref for pipeline that already has multiple package materials. Use "ensure_material(PackageMaterial(..." instead')
        PossiblyMissingElement(self.element).possibly_missing_child('materials').remove_all_children('package')
        self.__add_material(package_material)
        return self

    @property
    def git_url(self):
        return self.git_material.url

    @property
    def git_branch(self):
        return self.git_material.branch

    def set_git_url(self, git_url):
        return self.set_git_material(GitMaterial(git_url))

    def set_git_material(self, git_material):
        if len(self.git_materials) > 1:
            raise RuntimeError('Cannot set git url for pipeline that already has multiple git materials. Use "ensure_material(GitMaterial(..." instead')
        PossiblyMissingElement(self.element).possibly_missing_child('materials').remove_all_children('git')
        self.__add_material(git_material)
        return self

    @property
    def is_based_on_template(self):
        return self.__template_name is not None

    @property
    def template(self):
        return next(template for template in self.parent.templates if template.name == self.__template_name)

    @property
    def parameters(self):
        param_elements = PossiblyMissingElement(self.element).possibly_missing_child("params").findall("param")
        result = {}
        for param_element in param_elements:
            result[param_element.attrib['name']] = param_element.text
        return result

    def ensure_parameters(self, parameters):
        parameters_ensurance = Ensurance(self.element).ensure_child("params")
        for key, value in parameters.items():
            parameters_ensurance.ensure_child_with_attribute("param", "name", key).set_text(value)
        return self

    def without_any_parameters(self):
        PossiblyMissingElement(self.element).possibly_missing_child("params").remove_all_children()
        return self

    @property
    def stages(self):
        return [Stage(stage_element, self) for stage_element in self.element.findall('stage')]

    def ensure_stage(self, name):
        stage_element = Ensurance(self.element).ensure_child_with_attribute("stage", "name", name)
        return Stage(stage_element.element, self)

    def ensure_removal_of_stage(self, name):
        matching_stages = [s for s in self.stages if s.name == name]
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
        materials = self.materials
        self.remove_materials()
        for material in self.__reordered_materials_to_reduce_thrash(materials):
            self.__add_material(material)

        move_all_to_end(self.element, "params")
        move_all_to_end(self.element, "timer")
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "materials")
        move_all_to_end(self.element, "stage")

        for stage in self.stages:
            stage.reorder_elements_to_please_go()

    @property
    def timer(self):
        if self.has_timer:
            return self.element.find('timer').text
        else:
            raise RuntimeError("%s has no timer" % self)

    @property
    def has_timer(self):
        return self.element.find('timer') is not None

    def set_timer(self, timer, only_on_changes=False):
        if only_on_changes:
            Ensurance(self.element).ensure_child_with_attribute('timer', 'onlyOnChanges', 'true').set_text(timer)
        else:
            Ensurance(self.element).ensure_child('timer').set_text(timer)
        return self

    def remove_timer(self):
        PossiblyMissingElement(self.element).remove_all_children('timer')
        return self

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children().remove_attribute('labeltemplate')

    @property
    def timer_triggers_only_on_changes(self):
        element = self.element.find('timer')
        return "true" == element.attrib.get('onlyOnChanges')

    def remove_materials(self):
        PossiblyMissingElement(self.element).remove_all_children('materials')

    @staticmethod
    def __reordered_materials_to_reduce_thrash(materials):
        def _cmp(a, b):
            return (a > b) - (a < b)

        def cmp_materials(m1, m2):
            if m1.is_git:
                if m2.is_git:
                    return _cmp(m1.url, m2.url)
                else:
                    return -1
            else:
                if m2.is_git:
                    return 1
                else:
                    return _cmp(str(m1), str(m2))

        return sorted(materials, key=cmp_to_key(cmp_materials))


class PipelineGroup(CommonEqualityMixin):
    def __init__(self, element, configurator):
        self.element = element
        self.configurator = configurator

    def __repr__(self):
        return 'PipelineGroup("%s")' % self.name

    @property
    def name(self):
        return self.element.attrib['group']

    @property
    def templates(self):
        return self.configurator.templates

    @property
    def authorization(self):
        return Authorization(self.element.find('authorization'))

    @property
    def pipelines(self):
        return [Pipeline(e, self) for e in self.element.findall('pipeline')]

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.element, 'pipeline')

    def _matching_pipelines(self, name):
        return [p for p in self.pipelines if p.name == name]

    def has_pipeline(self, name):
        return len(self._matching_pipelines(name)) > 0

    def find_pipeline(self, name):
        if self.has_pipeline(name):
            return self._matching_pipelines(name)[0]
        else:
            raise RuntimeError('Cannot find pipeline with name "%s" in %s' % (name, self.pipelines))

    def ensure_authorization(self):
        authorization_element = Ensurance(self.element).ensure_child('authorization').element
        return Authorization(authorization_element)

    def ensure_replacement_of_authorization(self):
        authorization = self.ensure_authorization()
        authorization.make_empty()
        return authorization

    def ensure_pipeline(self, name):
        pipeline_element = Ensurance(self.element).ensure_child_with_attribute('pipeline', 'name', name).element
        return Pipeline(pipeline_element, self)

    def ensure_removal_of_pipeline(self, name):
        for pipeline in self._matching_pipelines(name):
            self.element.remove(pipeline.element)
        return self

    def ensure_replacement_of_pipeline(self, name):
        pipeline = self.ensure_pipeline(name)
        pipeline.make_empty()
        return pipeline


def then(s):
    return '\\\n\t.' + s
