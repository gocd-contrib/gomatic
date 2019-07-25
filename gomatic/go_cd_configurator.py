#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from decimal import Decimal
from uuid import uuid4

import requests

from gomatic.gocd.config_repos import ConfigRepos
from gomatic.gocd.security import Security
from gomatic.gocd.elastic import Elastic
from gomatic.gocd.agents import Agent
from gomatic.gocd.pipelines import Pipeline, PipelineGroup
from gomatic.gocd.repositories import Repository
from gomatic.xml_operations import Ensurance, PossiblyMissingElement, move_all_to_end, prettify


class GoCdConfigurator(object):
    def __init__(self, host_rest_client):
        self.__host_rest_client = host_rest_client
        self.__set_initial_config_xml()
        self.__set_server_version()

    def __set_initial_config_xml(self):
        initial_config, self._initial_md5 = self.__current_config_response()
        if isinstance(initial_config, bytes):
            self.__initial_config = initial_config.decode('ascii', errors='xmlcharrefreplace')
        else:
            self.__initial_config = initial_config.encode('ascii', errors='xmlcharrefreplace')
        self.__xml_root = ET.fromstring(self.__initial_config)

    def __set_server_version(self):
        version_url = "/go/api/version"
        response = self.__host_rest_client.get(version_url)
        if response.status_code == 404:
            self.__server_version = '16.5.0' #hardcoding to version before endpoint created
        elif response.status_code == 200:
            data = response.json()
            self.__server_version = data['version']
        else:
            raise Exception("Failed to get {} status {}\n:{}".format(version_url, response.status_code, response.text))


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

    @property
    def server_version(self):
        return self.__server_version

    def __current_config_response(self):
        config_url = "/go/api/admin/config.xml"
        response = self.__host_rest_client.get(config_url)

        if response.status_code != 200:
            raise Exception("Failed to get {} status {}\n:{}".format(config_url, response.status_code, response.text))
        return response.text, response.headers['x-cruise-config-md5']

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.__xml_root, 'pipelines')
        move_all_to_end(self.__xml_root, 'templates')
        move_all_to_end(self.__xml_root, 'environments')
        move_all_to_end(self.__xml_root, 'agents')

        for pipeline_group in self.pipeline_groups:
            pipeline_group.reorder_elements_to_please_go()
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
    def default_job_timeout(self):
        return self.__server_decimal_attribute('jobTimeout')

    @default_job_timeout.setter
    def default_job_timeout(self, timeout_in_minutes):
        self.__server_element_ensurance().set('jobTimeout', str(timeout_in_minutes))

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

    @property
    def config_repos(self):
        return ConfigRepos(self.__xml_root.find('config-repos'), self)

    def ensure_pipeline_group(self, group_name):
        pipeline_group_element = Ensurance(self.__xml_root).ensure_child_with_attribute("pipelines", "group", group_name)
        return PipelineGroup(pipeline_group_element.element, self)

    def ensure_config_repos(self):
        config_repos = Ensurance(self.__xml_root).ensure_child("config-repos")
        return ConfigRepos(config_repos.element, self)

    def ensure_replacement_of_config_repos(self):
        config_repos = self.ensure_config_repos()
        config_repos.make_empty()
        return config_repos

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
    def repositories(self):
        return [Repository(e) for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('repositories').findall('repository')]

    def ensure_repository(self, repository_name):
        ensured_repository_element = Ensurance(self.__xml_root).ensure_child('repositories').ensure_child_with_attribute('repository', 'name', repository_name)
        if not ensured_repository_element.has_attribute('id'):
            ensured_repository_element.set('id', str(uuid4()))
        return Repository(ensured_repository_element.element)

    @property
    def agents(self):
        return [Agent(e) for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('agents').findall('agent')]

    def ensure_removal_of_agent(self, hostname):
        matching = [agent for agent in self.agents if agent.hostname == hostname]
        for agent in matching:
            Ensurance(self.__xml_root).ensure_child('agents').element.remove(agent.element)
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
        pipeline_element = Ensurance(self.__xml_root).ensure_child('templates').ensure_child_with_attribute('pipeline', 'name', template_name).element
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

    def ensure_security(self):
        security_element = self.__server_element_ensurance().ensure_child('security').element
        return Security(security_element)

    def ensure_replacement_of_security(self):
        security = self.ensure_security()
        security.make_empty()
        return security

    @property
    def security(self):
        return Security(self.__server_element_ensurance().element.find('security'))

    def ensure_elastic(self):
        gocd_version_with_elastic_outside_server_tag = 18
        gocd_major_version = int(self.server_version.split('.')[0])
        if gocd_major_version < gocd_version_with_elastic_outside_server_tag:
            elastic_element = self.__server_element_ensurance().ensure_child('elastic').element
        else:
            elastic_element = Ensurance(self.__xml_root).ensure_child('elastic').element
        return Elastic(elastic_element)

    def ensure_replacement_of_elastic(self):
        elastic = self.ensure_elastic()
        elastic.make_empty()
        return elastic

    @property
    def elastic(self):
        gocd_version_with_elastic_outside_server_tag = 18
        gocd_major_version = int(self.server_version.split('.')[0])
        if gocd_major_version < gocd_version_with_elastic_outside_server_tag:
            elastic_element = Elastic(self.__server_element_ensurance().element.find('elastic'))
        else:
            elastic_element = Elastic(Ensurance(self.__xml_root).element.find('elastic'))
        return elastic_element

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
            open('config-before.xml', 'w').write(config_before)
            open('config-after.xml', 'w').write(config_after)

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
            headers = {
                "Confirm": "true",
            }
            if self.__host_rest_client.access_token is not None:
                headers["Authorization"] = "Bearer %s" % self.__host_rest_client.access_token
            self.__host_rest_client.post('/go/api/admin/config.xml', data, headers)
            self.__set_initial_config_xml()


