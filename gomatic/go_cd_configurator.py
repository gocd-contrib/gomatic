#!/usr/bin/env python
import json
import xml.etree.ElementTree as ET
import argparse
import sys
import subprocess

import requests

from gomatic.gocd.pipelines import Pipeline, PipelineGroup
from gomatic.gocd.agents import Agent
from gomatic.xml_operations import Ensurance, PossiblyMissingElement, move_all_to_end, prettify


class GoCdConfigurator:
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
    def pipeline_groups(self):
        return [PipelineGroup(e, self) for e in self.__xml_root.findall('pipelines')]

    def ensure_pipeline_group(self, group_name):
        pipeline_group_element = Ensurance(self.__xml_root).ensure_child_with_attribute("pipelines", "group", group_name)
        return PipelineGroup(pipeline_group_element.element, self)

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
        pipeline_element = Ensurance(self.__xml_root).ensure_child('templates').ensure_child_with_attribute('pipeline', 'name', template_name).element
        return Pipeline(pipeline_element, 'templates')

    def ensure_replacement_of_template(self, template_name):
        template = self.ensure_template(template_name)
        template.make_empty()
        return template

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
