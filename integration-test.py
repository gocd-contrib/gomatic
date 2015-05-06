#!/usr/bin/env python
from distutils.version import StrictVersion
from urllib2 import urlopen
import time
import subprocess
import webbrowser
import os
import unittest
import sys

from gomatic import *


def start_go_server(gocd_version):
    with open('Dockerfile', 'w') as f:
        f.write(open("Dockerfile.tmpl").read().replace('GO-VERSION-REPLACE-ME', gocd_version))

    os.system("./build-and-run-go-server-in-docker %s" % gocd_version)

    for attempt in range(120):
        try:
            urlopen("http://localhost:8153").read()
            return
        except:
            time.sleep(1)
            print "Waiting for Docker-based Go server to start..."


class populated_go_server:
    def __init__(self, gocd_version):
        self.gocd_version = gocd_version

    def __enter__(self):
        try:
            start_go_server(self.gocd_version)

            configurator = GoCdConfigurator(HostRestClient('localhost:8153'))
            pipeline = configurator \
                .ensure_pipeline_group("P.Group") \
                .ensure_replacement_of_pipeline("more-options") \
                .set_timer("0 15 22 * * ?") \
                .set_git_material(
                GitMaterial("git@bitbucket.org:springersbm/gomatic.git", material_name="some-material-name",
                            polling=False)) \
                .ensure_environment_variables(
                {'JAVA_HOME': '/opt/java/jdk-1.7'}) \
                .ensure_parameters({'environment': 'qa'})
            stage = pipeline.ensure_stage("earlyStage")
            job = stage.ensure_job("earlyWorm").ensure_artifacts(
                {BuildArtifact("scripts/*", "files"), BuildArtifact("target/universal/myapp*.zip", "artifacts"),
                 TestArtifact("from", "to")}).set_runs_on_all_agents()
            job.add_task(ExecTask(['ls']))

            configurator.save_updated_config(save_config_locally=True)
            return GoCdConfigurator(HostRestClient('localhost:8153'))
        except:
            # Swallow exception if __exit__ returns a True value
            if self.__exit__(*sys.exc_info()):
                pass
            else:
                raise

    def __exit__(self, type, value, traceback):
        print "*" * 60, "trying to clean up docker for %s" % self.gocd_version
        os.system("docker rm -f gocd-test-server-%s" % self.gocd_version)


def fail_with(message):
    print message
    sys.exit(1)


def check_installed(command, desired_version, versionNumberFromVersionOutput, installationInstructions):
    try:
        installed_version = versionNumberFromVersionOutput(subprocess.check_output([command, "--version"]))
        if StrictVersion(desired_version) > StrictVersion(installed_version):
            fail_with("Need %s version %s+. You have %s." % (command, desired_version, installed_version))
    except OSError:
        webbrowser.open_new_tab(installationInstructions)
        fail_with(
            "Need %s version %s+. See installation instructions at %s (opened in browser for your convenience)" % (
                command, desired_version, installationInstructions))


def check_docker():
    uname = os.uname()[0]
    url = 'https://docs.docker.com/'
    if uname == "Linux":
        url = "https://docs.docker.com/installation/ubuntulinux/"
    if uname == "Darwin":
        url = "https://docs.docker.com/installation/mac/"
    check_installed("docker", "1.3.0", lambda o: o.split(" ")[2][:-1], url)


class IntegrationTest(unittest.TestCase):
    def test_all_versions(self):
        for gocd_version in [#'13.1.1-16714',
                             '13.2.2-17585',
                             '13.3.1-18130',
                             '13.4.0-18334',
                             '13.4.1-18342',
                             '14.1.0-18882',
                             '14.2.0-377',
                             '14.3.0-1186',
                             '14.4.0-1356',
                             '15.1.0-1863']:
            print "*" * 60, gocd_version
            with populated_go_server(gocd_version) as configurator:
                self.assertEquals(["P.Group"], [p.name() for p in configurator.pipeline_groups()])
                self.assertEquals(["more-options"], [p.name() for p in configurator.pipeline_groups()[0].pipelines()])
                pipeline = configurator.pipeline_groups()[0].pipelines()[0]
                self.assertEquals("0 15 22 * * ?", pipeline.timer())
                self.assertEquals(
                    GitMaterial("git@bitbucket.org:springersbm/gomatic.git", material_name="some-material-name",
                                polling=False), pipeline.git_material())
                self.assertEquals({'JAVA_HOME': '/opt/java/jdk-1.7'}, pipeline.environment_variables())
                self.assertEquals({'environment': 'qa'}, pipeline.parameters())
                self.assertEquals(['earlyStage'], [s.name() for s in pipeline.stages()])
                self.assertEquals(['earlyWorm'], [j.name() for j in pipeline.stages()[0].jobs()])
                job = pipeline.stages()[0].jobs()[0]
                self.assertEquals(
                    {BuildArtifact("scripts/*", "files"), BuildArtifact("target/universal/myapp*.zip", "artifacts"),
                     TestArtifact("from", "to")}, job.artifacts())
                self.assertEquals(True, job.runs_on_all_agents())
                self.assertEquals([ExecTask(['ls'])], job.tasks())


if __name__ == '__main__':
    if not os.path.exists("go-server-13.2.2-17585.deb"):
        print "This takes a long time to run first time, because it downloads a Java docker image and GoCD .deb packages from the internet"
    check_docker()

    unittest.main()