class HostRestClient(object):
    def __init__(self, host, username=None, password=None, ssl=False, verify_ssl=True, access_token=None):
        self.__host = host
        self.__username = username
        self.__password = password
        self.__ssl = ssl
        self.__verify_ssl = verify_ssl
        self.__access_token = access_token

    def __repr__(self):
        return 'HostRestClient("{0}", ssl={1})'.format(self.__host, self.__ssl)

    def __path(self, path):
        http_prefix = 'https://' if self.__ssl else 'http://'
        return '{0}{1}{2}'.format(http_prefix, self.__host, path)

    def __auth(self):
        return (self.__username, self.__password) if self.__username or self.__password else None

    def get(self, path):
        header = {'Accept': 'application/vnd.go.cd.v1+json'}
        if self.__access_token is not None:
            header["Authorization"] = "Bearer %s" % self.__access_token
        result = requests.get(self.__path(path), verify=self.__verify_ssl, headers=header)
        count = 0
        while ((result.status_code == 503) or (result.status_code == 504)) and (count < 5):
            result = requests.get(self.__path(path))
            time.sleep(1)
            count += 1
        return result

    def post(self, path, data, headers=None):
        url = self.__path(path)
        result = requests.post(url, data, auth=self.__auth(), verify=self.__verify_ssl, headers=headers)
        if result.status_code != 200:
            try:
                result_json = json.loads(result.text.replace("\\'", "'"))
                message = result_json.get('result', result.text)
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s]:\n%s" % (url, result.status_code, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s] (and result was not json):\n%s" % (url, result.status_code, result))

    @property
    def access_token(self):
        return self.__access_token


def main(args):
    parser = argparse.ArgumentParser(description='Gomatic is an API for configuring GoCD. '
                                                 'Run python -m gomatic.go_cd_configurator to reverse engineer code to configure an existing pipeline.')
    parser.add_argument('-s', '--server', help='the go server (e.g. "localhost:8153" or "my.gocd.com")')
    parser.add_argument('-p', '--pipeline', help='the name of the pipeline to reverse-engineer the config for')
    parser.add_argument('--username', help='the username for the gocd server', default=None)
    parser.add_argument('--password', help='the password for the gocd server', default=None)
    parser.add_argument('--ssl', help='use HTTPS for the connection to the gocd server', dest='ssl', action='store_true',
                        default=False)
    parser.add_argument('--verify_ssl', help='if set the identity of the ssl certificate will be verified.', dest='verify_ssl',
                        action='store_true',
                        default=False)

    args = parser.parse_args(args)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    go_server = GoCdConfigurator(HostRestClient(args.server, args.username, args.password, ssl=args.ssl, verify_ssl=args.verify_ssl))

    matching_pipelines = [p for p in go_server.pipelines if p.name == args.pipeline]
    if len(matching_pipelines) != 1:
        raise RuntimeError("Should have found one matching pipeline but found %s" % matching_pipelines)
    pipeline = matching_pipelines[0]

    print(go_server.as_python(pipeline))


if __name__ == '__main__':
    main(sys.argv[1:])
