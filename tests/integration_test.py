#!/usr/bin/env python
from __future__ import print_function
import os
import subprocess
import multiprocessing
import itertools
import socket
import sys
import time
import unittest
import webbrowser
from distutils.version import StrictVersion
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

from gomatic import ExecTask, GitMaterial, GoCdConfigurator, HostRestClient
from gomatic.gocd.artifacts import Artifact
from gomatic.gocd.materials import PackageMaterial


def get_free_tcp_port():
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(('', 0))
    addr, port = tcp.getsockname()
    tcp.close()
    return port


def start_go_server(gocd_version, gocd_download_version_string, gocd_port):
    os.system("./build-and-run-go-server-in-docker.sh %s %s %s" % (gocd_version, gocd_download_version_string, gocd_port))

    count = 0
    for attempt in range(300):
        try:
            urlopen("http://localhost:{}/go".format(gocd_port)).read()
            return
        except:
            count += 1
            time.sleep(1)
            if count % 10 == 0:
                print("Waiting for Docker-based Go server to start...")

    raise Exception("Failed to connect to gocd. It didn't start up correctly in time")


class populated_go_server(object):
    def __init__(self, gocd_version, gocd_download_version_string):
        self.gocd_version = gocd_version
        self.gocd_download_version_string = gocd_download_version_string
        self.gocd_port = get_free_tcp_port()

    def __enter__(self):
        try:
            start_go_server(self.gocd_version, self.gocd_download_version_string, self.gocd_port)

            configurator = GoCdConfigurator(HostRestClient('localhost:{}'.format(self.gocd_port)))
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
            return GoCdConfigurator(HostRestClient('localhost:{}'.format(self.gocd_port)))
        except:
            # Swallow exception if __exit__ returns a True value
            if self.__exit__(*sys.exc_info()):
                pass
            else:
                raise

    def __exit__(self, type, value, traceback):
        print("*" * 60, "trying to clean up docker for %s" % self.gocd_version)
        os.system("docker rm -f gocd-test-server-%s" % self.gocd_version)


def fail_with(message):
    print(message)
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
        ('16.3.0-3183',  '-16.3.0-3183'),
        ('16.4.0-3223',  '-16.4.0-3223'),
        ('16.5.0-3305',  '-16.5.0-3305'),
        ('16.6.0-3590',  '-16.6.0-3590'),
        ('16.7.0-3819',  '_16.7.0-3819_all'),
        ('16.8.0-3929',  '_16.8.0-3929_all'),
        ('16.9.0-4001',  '_16.9.0-4001_all'),
        ('16.10.0-4131', '_16.10.0-4131_all'),
        ('16.11.0-4185', '_16.11.0-4185_all'),
        ('16.12.0-4352', '_16.12.0-4352_all'),
        ('17.1.0-4511',  '_17.1.0-4511_all'),
        ('17.2.0-4587',  '_17.2.0-4587_all'),
        ('17.3.0-4704',  '_17.3.0-4704_all'),
        ('17.4.0-4892',  '_17.4.0-4892_all'),
        ('17.5.0-5095',  '_17.5.0-5095_all'),
        ('17.6.0-5142',  '_17.6.0-5142_all'),
        ('17.7.0-5147',  '_17.7.0-5147_all'),
        ('17.8.0-5277',  '_17.8.0-5277_all'),
        ('17.9.0-5368',  '_17.9.0-5368_all'),
        ('17.10.0-5380', '_17.10.0-5380_all'),
        ('17.11.0-5520', '_17.11.0-5520_all'),
        ('17.12.0-5626', '_17.12.0-5626_all'),
        ('18.1.0-5937',  '_18.1.0-5937_all'),
        ('18.2.0-6228',  '_18.2.0-6228_all'),
        ('18.3.0-6540',  '_18.3.0-6540_all'),
        ('18.4.0-6640',  '_18.4.0-6640_all'),
        ('18.5.0-6679',  '_18.5.0-6679_all')
    ]

    def test_all_versions(self):
        processes = []
        for gocd_version, gocd_download_version_string in self.gocd_versions:
            def work(gocd_version, gocd_download_version_string, self):
                print('test_all_versions', "*" * 60, gocd_version)
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

            p = multiprocessing.Process(target=work, args=[gocd_version, gocd_download_version_string, self])
            processes.append(p)

        n = 4 # number of processes to run in parallel
        groups = [processes[i:i+n] for i in range(0, len(processes), n)]
        for group in groups:
            for p in group:
                p.start()
            _ = [p.join() for p in group]



    def ignore_test_can_save_multiple_times_using_same_configurator(self):
        gocd_version, gocd_download_version_string = self.gocd_versions[-1]
        print('test_can_save_multiple_times_using_same_configurator', "*" * 60, gocd_version)
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

    def ignore_test_can_save_pipeline_with_package_ref(self):
        gocd_version, gocd_download_version_string = self.gocd_versions[-1]
        print('test_can_save_pipeline_with_package_ref', "*" * 60, gocd_version)
        with populated_go_server(gocd_version, gocd_download_version_string) as configurator:
            pipeline = configurator \
                    .ensure_pipeline_group("Test") \
                    .ensure_replacement_of_pipeline("new-package")

            repo = configurator.ensure_repository("repo_one")
            repo.ensure_type('yum', '1')
            repo.ensure_property('REPO_URL', 'test/repo')
            package = repo.ensure_package('xxx')
            package.ensure_property('PACKAGE_SPEC' , 'spec.*')

            pipeline.set_package_material(PackageMaterial(package.id))
            job = pipeline.ensure_stage("build").ensure_job("build")
            job.ensure_task(ExecTask(["ls"]))

            configurator.save_updated_config(save_config_locally=True, dry_run=False)
            self.assertEquals(1, len(configurator.ensure_pipeline_group('Test').find_pipeline('new-package').materials))
            self.assertEquals(package.id, configurator.ensure_pipeline_group('Test').find_pipeline('new-package').package_material.ref)

    def ignore_test_can_save_and_read_repositories(self):
        gocd_version, gocd_download_version_string = self.gocd_versions[-1]
        print('test_can_save_and_read_repositories', "*" * 60, gocd_version)
        with populated_go_server(gocd_version, gocd_download_version_string) as configurator:
            repo = configurator.ensure_repository("repo_one")
            repo.ensure_type('yum', '1')
            repo.ensure_property('REPO_URL', 'test/repo')
            repo.ensure_property('REPO_URL', 'test/repo')
            package = repo.ensure_package('xxx')
            package.ensure_property('PACKAGE_SPEC', 'spec.*')

            pipeline = configurator.ensure_pipeline_group('repo-pipeline').ensure_pipeline('pone')
            pipeline.set_package_ref(package.id)
            job = pipeline.ensure_stage("build").ensure_job("build")
            job.ensure_task(ExecTask(["ls"]))

            configurator.save_updated_config(save_config_locally=True, dry_run=False)

            self.assertIsNotNone(configurator.ensure_repository("repo_one"))

if __name__ == '__main__':
    if not os.path.exists("go-server-%s.deb" % IntegrationTest.gocd_versions[0][0]):
        print("This takes a long time to run first time, because it downloads a Java docker image and GoCD .deb packages from the internet")
        check_docker()

    unittest.main()
