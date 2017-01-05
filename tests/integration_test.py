#!/usr/bin/env python
from distutils.version import StrictVersion
from urllib2 import urlopen
import time
import subprocess
import webbrowser
import os
import unittest
import sys

from gomatic import GoCdConfigurator, HostRestClient, GitMaterial, ExecTask
from gomatic.gocd.artifacts import Artifact


def start_go_server(gocd_version, gocd_download_version_string):
    with open('Dockerfile', 'w') as f:
        f.write(open("Dockerfile.tmpl").read().replace('GO-VERSION-REPLACE-ME', gocd_version))

    os.system("./build-and-run-go-server-in-docker %s %s" % (gocd_version, gocd_download_version_string))

    count = 0
    for attempt in range(300):
        try:
            urlopen("http://localhost:8153/go").read()
            return
        except:
            count += 1
            time.sleep(1)
            if count % 10 == 0:
                print "Waiting for Docker-based Go server to start..."

    raise Exception("Failed to connect to gocd. It didn't start up correctly in time")


class populated_go_server(object):
    def __init__(self, gocd_version, gocd_download_version_string):
        self.gocd_version = gocd_version
        self.gocd_download_version_string = gocd_download_version_string

    def __enter__(self):
        try:
            start_go_server(self.gocd_version, self.gocd_download_version_string)

            configurator = GoCdConfigurator(HostRestClient('localhost:8153'))
            pipeline = configurator \
                .ensure_pipeline_group("P.Group") \
                .ensure_replacement_of_pipeline("more-options") \
                .set_timer("0 15 22 * * ?") \
                .set_git_material(GitMaterial("https://github.com/SpringerSBM/gomatic.git", material_name="some-material-name", polling=False)) \
                .ensure_environment_variables({'JAVA_HOME': '/opt/java/jdk-1.7'}) \
                .ensure_parameters({'environment': 'qa'})
            stage = pipeline.ensure_stage("earlyStage")
            job = stage.ensure_job("earlyWorm").ensure_artifacts(
                {Artifact.get_build_artifact("scripts/*", "files"),
                 Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts"),
                 Artifact.get_test_artifact("from", "to")}).set_runs_on_all_agents()
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
    gocd_versions = [
        ('13.1.1-16714','-13.1.1-16714'),
        ('13.2.2-17585','-13.2.2-17585'),
        ('13.3.1-18130','-13.3.1-18130'),
        ('13.4.0-18334','-13.4.0-18334'),
        ('13.4.1-18342','-13.4.1-18342'),
        ('14.1.0-18882','-14.1.0-18882'),
        ('14.2.0-377',  '-14.2.0-377'),
        ('14.3.0-1186', '-14.3.0-1186'),
        ('14.4.0-1356', '-14.4.0-1356'),
        ('15.1.0-1863', '-15.1.0-1863'),
        ('15.2.0-2248', '-15.2.0-2248'),
        # '15.3.0-2771', no longer on download page
        # '15.3.1-2777', no longer on download page
        ('16.1.0-2855', '-16.1.0-2855'),
        ('16.2.1-3027', '-16.2.1-3027'),
        ('16.3.0-3183', '-16.3.0-3183'),
        ('16.4.0-3223', '-16.4.0-3223'),
        ('16.5.0-3305', '-16.5.0-3305'),
        ('16.6.0-3590', '-16.6.0-3590'),
        ('16.7.0-3819', '_16.7.0-3819_all'), # arghhh! from now they have "_all" suffix
        ('16.8.0-3929', '_16.8.0-3929_all'),
        ('16.9.0-4001', '_16.9.0-4001_all'),
        ('16.10.0-4131', '_16.10.0-4131_all'),
        ('16.11.0-4185', '_16.11.0-4185_all')
    ]

    def test_all_versions(self):
        for gocd_version, gocd_download_version_string in self.gocd_versions:
            print 'test_all_versions', "*" * 60, gocd_version
            with populated_go_server(gocd_version, gocd_download_version_string) as configurator:
                self.assertEquals(["P.Group"], [p.name for p in configurator.pipeline_groups])
                self.assertEquals(["more-options"], [p.name for p in configurator.pipeline_groups[0].pipelines])
                pipeline = configurator.pipeline_groups[0].pipelines[0]
                self.assertEquals("0 15 22 * * ?", pipeline.timer)
                self.assertEquals(GitMaterial("https://github.com/SpringerSBM/gomatic.git", material_name="some-material-name", polling=False),
                                  pipeline.git_material)
                self.assertEquals({'JAVA_HOME': '/opt/java/jdk-1.7'}, pipeline.environment_variables)
                self.assertEquals({'environment': 'qa'}, pipeline.parameters)
                self.assertEquals(['earlyStage'], [s.name for s in pipeline.stages])
                self.assertEquals(['earlyWorm'], [j.name for j in pipeline.stages[0].jobs])
                job = pipeline.stages[0].jobs[0]
                self.assertEquals({Artifact.get_build_artifact("scripts/*", "files"), Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts"), Artifact.get_test_artifact("from", "to")},
                                  job.artifacts)
                self.assertEquals(True, job.runs_on_all_agents)
                self.assertEquals([ExecTask(['ls'])], job.tasks)

    def test_can_save_multiple_times_using_same_configurator(self):
        gocd_version, gocd_download_version_string = self.gocd_versions[-1]
        print 'test_can_save_multiple_times_using_same_configurator', "*" * 60, gocd_version
        with populated_go_server(gocd_version, gocd_download_version_string) as configurator:
            pipeline = configurator \
                .ensure_pipeline_group("Test") \
                .ensure_replacement_of_pipeline("new-one")
            pipeline.set_git_material(GitMaterial("https://github.com/SpringerSBM/gomatic.git", polling=False))
            job = pipeline.ensure_stage("build").ensure_job("build")
            job.ensure_task(ExecTask(["ls"]))

            configurator.save_updated_config(save_config_locally=True, dry_run=False)

            pipeline = configurator \
                .ensure_pipeline_group("Test") \
                .ensure_replacement_of_pipeline("new-two")
            pipeline.set_git_material(GitMaterial("https://github.com/SpringerSBM/gomatic.git", polling=False))
            job = pipeline.ensure_stage("build").ensure_job("build")
            job.ensure_task(ExecTask(["ls"]))

            configurator.save_updated_config(save_config_locally=True, dry_run=False)

            self.assertEquals(1, len(configurator.ensure_pipeline_group('Test').find_pipeline('new-one').stages))
            self.assertEquals(1, len(configurator.ensure_pipeline_group('Test').find_pipeline('new-two').stages))


if __name__ == '__main__':
    if not os.path.exists("go-server-%s.deb" % IntegrationTest.gocd_versions[0][0]):
        print "This takes a long time to run first time, because it downloads a Java docker image and GoCD .deb packages from the internet"
    check_docker()

    unittest.main()
