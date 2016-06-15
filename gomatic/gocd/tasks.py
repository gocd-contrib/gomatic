from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from gomatic.gocd.artifacts import fetch_artifact_src_from
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance
from collections import OrderedDict

def Task(element):
    runif = runif_from(element)
    if element.tag == "exec":
        command_and_args = [element.attrib["command"]] + [e.text for e in element.findall('arg')]
        working_dir = element.attrib.get("workingdir", None)  # TODO not ideal to return "None" for working_dir
        return ExecTask(command_and_args, working_dir, runif)
    elif element.tag == "fetchartifact":
        dest = element.attrib.get('dest', None)
        return FetchArtifactTask(element.attrib['pipeline'], element.attrib['stage'], element.attrib['job'], fetch_artifact_src_from(element), dest, runif)
    elif element.tag == "rake":
        return RakeTask(element.attrib['target'])
    elif element.tag == "task":
        plugin_config = element.findall('pluginConfiguration')
        if len(plugin_config):
            if plugin_config[0].attrib['id'] == 'script-executor':
                script = element.findall('configuration/property/value')
                if len(script):
                    return ScriptExecutorTask(script[0].text, runif)
            elif plugin_config[0].attrib['id'] == 'maven':
                args = {'runif': runif}
                args['arguments'] = element.findall(
                    'configuration/property[key="Arguments"]/value')[0].text
                args['profiles'] = element.findall(
                    'configuration/property[key="Profiles"]/value')[0].text
                args['offline'] = element.findall(
                    'configuration/property[key="Offline"]/value')[0].text
                args['quiet'] = element.findall(
                    'configuration/property[key="Quiet"]/value')[0].text
                args['debug'] = element.findall(
                    'configuration/property[key="Debug"]/value')[0].text
                args['batch'] = element.findall(
                    'configuration/property[key="Batch"]/value')[0].text
                # properties = element.findall('configuration/property')
                return MavenTask(**args)
    raise RuntimeError("Don't know task type %s" % element.tag)


class AbstractTask(CommonEqualityMixin):
    def __init__(self, runif):
        self._runif = runif
        valid_values = ['passed', 'failed', 'any']
        if runif not in valid_values:
            raise RuntimeError('Cannot create task with runif="%s" - it must be one of %s' % (runif, valid_values))

    @property
    def runif(self):
        return self._runif


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
        result['type'] = self.type
        result['runif'] = self.runif
        result['pipeline'] = self.pipeline
        result['stage'] = self.stage
        result['job'] = self.job
        result['src_type'] = self.src.as_xml_type_and_value[0]
        result['src_value'] = self.src.as_xml_type_and_value[1]
        result['dest'] = self.dest
        return result

    type = 'fetchartifact'

    @property
    def pipeline(self):
        return self.__pipeline

    @property
    def stage(self):
        return self.__stage

    @property
    def job(self):
        return self.__job

    @property
    def src(self):
        return self.__src

    @property
    def dest(self):
        return self.__dest

    def append_to(self, element):
        src_type, src_value = self.src.as_xml_type_and_value
        if self.__dest is None:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" />' % (self.__pipeline, self.__stage, self.__job, src_type, src_value))
        else:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" dest="%s"/>' % (
                    self.__pipeline, self.__stage, self.__job, src_type, src_value, self.__dest))
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

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

        return ('ExecTask(%s' % self.command_and_args) + working_dir_parameter + runif_parameter + ')'

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type
        result['runif'] = self.runif
        result['command'] = self.command_and_args
        result['working_dir'] = self.working_dir
        return result

    type = 'exec'

    @property
    def command_and_args(self):
        return self.__command_and_args

    @property
    def working_dir(self):
        return self.__working_dir

    def append_to(self, element):
        if self.__working_dir is None:
            new_element = ET.fromstring('<exec command="%s"></exec>' % self.__command_and_args[0])
        else:
            new_element = ET.fromstring('<exec command="%s" workingdir="%s"></exec>' % (self.__command_and_args[0], self.__working_dir))

        for arg in self.__command_and_args[1:]:
            new_element.append(ET.fromstring('<arg>%s</arg>' % escape(arg)))

        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)

class MavenTask(AbstractTask):
    def __init__(self, arguments, profiles='', offline='false', quiet='false',
                 debug='false', batch='false', runif="passed"):
        super(self.__class__, self).__init__(runif)
        self._arguments = arguments
        self._profiles = profiles
        self._offline = offline
        self._quiet = quiet
        self._debug = debug
        self._batch = batch

    def __repr__(self):
        return '''
            MavenTask(runif="%s", arguments="%s", profiles="%s", offline="%s",
                      quiet="%s", debug="%s", batch="%s")
        ''' % (self._runif, self._arguments, self._profiles, self._offline,
               self._quiet, self._debug, self._batch)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type()
        result['runif'] = self.runif
        result['arguments'] = self._arguments
        result['profiles'] = self._profiles
        result['offline'] = self._offline
        result['quiet'] = self._quiet
        result['debug'] = self._debug
        result['batch'] = self._batch
        return result

    def type(self):
        return "maven"

    def append_to(self, element):
        new_element = ET.fromstring('<task></task>')
        plugin_config = ET.fromstring(
            '<pluginConfiguration id="maven" version="1" />')
        config = ET.fromstring('<configuration></configuration>')
        config.append(ET.fromstring(
            '''<property>
                <key>Arguments</key>
                <value>%s</value>
               </property>
            ''' % self._arguments)
        )
        config.append(ET.fromstring(
            '''<property>
                <key>Profiles</key>
                <value>%s</value>
               </property>
            ''' % self._profiles)
        )
        config.append(ET.fromstring(
            '''<property>
                <key>Offline</key>
                <value>%s</value>
               </property>
            ''' % self._offline)
        )
        config.append(ET.fromstring(
            '''<property>
                <key>Quiet</key>
                <value>%s</value>
               </property>
            ''' % self._quiet)
        )
        config.append(ET.fromstring(
            '''<property>
                <key>Debug</key>
                <value>%s</value>
               </property>
            ''' % self._debug)
        )
        config.append(ET.fromstring(
            '''<property>
                <key>Batch</key>
                <value>%s</value>
               </property>
            ''' % self._batch)
        )

        new_element.append(plugin_config)
        new_element.append(config)
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)

class RakeTask(AbstractTask):
    def __init__(self, target, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__target = target

    def __repr__(self):
        return 'RakeTask("%s", "%s")' % (self.__target, self._runif)

    def to_dict(self, ordered=False):
        if ordered:
            result = OrderedDict()
        else:
            result = {}
        result['type'] = self.type
        result['runif'] = self.runif
        result['target'] = self.target
        return result

    type = 'rake'

    @property
    def target(self):
        return self.__target

    def append_to(self, element):
        new_element = ET.fromstring('<rake target="%s"></rake>' % self.__target)
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
        result['type'] = self.type
        result['runif'] = self.runif
        result['script'] = self.script
        return result

    @property
    def type(self):
        return "script"

    @property
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
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)



def runif_from(element):
    runifs = [e.attrib['status'] for e in element.findall("runif")]
    if len(runifs) == 0:
        return 'passed'
    if len(runifs) == 1:
        return runifs[0]
    if len(runifs) == 2 and 'passed' in runifs and 'failed' in runifs:
        return 'any'
    raise RuntimeError("Don't know what multiple runif values (%s) means" % runifs)


