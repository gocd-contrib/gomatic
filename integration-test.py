#!/usr/bin/env python

from urllib2 import urlopen
import time
import os
import unittest

from gomatic import *


def start_go_server(gocd_version):
    with open('Dockerfile', 'w') as f:
        f.write(open("Dockerfile.tmpl").read().replace('GO-VERSION-REPLACE-ME', gocd_version))

    os.system("./build-and-run-go-server-in-docker %s" % gocd_version)

    def wait_for_go_server_to_start():
        for attempt in range(120):
            try:
                urlopen("http://localhost:8153").read()
                return
            except:
                time.sleep(1)
                print "Waiting for Docker-based Go server to start..."

    wait_for_go_server_to_start()


class IntegrationTest(unittest.TestCase):
    def test_thing(self):
        start_go_server('13.4.0-18334')  # Newest: 14.4.0-1356

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

        configurator = GoCdConfigurator(HostRestClient('localhost:8153'))

        self.assertEquals(["P.Group"], [p.name() for p in configurator.pipeline_groups()])


if __name__ == '__main__':
    unittest.main()
