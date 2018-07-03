#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import xml.etree.ElementTree as ET
import os
from decimal import Decimal
from xml.dom.minidom import parseString

from gomatic import (
    ExecTask,
    FetchArtifactDir,
    FetchArtifactFile,
    FetchArtifactTask,
    GitMaterial,
    GoCdConfigurator,
    Pipeline,
    PipelineMaterial,
    RakeTask,
    Security,
    Tab
)
from gomatic.fake import FakeHostRestClient, config, empty_config, empty_config_xml, load_file
from gomatic.gocd.artifacts import Artifact, ArtifactFor, BuildArtifact, TestArtifact
from gomatic.gocd.pipelines import DEFAULT_LABEL_TEMPLATE
from gomatic.xml_operations import prettify


def find_with_matching_name(things, name):
    return [thing for thing in things if thing.name == name]


def standard_pipeline_group():
    return GoCdConfigurator(config('config-with-typical-pipeline')).ensure_pipeline_group('P.Group')


def typical_pipeline():
    return standard_pipeline_group().find_pipeline('typical')


def more_options_pipeline():
    return GoCdConfigurator(config('config-with-more-options-pipeline')).ensure_pipeline_group('P.Group').find_pipeline('more-options')

def more_options_pipeline_with_artifacts_type():
    return GoCdConfigurator(config('config-with-more-options-pipeline-including-artifacts-type')).ensure_pipeline_group('P.Group').find_pipeline('more-options')

def empty_pipeline():
    return GoCdConfigurator(empty_config()).ensure_pipeline_group("pg").ensure_pipeline("pl").set_git_url("gurl")


def empty_stage():
    return empty_pipeline().ensure_stage("deploy-to-dev")


class TestAgents(unittest.TestCase):
    def _agents_from_config(self):
        return GoCdConfigurator(config('config-with-just-agents')).agents

    def test_could_have_no_agents(self):
        agents = GoCdConfigurator(empty_config()).agents
        self.assertEqual(0, len(agents))

    def test_agents_have_resources(self):
        agents = self._agents_from_config()
        self.assertEqual(2, len(agents))
        self.assertEqual({'a-resource', 'b-resource'}, agents[0].resources)

    def test_agents_have_names(self):
        agents = self._agents_from_config()
        self.assertEqual('go-agent-1', agents[0].hostname)
        self.assertEqual('go-agent-2', agents[1].hostname)

    def test_agent_could_have_no_resources(self):
        agents = self._agents_from_config()
        self.assertEqual(0, len(agents[1].resources))

    def test_can_add_resource_to_agent_with_no_resources(self):
        agent = self._agents_from_config()[1]
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        self.assertEqual(1, len(agent.resources))

    def test_can_add_resource_to_agent(self):
        agent = self._agents_from_config()[0]
        self.assertEqual(2, len(agent.resources))
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        self.assertEqual(3, len(agent.resources))


class TestJobs(unittest.TestCase):
    def test_jobs_have_resources(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        resources = job.resources
        self.assertEqual(1, len(resources))
        self.assertEqual({'a-resource'}, resources)

    def test_job_has_nice_tostring(self):
        job = typical_pipeline().stages[0].jobs[0]
        self.assertEqual("Job('compile', [ExecTask(['make', 'options', 'source code'])])", str(job))

    def test_jobs_can_have_timeout(self):
        job = typical_pipeline().ensure_stage("deploy").ensure_job("upload")
        self.assertEqual(True, job.has_timeout)
        self.assertEqual('20', job.timeout)

    def test_can_set_timeout(self):
        job = empty_stage().ensure_job("j")
        j = job.set_timeout("42")
        self.assertEqual(j, job)
        self.assertEqual(True, job.has_timeout)
        self.assertEqual('42', job.timeout)

    def test_jobs_do_not_have_to_have_timeout(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        self.assertEqual(False, job.has_timeout)
        try:
            timeout = job.timeout
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_jobs_can_run_on_all_agents(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        self.assertEqual(True, job.runs_on_all_agents)

    def test_jobs_do_not_have_to_run_on_all_agents(self):
        job = typical_pipeline().ensure_stage("build").ensure_job("compile")
        self.assertEqual(False, job.runs_on_all_agents)

    def test_jobs_can_be_made_to_run_on_all_agents(self):
        job = typical_pipeline().ensure_stage("build").ensure_job("compile")
        j = job.set_runs_on_all_agents()
        self.assertEqual(j, job)
        self.assertEqual(True, job.runs_on_all_agents)

    def test_jobs_can_be_made_to_not_run_on_all_agents(self):
        job = typical_pipeline().ensure_stage("build").ensure_job("compile")
        j = job.set_runs_on_all_agents(False)
        self.assertEqual(j, job)
        self.assertEqual(False, job.runs_on_all_agents)

    def test_jobs_can_have_elastic_profile_id(self):
        job = typical_pipeline().ensure_stage("package").ensure_job("docker")
        self.assertEqual(True, job.has_elastic_profile_id)
        self.assertEqual('docker.unit-test', job.elastic_profile_id)

    def test_can_set_elastic_profile_id(self):
        job = empty_stage().ensure_job("j")
        j = job.set_elastic_profile_id("docker.unit-test")
        self.assertEqual(j, job)
        self.assertEqual(True, job.has_elastic_profile_id)
        self.assertEqual('docker.unit-test', job.elastic_profile_id)

    def test_jobs_do_not_have_to_have_elastic_profile_id(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        self.assertEqual(False, job.has_elastic_profile_id)
        try:
            elastic_profile_id = job.elastic_profile_id
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_jobs_can_have_run_instance_count(self):
        job = typical_pipeline().ensure_stage("package").ensure_job("docker")
        self.assertEqual(True, job.has_run_instance_count)
        self.assertEqual("2", job.run_instance_count)            

    def test_can_set_run_instance_count(self):
        job = empty_stage().ensure_job("j")
        j = job.set_run_instance_count(2)
        self.assertEqual(j, job)
        self.assertEqual(True, job.has_run_instance_count)
        self.assertEqual(2, job.run_instance_count)

    def test_jobs_do_not_have_to_have_run_instance_count(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        self.assertEqual(False, job.has_run_instance_count)
        try:
            run_instance_count = job.run_instance_count
            self.fail("should have thrown exception")
        except RuntimeError:
            pass        

    def test_can_ensure_job_has_resource(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        j = job.ensure_resource('moo')
        self.assertEqual(j, job)
        self.assertEqual(2, len(job.resources))
        self.assertEqual({'a-resource', 'moo'}, job.resources)

    def test_jobs_have_artifacts(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        artifacts = job.artifacts
        self.assertEqual({
                              Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts"),
                              Artifact.get_build_artifact("scripts/*", "files"),
                              Artifact.get_test_artifact("from", "to")},
                          artifacts)

    def test_jobs_have_artifacts_with_type(self):
        job = more_options_pipeline_with_artifacts_type().ensure_stage("earlyStage").ensure_job("earlyWorm")
        artifacts = job.artifacts
        self.assertEqual({
                              Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts"),
                              Artifact.get_build_artifact("scripts/*", "files"),
                              Artifact.get_test_artifact("from", "to")},
                          artifacts)

    def test_job_that_has_no_artifacts_has_no_artifacts_element_to_reduce_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())
        job = go_cd_configurator.ensure_pipeline_group("g").ensure_pipeline("p").ensure_stage("s").ensure_job("j")
        job.ensure_artifacts(set())
        self.assertEqual(set(), job.artifacts)

        xml = parseString(go_cd_configurator.config)
        self.assertEqual(0, len(xml.getElementsByTagName('artifacts')))

    def test_artifacts_might_have_no_dest(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("rake-job")
        artifacts = job.artifacts
        self.assertEqual(1, len(artifacts))
        self.assertEqual({Artifact.get_build_artifact("things/*")}, artifacts)

    def test_artifacts_with_type_might_have_no_dest(self):
        job = more_options_pipeline_with_artifacts_type().ensure_stage("s1").ensure_job("rake-job")
        artifacts = job.artifacts
        self.assertEqual(1, len(artifacts))
        self.assertEqual({Artifact.get_build_artifact("things/*")}, artifacts)

    def test_can_add_build_artifacts_to_job(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        job_with_artifacts = job.ensure_artifacts({
            Artifact.get_build_artifact("a1", "artifacts"),
            Artifact.get_build_artifact("a2", "others")})
        self.assertEqual(job, job_with_artifacts)
        artifacts = job.artifacts
        self.assertEqual(5, len(artifacts))
        self.assertTrue({Artifact.get_build_artifact("a1", "artifacts"), Artifact.get_build_artifact("a2", "others")}.issubset(artifacts))

    def test_can_add_test_artifacts_to_job(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        job_with_artifacts = job.ensure_artifacts({
            Artifact.get_test_artifact("a1"),
            Artifact.get_test_artifact("a2")})
        self.assertEqual(job, job_with_artifacts)
        artifacts = job.artifacts
        self.assertEqual(5, len(artifacts))
        self.assertTrue({Artifact.get_test_artifact("a1"), Artifact.get_test_artifact("a2")}.issubset(artifacts))

    def test_can_ensure_artifacts(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")

        job.ensure_artifacts({
            Artifact.get_test_artifact("from", "to"),
            Artifact.get_build_artifact("target/universal/myapp*.zip", "somewhereElse"),
            Artifact.get_test_artifact("another", "with dest"),
            Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts")})
        self.assertEqual({
                              Artifact.get_build_artifact("target/universal/myapp*.zip", "artifacts"),
                              Artifact.get_build_artifact("scripts/*", "files"),
                              Artifact.get_test_artifact("from", "to"),
                              Artifact.get_build_artifact("target/universal/myapp*.zip", "somewhereElse"),
                              Artifact.get_test_artifact("another", "with dest")
                          },
                          job.artifacts)

    def test_jobs_have_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").jobs[2]
        tasks = job.tasks
        self.assertEqual(4, len(tasks))
        self.assertEqual('rake', tasks[0].type)
        self.assertEqual('sometarget', tasks[0].target)
        self.assertEqual('passed', tasks[0].runif)

        self.assertEqual('fetchartifact', tasks[1].type)
        self.assertEqual('more-options', tasks[1].pipeline)
        self.assertEqual('earlyStage', tasks[1].stage)
        self.assertEqual('earlyWorm', tasks[1].job)
        self.assertEqual(FetchArtifactDir('sourceDir'), tasks[1].src)
        self.assertEqual('destDir', tasks[1].dest)
        self.assertEqual('passed', tasks[1].runif)

    def test_runif_defaults_to_passed(self):
        pipeline = typical_pipeline()
        tasks = pipeline.ensure_stage("build").ensure_job("compile").tasks
        self.assertEqual("passed", tasks[0].runif)

    def test_jobs_can_have_rake_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").jobs[0]
        tasks = job.tasks
        self.assertEqual(1, len(tasks))
        self.assertEqual('rake', tasks[0].type)
        self.assertEqual("boo", tasks[0].target)

    def test_can_ensure_rake_task(self):
        job = more_options_pipeline().ensure_stage("s1").jobs[0]
        job.ensure_task(RakeTask("boo"))
        self.assertEqual(1, len(job.tasks))

    def test_can_add_rake_task(self):
        job = more_options_pipeline().ensure_stage("s1").jobs[0]
        job.ensure_task(RakeTask("another"))
        self.assertEqual(2, len(job.tasks))
        self.assertEqual("another", job.tasks[1].target)

    def test_can_add_exec_task_with_runif(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir', "failed"))
        self.assertEqual(2, len(job.tasks))
        task = job.tasks[1]
        self.assertEqual(task, added_task)
        self.assertEqual(['ls', '-la'], task.command_and_args)
        self.assertEqual('some/dir', task.working_dir)
        self.assertEqual('failed', task.runif)

    def test_can_add_exec_task(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir'))
        self.assertEqual(2, len(job.tasks))
        task = job.tasks[1]
        self.assertEqual(task, added_task)
        self.assertEqual(['ls', '-la'], task.command_and_args)
        self.assertEqual('some/dir', task.working_dir)

    def test_can_ensure_exec_task(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        t1 = job.ensure_task(ExecTask(['ls', '-la'], 'some/dir'))
        t2 = job.ensure_task(ExecTask(['make', 'options', 'source code']))
        job.ensure_task(ExecTask(['ls', '-la'], 'some/otherdir'))
        job.ensure_task(ExecTask(['ls', '-la'], 'some/dir'))
        self.assertEqual(3, len(job.tasks))

        self.assertEqual(t2, job.tasks[0])
        self.assertEqual(['make', 'options', 'source code'], (job.tasks[0]).command_and_args)

        self.assertEqual(t1, job.tasks[1])
        self.assertEqual(['ls', '-la'], (job.tasks[1]).command_and_args)
        self.assertEqual('some/dir', (job.tasks[1]).working_dir)

        self.assertEqual(['ls', '-la'], (job.tasks[2]).command_and_args)
        self.assertEqual('some/otherdir', (job.tasks[2]).working_dir)

    def test_exec_task_args_are_unescaped_as_appropriate(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        task = job.tasks[1]
        self.assertEqual(["bash", "-c",
                           'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"'],
                          task.command_and_args)

    def test_exec_task_args_are_escaped_as_appropriate(self):
        job = empty_stage().ensure_job("j")
        task = job.add_task(ExecTask(["bash", "-c",
                                      'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"']))
        self.assertEqual(["bash", "-c",
                           'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"'],
                          task.command_and_args)

    def test_can_have_no_tasks(self):
        self.assertEqual(0, len(empty_stage().ensure_job("empty_job").tasks))

    def test_can_add_fetch_artifact_task_to_job(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        added_task = job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('d'), runif="any"))
        self.assertEqual(2, len(job.tasks))
        task = job.tasks[1]
        self.assertEqual(added_task, task)
        self.assertEqual('p', task.pipeline)
        self.assertEqual('s', task.stage)
        self.assertEqual('j', task.job)
        self.assertEqual(FetchArtifactDir('d'), task.src)
        self.assertEqual('any', task.runif)

    def test_fetch_artifact_task_can_have_src_file_rather_than_src_dir(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("variety-of-tasks")
        tasks = job.tasks

        self.assertEqual(4, len(tasks))
        self.assertEqual('more-options', tasks[1].pipeline)
        self.assertEqual('earlyStage', tasks[1].stage)
        self.assertEqual('earlyWorm', tasks[1].job)
        self.assertEqual(FetchArtifactFile('someFile'), tasks[2].src)
        self.assertEqual('passed', tasks[1].runif)
        self.assertEqual(['true'], tasks[3].command_and_args)

    def test_fetch_artifact_task_can_have_dest(self):
        pipeline = more_options_pipeline()
        job = pipeline.ensure_stage("s1").ensure_job("variety-of-tasks")
        tasks = job.tasks
        self.assertEqual(FetchArtifactTask("more-options",
                                            "earlyStage",
                                            "earlyWorm",
                                            FetchArtifactDir("sourceDir"),
                                            dest="destDir"),
                          tasks[1])

    def test_can_ensure_fetch_artifact_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("variety-of-tasks")
        job.ensure_task(FetchArtifactTask("more-options", "middleStage", "middleJob", FetchArtifactFile("someFile")))
        first_added_task = job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        self.assertEqual(5, len(job.tasks))

        self.assertEqual(first_added_task, job.tasks[4])

        self.assertEqual('p', (job.tasks[4]).pipeline)
        self.assertEqual('s', (job.tasks[4]).stage)
        self.assertEqual('j', (job.tasks[4]).job)
        self.assertEqual(FetchArtifactDir('dir'), (job.tasks[4]).src)
        self.assertEqual('passed', (job.tasks[4]).runif)

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactFile('f')))
        self.assertEqual(FetchArtifactFile('f'), (job.tasks[5]).src)

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir'), dest="somedest"))
        self.assertEqual("somedest", (job.tasks[6]).dest)

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir'), runif="failed"))
        self.assertEqual('failed', (job.tasks[7]).runif)

    def test_tasks_run_if_defaults_to_passed(self):
        job = empty_stage().ensure_job("j")
        job.add_task(ExecTask(['ls', '-la'], 'some/dir'))
        job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        job.add_task(RakeTask('x'))
        self.assertEqual('passed', (job.tasks[0]).runif)
        self.assertEqual('passed', (job.tasks[1]).runif)
        self.assertEqual('passed', (job.tasks[2]).runif)

    def test_tasks_run_if_variants(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("run-if-variants")
        tasks = job.tasks
        self.assertEqual('t-passed', tasks[0].command_and_args[0])
        self.assertEqual('passed', tasks[0].runif)

        self.assertEqual('t-none', tasks[1].command_and_args[0])
        self.assertEqual('passed', tasks[1].runif)

        self.assertEqual('t-failed', tasks[2].command_and_args[0])
        self.assertEqual('failed', tasks[2].runif)

        self.assertEqual('t-any', tasks[3].command_and_args[0])
        self.assertEqual('any', tasks[3].runif)

        self.assertEqual('t-both', tasks[4].command_and_args[0])
        self.assertEqual('any', tasks[4].runif)

    def test_cannot_set_runif_to_random_things(self):
        try:
            ExecTask(['x'], runif='whatever')
            self.fail("should have thrown exception")
        except RuntimeError as e:
            self.assertTrue(str(e).count("whatever") > 0)

    def test_can_set_runif_to_particular_values(self):
        self.assertEqual('passed', ExecTask(['x'], runif='passed').runif)
        self.assertEqual('failed', ExecTask(['x'], runif='failed').runif)
        self.assertEqual('any', ExecTask(['x'], runif='any').runif)

    def test_tasks_dest_defaults_to_none(self):  # TODO: maybe None could be avoided
        job = empty_stage().ensure_job("j")
        job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        self.assertEqual(None, (job.tasks[0]).dest)

    def test_can_add_exec_task_to_empty_job(self):
        job = empty_stage().ensure_job("j")
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir', "any"))
        self.assertEqual(1, len(job.tasks))
        task = job.tasks[0]
        self.assertEqual(task, added_task)
        self.assertEqual(['ls', '-la'], task.command_and_args)
        self.assertEqual('some/dir', task.working_dir)
        self.assertEqual('any', task.runif)

    def test_can_remove_all_tasks(self):
        stages = typical_pipeline().stages
        job = stages[0].jobs[0]
        self.assertEqual(1, len(job.tasks))
        j = job.without_any_tasks()
        self.assertEqual(j, job)
        self.assertEqual(0, len(job.tasks))

    def test_can_have_encrypted_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-encrypted-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        job = pipeline.ensure_stage('defaultStage').ensure_job('defaultJob')
        self.assertEqual({"MY_JOB_PASSWORD": "yq5qqPrrD9/j=="}, job.encrypted_environment_variables)

    def test_can_set_encrypted_environment_variables(self):
        job = empty_stage().ensure_job("j")
        job.ensure_encrypted_environment_variables({'one': 'blah=='})
        self.assertEqual({"one": "blah=="}, job.encrypted_environment_variables)

    def test_can_add_unencrypted_secure_environment_variables_to_stage(self):
        job = empty_stage().ensure_job("j")
        job.ensure_unencrypted_secure_environment_variables({"new": "one", "again": "two"})
        self.assertEqual({"new": "one", "again": "two"}, job.unencrypted_secure_environment_variables)

    def test_can_add_environment_variables(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.ensure_environment_variables({"new": "one"})
        self.assertEqual(j, job)
        self.assertEqual({"CF_COLOR": "false", "new": "one"}, job.environment_variables)

    def test_environment_variables_get_added_in_sorted_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        job = go_cd_configurator\
            .ensure_pipeline_group('P.Group')\
            .ensure_pipeline('P.Name') \
            .ensure_stage("build") \
            .ensure_job("compile")

        job.ensure_environment_variables({"ant": "a", "badger": "a", "zebra": "a"})

        xml = parseString(go_cd_configurator.config)
        names = [e.getAttribute('name') for e in xml.getElementsByTagName('variable')]
        self.assertEqual([u'ant', u'badger', u'zebra'], names)

    def test_can_remove_all_environment_variables(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.without_any_environment_variables()
        self.assertEqual(j, job)
        self.assertEqual({}, job.environment_variables)

    def test_job_can_haveTabs(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        self.assertEqual([Tab("Time_Taken", "artifacts/test-run-times.html")], job.tabs)

    def test_can_addTab(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.ensure_tab(Tab("n", "p"))
        self.assertEqual(j, job)
        self.assertEqual([Tab("Time_Taken", "artifacts/test-run-times.html"), Tab("n", "p")], job.tabs)

    def test_can_ensure_tab(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        job.ensure_tab(Tab("Time_Taken", "artifacts/test-run-times.html"))
        self.assertEqual([Tab("Time_Taken", "artifacts/test-run-times.html")], job.tabs)


class TestStages(unittest.TestCase):
    def test_pipelines_have_stages(self):
        self.assertEqual(3, len(typical_pipeline().stages))

    def test_stages_have_names(self):
        stages = typical_pipeline().stages
        self.assertEqual('build', stages[0].name)
        self.assertEqual('package', stages[1].name)
        self.assertEqual('deploy', stages[2].name)

    def test_stages_can_have_manual_approval(self):
        self.assertEqual(False, typical_pipeline().stages[0].has_manual_approval)
        self.assertEqual(False, typical_pipeline().stages[1].has_manual_approval)
        self.assertEqual(True, typical_pipeline().stages[2].has_manual_approval)

    def test_can_set_manual_approval(self):
        stage = typical_pipeline().stages[0]
        s = stage.set_has_manual_approval()
        self.assertEqual(s, stage)
        self.assertEqual(True, stage.has_manual_approval)

    def test_manual_approval_can_have_authorization(self):
        stage = typical_pipeline().stages[0]
        s = stage.set_has_manual_approval(authorize_users=['user1'], authorize_roles=['role1'])

        self.assertEqual(True, stage.has_manual_approval)
        self.assertEqual(['user1'], stage.authorized_users)
        self.assertEqual(['role1'], stage.authorized_roles)

    def test_stages_have_fetch_materials_flag(self):
        stage = typical_pipeline().ensure_stage("build")
        self.assertEqual(True, stage.fetch_materials)
        stage = more_options_pipeline().ensure_stage("s1")
        self.assertEqual(False, stage.fetch_materials)

    def test_can_set_fetch_materials_flag(self):
        stage = typical_pipeline().ensure_stage("build")
        s = stage.set_fetch_materials(False)
        self.assertEqual(s, stage)
        self.assertEqual(False, stage.fetch_materials)
        stage = more_options_pipeline().ensure_stage("s1")
        stage.set_fetch_materials(True)
        self.assertEqual(True, stage.fetch_materials)

    def test_stages_have_jobs(self):
        stages = typical_pipeline().stages
        jobs = stages[0].jobs
        self.assertEqual(1, len(jobs))
        self.assertEqual('compile', jobs[0].name)

    def test_can_add_job(self):
        stage = typical_pipeline().ensure_stage("deploy")
        self.assertEqual(1, len(stage.jobs))
        ensured_job = stage.ensure_job("new-job")
        self.assertEqual(2, len(stage.jobs))
        self.assertEqual(ensured_job, stage.jobs[1])
        self.assertEqual("new-job", stage.jobs[1].name)

    def test_can_add_job_to_empty_stage(self):
        stage = empty_stage()
        self.assertEqual(0, len(stage.jobs))
        ensured_job = stage.ensure_job("new-job")
        self.assertEqual(1, len(stage.jobs))
        self.assertEqual(ensured_job, stage.jobs[0])
        self.assertEqual("new-job", stage.jobs[0].name)

    def test_can_ensure_job_exists(self):
        stage = typical_pipeline().ensure_stage("deploy")
        self.assertEqual(1, len(stage.jobs))
        ensured_job = stage.ensure_job("upload")
        self.assertEqual(1, len(stage.jobs))
        self.assertEqual("upload", ensured_job.name)

    def test_can_have_encrypted_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-encrypted-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        stage = pipeline.ensure_stage('defaultStage')
        self.assertEqual({"MY_STAGE_PASSWORD": "yq5qqPrrD9/s=="}, stage.encrypted_environment_variables)

    def test_can_set_encrypted_environment_variables(self):
        stage = typical_pipeline().ensure_stage("deploy")
        stage.ensure_encrypted_environment_variables({'one': 'blah=='})
        self.assertEqual({"one": "blah=="}, stage.encrypted_environment_variables)

    def test_can_set_environment_variables(self):
        stage = typical_pipeline().ensure_stage("deploy")
        s = stage.ensure_environment_variables({"new": "one"})
        self.assertEqual(s, stage)
        self.assertEqual({"BASE_URL": "http://myurl", "new": "one"}, stage.environment_variables)

    def test_can_add_unencrypted_secure_environment_variables_to_stage(self):
        stage = typical_pipeline().ensure_stage("deploy")
        stage.ensure_unencrypted_secure_environment_variables({"new": "one", "again": "two"})
        self.assertEqual({"new": "one", "again": "two"}, stage.unencrypted_secure_environment_variables)

    def test_can_remove_all_environment_variables(self):
        stage = typical_pipeline().ensure_stage("deploy")
        s = stage.without_any_environment_variables()
        self.assertEqual(s, stage)
        self.assertEqual({}, stage.environment_variables)


class TestConfigRepo(unittest.TestCase):
    def setUp(self):
        self.configurator = GoCdConfigurator(empty_config())

    def test_ensure_replacement_of_config_repos(self):
        self.configurator.ensure_config_repos().ensure_config_repo('git://url', 'yaml.config.plugin')
        self.assertEqual(len(self.configurator.config_repos.config_repo), 1)

        self.configurator.ensure_replacement_of_config_repos().ensure_config_repo('git://otherurl', 'yaml.config.plugin')
        self.assertEqual(len(self.configurator.config_repos.config_repo), 1)

    def test_can_ensure_config_repo_with_git_url_and_plugin(self):
        self.configurator.ensure_config_repos().ensure_config_repo('git://url', 'yaml.config.plugin')

        self.assertEqual(self.configurator.config_repos.config_repo[0].url, 'git://url')
        self.assertEqual(self.configurator.config_repos.config_repo[0].plugin, 'yaml.config.plugin')

    def test_can_ensure_yaml_config_repo_with_git_url(self):
        self.configurator.ensure_config_repos().ensure_yaml_config_repo('git://url')

        self.assertEqual(self.configurator.config_repos.config_repo[0].url, 'git://url')
        self.assertEqual(self.configurator.config_repos.config_repo[0].plugin, 'yaml.config.plugin')

    def test_can_ensure_json_config_repo_with_git_url(self):
        self.configurator.ensure_config_repos().ensure_json_config_repo('git://url')

        self.assertEqual(self.configurator.config_repos.config_repo[0].url, 'git://url')
        self.assertEqual(self.configurator.config_repos.config_repo[0].plugin, 'json.config.plugin')

    def test_can_ensure_repo_for_different_cvs(self):
        self.configurator.ensure_config_repos().ensure_config_repo('svn://url', 'json.config.plugin', cvs='svn')

        self.assertEqual(self.configurator.config_repos.config_repo[0].url, 'svn://url')
        self.assertEqual(self.configurator.config_repos.config_repo[0].plugin, 'json.config.plugin')

    def test_can_ensure_config_repo_with_configuration(self):
        self.configurator.ensure_config_repos().ensure_config_repo('yml://url', 'yml.config.plugin', cvs='yml',
                                                                   configuration={
                                                                       'file_pattern': '*.gocd.yml'
                                                                   })

        self.assertEqual(self.configurator.config_repos.config_repo[0].configuration, {
            'file_pattern': '*.gocd.yml'
        })

    def test_can_ensure_replacement_of_config_repo(self):
        self.configurator.ensure_config_repos().ensure_config_repo('git://url', 'yml.config.plugin')

        self.configurator.ensure_config_repos().ensure_replacement_of_config_repo('git://url', 'json.config.plugin')

        self.assertEqual(self.configurator.config_repos.config_repo[0].url, 'git://url')
        self.assertEqual(self.configurator.config_repos.config_repo[0].plugin, 'json.config.plugin')

    def test_doesnt_duplicate_config_repos(self):
        self.configurator.ensure_config_repos().ensure_yaml_config_repo('git://url')
        self.configurator.ensure_config_repos().ensure_yaml_config_repo('git://url')

        self.assertEqual(len(self.configurator.config_repos.config_repo), 1)

    def test_can_add_more_than_2_config_repos(self):
        self.configurator.ensure_config_repos().ensure_yaml_config_repo('git://url')
        self.configurator.ensure_config_repos().ensure_json_config_repo('git://url')
        self.configurator.ensure_config_repos().ensure_yaml_config_repo('git://url2')

        self.assertEqual(len(self.configurator.config_repos.config_repo), 3)

    def test_changes_attrs_for_new_server_versions(self):
        configurator = GoCdConfigurator(FakeHostRestClient(empty_config_xml, version='17.9.0'))
        configurator.ensure_config_repos().ensure_config_repo('git://url', 'yml.config.plugin', repo_id='myRepo')
        self.assertEqual(configurator.config_repos.config_repo[0].element.get('pluginId'), 'yml.config.plugin')
        self.assertEqual(configurator.config_repos.config_repo[0].plugin, 'yml.config.plugin')
        self.assertEqual(configurator.config_repos.config_repo[0].repo_id, 'myRepo')

    def test_handles_unspecified_id_for_migration(self):
        configurator = GoCdConfigurator(FakeHostRestClient(empty_config_xml, version='17.8.0'))
        configurator.ensure_config_repos().ensure_config_repo('git://url', 'yml.config.plugin')
        self.assertIsNotNone(configurator.config_repos.config_repo[0].repo_id)

class TestPipeline(unittest.TestCase):
    def test_pipelines_have_names(self):
        pipeline = typical_pipeline()
        self.assertEqual('typical', pipeline.name)

    def test_can_add_stage(self):
        pipeline = empty_pipeline()
        self.assertEqual(0, len(pipeline.stages))
        new_stage = pipeline.ensure_stage("some_stage")
        self.assertEqual(1, len(pipeline.stages))
        self.assertEqual(new_stage, pipeline.stages[0])
        self.assertEqual("some_stage", new_stage.name)

    def test_can_ensure_stage(self):
        pipeline = typical_pipeline()
        self.assertEqual(3, len(pipeline.stages))
        ensured_stage = pipeline.ensure_stage("deploy")
        self.assertEqual(3, len(pipeline.stages))
        self.assertEqual("deploy", ensured_stage.name)

    def test_can_remove_stage(self):
        pipeline = typical_pipeline()
        self.assertEqual(3, len(pipeline.stages))
        p = pipeline.ensure_removal_of_stage("deploy")
        self.assertEqual(p, pipeline)
        self.assertEqual(2, len(pipeline.stages))
        self.assertEqual(0, len([s for s in pipeline.stages if s.name == "deploy"]))

    def test_can_ensure_removal_of_stage(self):
        pipeline = typical_pipeline()
        self.assertEqual(3, len(pipeline.stages))
        pipeline.ensure_removal_of_stage("stage-that-has-already-been-deleted")
        self.assertEqual(3, len(pipeline.stages))

    def test_can_ensure_initial_stage(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("first")
        self.assertEqual(stage, pipeline.stages[0])
        self.assertEqual(4, len(pipeline.stages))

    def test_can_ensure_initial_stage_if_already_exists_as_initial(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("build")
        self.assertEqual(stage, pipeline.stages[0])
        self.assertEqual(3, len(pipeline.stages))

    def test_can_ensure_initial_stage_if_already_exists(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("deploy")
        self.assertEqual(stage, pipeline.stages[0])
        self.assertEqual("build", pipeline.stages[1].name)
        self.assertEqual(3, len(pipeline.stages))

    def test_can_set_stage_clean_policy(self):
        pipeline = empty_pipeline()
        stage1 = pipeline.ensure_stage("some_stage1").set_clean_working_dir()
        stage2 = pipeline.ensure_stage("some_stage2")
        self.assertEqual(True, pipeline.stages[0].clean_working_dir)
        self.assertEqual(True, stage1.clean_working_dir)
        self.assertEqual(False, pipeline.stages[1].clean_working_dir)
        self.assertEqual(False, stage2.clean_working_dir)

    def test_pipelines_can_have_git_urls(self):
        pipeline = typical_pipeline()
        self.assertEqual("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url)

    def test_git_is_polled_by_default(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.set_git_url("some git url")
        self.assertEqual(True, pipeline.git_material.polling)

    def test_pipelines_can_have_git_material_with_material_name(self):
        pipeline = more_options_pipeline()
        self.assertEqual("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url)
        self.assertEqual("some-material-name", pipeline.git_material.material_name)

    def test_git_material_can_ignore_sources(self):
        pipeline = GoCdConfigurator(config('config-with-source-exclusions')).ensure_pipeline_group("P.Group").find_pipeline("with-exclusions")
        self.assertEqual({"excluded-folder", "another-excluded-folder"}, pipeline.git_material.ignore_patterns)

    def test_can_set_pipeline_git_url(self):
        pipeline = typical_pipeline()
        p = pipeline.set_git_url("git@bitbucket.org:springersbm/changed.git")
        self.assertEqual(p, pipeline)
        self.assertEqual("git@bitbucket.org:springersbm/changed.git", pipeline.git_url)
        self.assertEqual('master', pipeline.git_branch)

    def test_can_set_pipeline_git_url_with_options(self):
        pipeline = typical_pipeline()
        p = pipeline.set_git_material(GitMaterial(
            "git@bitbucket.org:springersbm/changed.git",
            branch="branch",
            destination_directory="foo",
            material_name="material-name",
            ignore_patterns={"ignoreMe", "ignoreThisToo"},
            polling=False))
        self.assertEqual(p, pipeline)
        self.assertEqual("branch", pipeline.git_branch)
        self.assertEqual("foo", pipeline.git_material.destination_directory)
        self.assertEqual("material-name", pipeline.git_material.material_name)
        self.assertEqual({"ignoreMe", "ignoreThisToo"}, pipeline.git_material.ignore_patterns)
        self.assertFalse(pipeline.git_material.polling, "git polling")

    def test_throws_exception_if_no_git_url(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        self.assertEqual(False, pipeline.has_single_git_material)
        try:
            url = pipeline.git_url
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_git_url_throws_exception_if_multiple_git_materials(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/one.git"))
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/two.git"))
        self.assertEqual(False, pipeline.has_single_git_material)
        try:
            url = pipeline.git_url
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_set_git_url_throws_exception_if_multiple_git_materials(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/one.git"))
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/two.git"))
        try:
            pipeline.set_git_url("git@bitbucket.org:springersbm/three.git")
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_can_add_git_material(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        p = pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/changed.git"))
        self.assertEqual(p, pipeline)
        self.assertEqual("git@bitbucket.org:springersbm/changed.git", pipeline.git_url)

    def test_can_ensure_git_material(self):
        pipeline = typical_pipeline()
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/gomatic.git"))
        self.assertEqual("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url)
        self.assertEqual([GitMaterial("git@bitbucket.org:springersbm/gomatic.git")], pipeline.materials)

    def test_can_have_multiple_git_materials(self):
        pipeline = typical_pipeline()
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/changed.git"))
        self.assertEqual([GitMaterial("git@bitbucket.org:springersbm/gomatic.git"), GitMaterial("git@bitbucket.org:springersbm/changed.git")],
                          pipeline.materials)

    def test_pipelines_can_have_pipeline_materials(self):
        pipeline = more_options_pipeline()
        self.assertEqual(2, len(pipeline.materials))
        self.assertEqual(GitMaterial('git@bitbucket.org:springersbm/gomatic.git', branch="a-branch", material_name="some-material-name", polling=False),
                          pipeline.materials[0])

    def test_pipelines_can_have_more_complicated_pipeline_materials(self):
        pipeline = more_options_pipeline()
        self.assertEqual(2, len(pipeline.materials))
        self.assertEqual(True, pipeline.materials[0].is_git)
        self.assertEqual(PipelineMaterial('pipeline2', 'build'), pipeline.materials[1])

    def test_pipelines_can_have_no_materials(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        self.assertEqual(0, len(pipeline.materials))

    def test_can_add_pipeline_material(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        p = pipeline.ensure_material(PipelineMaterial('deploy-qa', 'baseline-user-data'))
        self.assertEqual(p, pipeline)
        self.assertEqual(PipelineMaterial('deploy-qa', 'baseline-user-data'), pipeline.materials[0])

    def test_can_add_more_complicated_pipeline_material(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        p = pipeline.ensure_material(PipelineMaterial('p', 's', 'm'))
        self.assertEqual(p, pipeline)
        self.assertEqual(PipelineMaterial('p', 's', 'm'), pipeline.materials[0])

    def test_can_ensure_pipeline_material(self):
        pipeline = more_options_pipeline()
        self.assertEqual(2, len(pipeline.materials))
        pipeline.ensure_material(PipelineMaterial('pipeline2', 'build'))
        self.assertEqual(2, len(pipeline.materials))

    def test_can_remove_all_pipeline_materials(self):
        pipeline = more_options_pipeline()
        pipeline.remove_materials()
        self.assertEqual(0, len(pipeline.materials))

    def test_materials_are_sorted(self):
        go_cd_configurator = GoCdConfigurator(empty_config())
        pipeline = go_cd_configurator.ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.ensure_material(PipelineMaterial('zeta', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/zebra.git'))
        pipeline.ensure_material(PipelineMaterial('alpha', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/art.git'))
        pipeline.ensure_material(PipelineMaterial('theta', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/this.git'))

        xml = parseString(go_cd_configurator.config)
        materials = xml.getElementsByTagName('materials')[0].childNodes
        self.assertEqual('git', materials[0].tagName)
        self.assertEqual('git', materials[1].tagName)
        self.assertEqual('git', materials[2].tagName)
        self.assertEqual('pipeline', materials[3].tagName)
        self.assertEqual('pipeline', materials[4].tagName)
        self.assertEqual('pipeline', materials[5].tagName)

        self.assertEqual('git@bitbucket.org:springersbm/art.git', materials[0].attributes['url'].value)
        self.assertEqual('git@bitbucket.org:springersbm/this.git', materials[1].attributes['url'].value)
        self.assertEqual('git@bitbucket.org:springersbm/zebra.git', materials[2].attributes['url'].value)
        self.assertEqual('alpha', materials[3].attributes['pipelineName'].value)
        self.assertEqual('theta', materials[4].attributes['pipelineName'].value)
        self.assertEqual('zeta', materials[5].attributes['pipelineName'].value)

    def test_can_set_pipeline_git_url_for_new_pipeline(self):
        pipeline_group = standard_pipeline_group()
        new_pipeline = pipeline_group.ensure_pipeline("some_name")
        new_pipeline.set_git_url("git@bitbucket.org:springersbm/changed.git")
        self.assertEqual("git@bitbucket.org:springersbm/changed.git", new_pipeline.git_url)

    def test_pipelines_do_not_have_to_be_based_on_template(self):
        pipeline = more_options_pipeline()
        self.assertFalse(pipeline.is_based_on_template)

    def test_pipelines_can_be_based_on_template(self):
        pipeline = GoCdConfigurator(config('pipeline-based-on-template')).ensure_pipeline_group('defaultGroup').find_pipeline('siberian')
        assert isinstance(pipeline, Pipeline)
        self.assertTrue(pipeline.is_based_on_template)
        template = GoCdConfigurator(config('pipeline-based-on-template')).templates[0]
        self.assertEqual(template, pipeline.template)

    def test_pipelines_can_be_created_based_on_template(self):
        configurator = GoCdConfigurator(empty_config())
        configurator.ensure_template('temple').ensure_stage('s').ensure_job('j')
        pipeline = configurator.ensure_pipeline_group("g").ensure_pipeline('p').set_template_name('temple')
        self.assertEqual('temple', pipeline.template.name)

    def test_pipelines_have_environment_variables(self):
        pipeline = typical_pipeline()
        self.assertEqual({"JAVA_HOME": "/opt/java/jdk-1.8"}, pipeline.environment_variables)

    def test_pipelines_have_encrypted_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-encrypted-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        self.assertEqual({"MY_SECURE_PASSWORD": "yq5qqPrrD9/htfwTWMYqGQ=="}, pipeline.encrypted_environment_variables)

    def test_pipelines_have_unencrypted_secure_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-unencrypted-secure-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        self.assertEqual({"MY_SECURE_PASSWORD": "hunter2"}, pipeline.unencrypted_secure_environment_variables)

    def test_pipelines_have_unencrypted_secure_environment_variable_unicode(self):
        pipeline = GoCdConfigurator(config('config-with-unencrypted-secure-variable-unicode')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        self.assertEqual({"MY_SECURE_PASSWORD": u"hunter2ª"}, pipeline.unencrypted_secure_environment_variables)

    def test_can_add_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        p = pipeline.ensure_environment_variables({"new": "one", "again": "two"})
        self.assertEqual(p, pipeline)
        self.assertEqual({"new": "one", "again": "two"}, pipeline.environment_variables)

    def test_can_add_encrypted_secure_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        pipeline.ensure_encrypted_environment_variables({"new": "one", "again": "two"})
        self.assertEqual({"new": "one", "again": "two"}, pipeline.encrypted_environment_variables)

    def test_can_add_unencrypted_secure_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        pipeline.ensure_unencrypted_secure_environment_variables({"new": "one", "again": "two"})
        self.assertEqual({"new": "one", "again": "two"}, pipeline.unencrypted_secure_environment_variables)

    def test_can_add_environment_variables_to_new_pipeline(self):
        pipeline = typical_pipeline()
        pipeline.ensure_environment_variables({"new": "one"})
        self.assertEqual({"JAVA_HOME": "/opt/java/jdk-1.8", "new": "one"}, pipeline.environment_variables)

    def test_can_modify_environment_variables_of_pipeline(self):
        pipeline = typical_pipeline()
        pipeline.ensure_environment_variables({"new": "one", "JAVA_HOME": "/opt/java/jdk-1.1"})
        self.assertEqual({"JAVA_HOME": "/opt/java/jdk-1.1", "new": "one"}, pipeline.environment_variables)

    def test_can_remove_all_environment_variables(self):
        pipeline = typical_pipeline()
        p = pipeline.without_any_environment_variables()
        self.assertEqual(p, pipeline)
        self.assertEqual({}, pipeline.environment_variables)

    def test_can_remove_specific_environment_variable(self):
        pipeline = empty_pipeline()
        pipeline.ensure_encrypted_environment_variables({'a': 's'})
        pipeline.ensure_environment_variables({'c': 'v', 'd': 'f'})

        pipeline.remove_environment_variable('d')
        p = pipeline.remove_environment_variable('unknown')

        self.assertEqual(p, pipeline)
        self.assertEqual({'a': 's'}, pipeline.encrypted_environment_variables)
        self.assertEqual({'c': 'v'}, pipeline.environment_variables)

    def test_environment_variables_get_added_in_sorted_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_environment_variables({"badger": "a", "xray": "a"})
        pipeline.ensure_environment_variables({"ant": "a2", "zebra": "a"})

        xml = parseString(go_cd_configurator.config)
        names = [e.getAttribute('name') for e in xml.getElementsByTagName('variable')]
        self.assertEqual([u'ant', u'badger', u'xray', u'zebra'], names)

    def test_encrypted_environment_variables_get_added_in_sorted_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_encrypted_environment_variables({"badger": "a", "xray": "a"})
        pipeline.ensure_encrypted_environment_variables({"ant": "a2", "zebra": "a"})

        xml = parseString(go_cd_configurator.config)
        names = [e.getAttribute('name') for e in xml.getElementsByTagName('variable')]
        self.assertEqual([u'ant', u'badger', u'xray', u'zebra'], names)

    def test_unencrypted_environment_variables_do_not_have_secure_attribute_in_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_environment_variables({"ant": "a"})

        xml = parseString(go_cd_configurator.config)
        secure_attributes = [e.getAttribute('secure') for e in xml.getElementsByTagName('variable')]
        # attributes that are missing are returned as empty
        self.assertEqual([''], secure_attributes, "should not have any 'secure' attributes")

    def test_cannot_have_environment_variable_which_is_both_secure_and_insecure(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_unencrypted_secure_environment_variables({"ant": "a"})
        pipeline.ensure_environment_variables({"ant": "b"})  # not secure
        self.assertEqual({"ant": "b"}, pipeline.environment_variables)
        self.assertEqual({}, pipeline.unencrypted_secure_environment_variables)

    def test_can_change_environment_variable_from_secure_to_insecure(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_unencrypted_secure_environment_variables({"ant": "a", "badger": "b"})
        pipeline.ensure_environment_variables({"ant": "b"})
        self.assertEqual({"ant": "b"}, pipeline.environment_variables)
        self.assertEqual({"badger": "b"}, pipeline.unencrypted_secure_environment_variables)

    def test_pipelines_have_parameters(self):
        pipeline = more_options_pipeline()
        self.assertEqual({"environment": "qa"}, pipeline.parameters)

    def test_pipelines_have_no_parameters(self):
        pipeline = typical_pipeline()
        self.assertEqual({}, pipeline.parameters)

    def test_can_add_params_to_pipeline(self):
        pipeline = typical_pipeline()
        p = pipeline.ensure_parameters({"new": "one", "again": "two"})
        self.assertEqual(p, pipeline)
        self.assertEqual({"new": "one", "again": "two"}, pipeline.parameters)

    def test_can_modify_parameters_of_pipeline(self):
        pipeline = more_options_pipeline()
        pipeline.ensure_parameters({"new": "one", "environment": "qa55"})
        self.assertEqual({"environment": "qa55", "new": "one"}, pipeline.parameters)

    def test_can_remove_all_parameters(self):
        pipeline = more_options_pipeline()
        p = pipeline.without_any_parameters()
        self.assertEqual(p, pipeline)
        self.assertEqual({}, pipeline.parameters)

    def test_can_have_timer(self):
        pipeline = more_options_pipeline()
        self.assertEqual(True, pipeline.has_timer)
        self.assertEqual("0 15 22 * * ?", pipeline.timer)
        self.assertEqual(False, pipeline.timer_triggers_only_on_changes)

    def test_can_have_timer_with_onlyOnChanges_option(self):
        pipeline = GoCdConfigurator(config('config-with-more-options-pipeline')).ensure_pipeline_group('P.Group').find_pipeline('pipeline2')
        self.assertEqual(True, pipeline.has_timer)
        self.assertEqual("0 0 22 ? * MON-FRI", pipeline.timer)
        self.assertEqual(True, pipeline.timer_triggers_only_on_changes)

    def test_need_not_have_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        self.assertEqual(False, pipeline.has_timer)
        try:
            timer = pipeline.timer
            self.fail('should have thrown an exception')
        except RuntimeError:
            pass

    def test_can_set_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_timer("one two three")
        self.assertEqual(p, pipeline)
        self.assertEqual("one two three", pipeline.timer)

    def test_can_set_timer_with_only_on_changes_flag_off(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_timer("one two three", only_on_changes=False)
        self.assertEqual(p, pipeline)
        self.assertEqual("one two three", pipeline.timer)
        self.assertEqual(False, pipeline.timer_triggers_only_on_changes)

    def test_can_set_timer_with_only_on_changes_flag(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_timer("one two three", only_on_changes=True)
        self.assertEqual(p, pipeline)
        self.assertEqual("one two three", pipeline.timer)
        self.assertEqual(True, pipeline.timer_triggers_only_on_changes)

    def test_can_remove_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        pipeline.set_timer("one two three")
        p = pipeline.remove_timer()
        self.assertEqual(p, pipeline)
        self.assertFalse(pipeline.has_timer)

    def test_can_have_label_template(self):
        pipeline = typical_pipeline()
        self.assertEqual("something-${COUNT}", pipeline.label_template)
        self.assertEqual(True, pipeline.has_label_template)

    def test_might_not_have_label_template(self):
        pipeline = more_options_pipeline()  # TODO swap label with typical
        self.assertEqual(False, pipeline.has_label_template)
        try:
            label_template = pipeline.label_template
            self.fail('should have thrown an exception')
        except RuntimeError:
            pass

    def test_can_set_label_template(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_label_template("some label")
        self.assertEqual(p, pipeline)
        self.assertEqual("some label", pipeline.label_template)

    def test_can_set_default_label_template(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_default_label_template()
        self.assertEqual(p, pipeline)
        self.assertEqual(DEFAULT_LABEL_TEMPLATE, pipeline.label_template)

    def test_can_set_automatic_pipeline_locking(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline = configurator.ensure_pipeline_group("new_group").ensure_pipeline("some_name")
        p = pipeline.set_automatic_pipeline_locking()
        self.assertEqual(p, pipeline)
        self.assertEqual(True, pipeline.has_automatic_pipeline_locking)

    def test_can_set_lock_behavior(self):
        lock_on_failure = 'lockOnFailure'
        configurator = GoCdConfigurator(empty_config())
        pipeline = configurator.ensure_pipeline_group("new_group").ensure_pipeline("some_name")
        p = pipeline.set_lock_behavior(lock_on_failure)
        self.assertEqual(p, pipeline)
        self.assertEqual(True, pipeline.has_lock_behavior)
        self.assertEqual(lock_on_failure, pipeline.lock_behavior)

    def test_can_have_package_repo_material(self):
        pipeline = GoCdConfigurator(config('config-with-pipeline-and-yum-repo')).ensure_pipeline_group('P.Group').find_pipeline('test')
        self.assertTrue(pipeline.has_single_package_material)
        self.assertEqual(pipeline.package_material.ref, "eca7f187-73c2-4f62-971a-d15233937256")

    def test_can_set_pipeline_package_ref(self):
        pipeline = typical_pipeline()
        p = pipeline.set_package_ref("eca7f187-73c2-4f62-971a-d15233937256")
        self.assertEqual(p, pipeline)
        self.assertEqual("eca7f187-73c2-4f62-971a-d15233937256", pipeline.package_material.ref)


class TestAuthorization(unittest.TestCase):
    def setUp(self):
        configurator = GoCdConfigurator(config('config-with-two-pipelines'))
        self.pipeline_group = configurator.ensure_pipeline_group('g')

    def test_can_authorize_users_and_roles_for_operate(self):
        self.pipeline_group.ensure_authorization().ensure_operate().add_user('user1').add_role('role1')

        self.assertEqual(self.pipeline_group.authorization.operate.users[0].username, 'user1')
        self.assertEqual(self.pipeline_group.authorization.operate.roles[0].name, 'role1')

    def test_can_authorize_users_and_roles_for_admins(self):
        self.pipeline_group.ensure_authorization().ensure_admins().add_user('user1').add_role('role1')

        self.assertEqual(self.pipeline_group.authorization.admins.users[0].username, 'user1')
        self.assertEqual(self.pipeline_group.authorization.admins.roles[0].name, 'role1')

    def test_can_ensure_replacement_of_authorization(self):
        self.pipeline_group.ensure_authorization().ensure_admins().add_user('user1')
        self.assertEqual(len(self.pipeline_group.authorization.admins.users), 1)

        self.pipeline_group.ensure_replacement_of_authorization().ensure_admins().add_user('user2')
        self.assertEqual(len(self.pipeline_group.authorization.admins.users), 1)


class TestPipelineGroup(unittest.TestCase):
    def _pipeline_group_from_config(self):
        return GoCdConfigurator(config('config-with-two-pipelines')).ensure_pipeline_group('P.Group')

    def test_pipeline_groups_have_names(self):
        pipeline_group = standard_pipeline_group()
        self.assertEqual("P.Group", pipeline_group.name)

    def test_pipeline_groups_have_pipelines(self):
        pipeline_group = self._pipeline_group_from_config()
        self.assertEqual(2, len(pipeline_group.pipelines))

    def test_can_authorize_read_only_users(self):
        pipeline_group = self._pipeline_group_from_config()
        pipeline_group.ensure_authorization().ensure_view().add_user('user1').add_user('user2')
        self.assertEqual(2, len(pipeline_group.authorization.view.users))
        self.assertEqual('user1', pipeline_group.authorization.view.users[0].username)
        self.assertEqual('user2', pipeline_group.authorization.view.users[1].username)

    def test_reorders_elements_to_please_go(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline_group = configurator.ensure_pipeline_group("new_group")
        pipeline_group.ensure_pipeline("some_name")
        pipeline_group.ensure_authorization().ensure_view().add_user('user1').add_user('user2')

        xml = configurator.config

        pipeline_group_root = ET.fromstring(xml).find('pipelines')
        self.assertEqual("authorization", pipeline_group_root[0].tag)
        self.assertEqual("pipeline", pipeline_group_root[1].tag)

    def test_can_add_pipeline(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline_group = configurator.ensure_pipeline_group("new_group")
        new_pipeline = pipeline_group.ensure_pipeline("some_name")
        self.assertEqual(1, len(pipeline_group.pipelines))
        self.assertEqual(new_pipeline, pipeline_group.pipelines[0])
        self.assertEqual("some_name", new_pipeline.name)
        self.assertEqual(False, new_pipeline.has_single_git_material)
        self.assertEqual(False, new_pipeline.has_label_template)
        self.assertEqual(False, new_pipeline.has_automatic_pipeline_locking)

    def test_can_find_pipeline(self):
        found_pipeline = self._pipeline_group_from_config().find_pipeline("pipeline2")
        self.assertEqual("pipeline2", found_pipeline.name)
        self.assertTrue(self._pipeline_group_from_config().has_pipeline("pipeline2"))

    def test_does_not_find_missing_pipeline(self):
        self.assertFalse(self._pipeline_group_from_config().has_pipeline("unknown-pipeline"))
        try:
            self._pipeline_group_from_config().find_pipeline("unknown-pipeline")
            self.fail("should have thrown exception")
        except RuntimeError as e:
            self.assertTrue(str(e).count("unknown-pipeline"))

    def test_can_remove_pipeline(self):
        pipeline_group = self._pipeline_group_from_config()
        pipeline_group.ensure_removal_of_pipeline("pipeline1")
        self.assertEqual(1, len(pipeline_group.pipelines))
        try:
            pipeline_group.find_pipeline("pipeline1")
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_ensuring_replacement_of_pipeline_leaves_it_empty_but_in_same_place(self):
        pipeline_group = self._pipeline_group_from_config()
        self.assertEqual("pipeline1", pipeline_group.pipelines[0].name)
        pipeline = pipeline_group.find_pipeline("pipeline1")
        pipeline.set_label_template("something")
        self.assertEqual(True, pipeline.has_label_template)

        p = pipeline_group.ensure_replacement_of_pipeline("pipeline1")
        self.assertEqual(p, pipeline_group.pipelines[0])
        self.assertEqual("pipeline1", p.name)
        self.assertEqual(False, p.has_label_template)

    def test_can_ensure_pipeline_removal(self):
        pipeline_group = self._pipeline_group_from_config()
        pg = pipeline_group.ensure_removal_of_pipeline("already-removed-pipeline")
        self.assertEqual(pg, pipeline_group)
        self.assertEqual(2, len(pipeline_group.pipelines))
        try:
            pipeline_group.find_pipeline("already-removed-pipeline")
            self.fail("should have thrown exception")
        except RuntimeError:
            pass


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.configurator = GoCdConfigurator(empty_config())

    def test_can_ensure_admin_role(self):
        self.configurator.ensure_security().ensure_admins().add_user(name='admin')

        self.assertEqual(self.configurator.security.admins[0], 'admin')

    def test_can_ensure_roles(self):
        self.configurator.ensure_security().ensure_roles().ensure_role(name='role_name', users=['user1', 'user2'])

        self.assertEqual(self.configurator.security.roles.role[0].name, 'role_name')
        self.assertEqual(self.configurator.security.roles.role[0].users, ['user1', 'user2'])

    def test_can_ensure_plugin_roles(self):
        self.configurator.ensure_security().ensure_roles().ensure_plugin_role(name='role_name',
                                                                              auth_config_id='id-for-auth-plugin',
                                                                              properties={
                                                                                  'SomeKey': 'SomeValue'
                                                                              })

        self.assertEqual(self.configurator.security.roles.plugin_role[0].name, 'role_name')
        self.assertEqual(self.configurator.security.roles.plugin_role[0].auth_config_id, 'id-for-auth-plugin')
        self.assertEqual(self.configurator.security.roles.plugin_role[0].properties, {'SomeKey': 'SomeValue'})

    def test_can_ensure_replacement_of_security(self):
        self.configurator.ensure_security().ensure_roles().ensure_role(name='role_name', users=['user1', 'user2'])
        self.assertEqual(len(self.configurator.security.roles), 1)

        self.configurator.ensure_replacement_of_security().ensure_roles().ensure_role(name='another_role_name', users=['user1', 'user2'])
        self.assertEqual(len(self.configurator.security.roles), 1)

    def test_can_ensure_replacement_of_roles(self):
        self.configurator.ensure_security().ensure_roles().ensure_role(name='role_name', users=['user1', 'user2'])
        self.assertEqual(len(self.configurator.security.roles), 1)

        self.configurator.ensure_security().ensure_replacement_of_roles().ensure_role(name='another_role_name', users=['user1', 'user2'])
        self.assertEqual(len(self.configurator.security.roles), 1)

    def test_can_ensure_auth_config(self):
        properties = {'key': 'value' }
        self.configurator.ensure_security().ensure_auth_configs().ensure_auth_config(auth_config_id='auth-plugin-1',
                                                                                     plugin_id='auth.plugin.id',
                                                                                     properties=properties)

        self.assertEqual(self.configurator.security.auth_configs[0].auth_config_id, 'auth-plugin-1')
        self.assertEqual(self.configurator.security.auth_configs[0].plugin_id, 'auth.plugin.id')
        self.assertEqual(self.configurator.security.auth_configs[0].properties, properties)


    def test_doesnt_add_same_plugin_twice_and_equality_is_only_by_id(self):
        self.configurator.ensure_security(). \
            ensure_auth_configs(). \
            ensure_auth_config(auth_config_id='auth-plugin-1', plugin_id='auth.plugin.id', properties={})
        self.configurator.ensure_security(). \
            ensure_auth_configs(). \
            ensure_auth_config(auth_config_id='auth-plugin-1', plugin_id='another.plugin.id', properties={})

        self.assertEqual(self.configurator.security.auth_configs[0].auth_config_id, 'auth-plugin-1')
        self.assertEqual(self.configurator.security.auth_configs[0].plugin_id, 'auth.plugin.id')
        self.assertEqual(self.configurator.security.auth_configs[0].properties, {})

    def test_can_ensure_replacement_of_auth_configs(self):
        # this test ensures that you can replace ALL auth configs
        self.configurator.ensure_security(). \
            ensure_auth_configs(). \
            ensure_auth_config(auth_config_id='auth-plugin-1', plugin_id='auth.plugin.id', properties={})

        self.assertEqual(len(self.configurator.security.auth_configs), 1)

        self.configurator.ensure_security(). \
            ensure_replacement_of_auth_configs(). \
            ensure_auth_config(auth_config_id='auth-plugin-2', plugin_id='auth.plugin.id', properties={})

        self.assertEqual(len(self.configurator.security.auth_configs), 1)

    def test_can_ensure_replacement_of_auth_config(self):
        # this test ensures that you can override just a single auth config
        self.configurator.ensure_security(). \
            ensure_auth_configs(). \
            ensure_auth_config(auth_config_id='auth-plugin-1', plugin_id='auth.plugin.id', properties={})

        self.assertEqual(len(self.configurator.security.auth_configs), 1)

        self.configurator.ensure_security(). \
            ensure_auth_configs(). \
            ensure_replacement_of_auth_config(auth_config_id='auth-plugin-1', plugin_id='auth.plugin.id', properties={})

        self.assertEqual(len(self.configurator.security.auth_configs), 1)


class TestElastic(unittest.TestCase):
    def setUp(self):
        self.configurator = GoCdConfigurator(empty_config())

    def test_ensure_profile_returns_profile(self):
        properties = {'key': 'value' }
        profile = self.configurator.ensure_elastic().ensure_profiles().ensure_profile(profile_id='unit-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties=properties)

        self.assertEqual(self.configurator.elastic.profiles[0], profile)
        self.assertEqual(profile.profile_id, 'unit-test')
        self.assertEqual(profile.plugin_id, 'cd.go.contrib.elastic-agent.docker')
        self.assertEqual(profile.properties, properties)

    def test_can_ensure_elastic(self):
        properties = {'key': 'value' }
        self.configurator.ensure_elastic().ensure_profiles().ensure_profile(profile_id='unit-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties=properties)

        self.assertEqual(self.configurator.elastic.profiles[0].profile_id, 'unit-test')
        self.assertEqual(self.configurator.elastic.profiles[0].plugin_id, 'cd.go.contrib.elastic-agent.docker')
        self.assertEqual(self.configurator.elastic.profiles[0].properties, properties)

    def test_can_ensure_replacement_of_elastic(self):
        self.configurator.ensure_elastic().ensure_profiles().ensure_profile(profile_id='unit-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties={})
        self.assertEqual(len(self.configurator.elastic.profiles), 1)

        self.configurator.ensure_replacement_of_elastic().ensure_profiles().ensure_profile(profile_id='unit-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties={})
        self.assertEqual(len(self.configurator.elastic.profiles), 1)

    def test_can_ensure_replacement_of_profiles(self):
        self.configurator.ensure_elastic().ensure_profiles().ensure_profile(profile_id='unit-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties={})
        self.assertEqual(len(self.configurator.elastic.profiles), 1)

        self.configurator.ensure_elastic().ensure_replacement_of_profiles().ensure_profile(profile_id='integration-test',
                plugin_id='cd.go.contrib.elastic-agent.docker',
                properties={})
        self.assertEqual(len(self.configurator.elastic.profiles), 1)

    def test_can_ensure_replacement_of_profile(self):
        # this test ensures that you can override just a single profile
        self.configurator.ensure_elastic(). \
            ensure_profiles(). \
            ensure_profile(profile_id='unit-test', plugin_id='cd.go.contrib.elastic-agent.docker', properties={})

        self.assertEqual(len(self.configurator.elastic.profiles), 1)

        self.configurator.ensure_elastic(). \
            ensure_profiles(). \
            ensure_replacement_of_profile(profile_id='unit-test', plugin_id='cd.go.contrib.elastic-agent.docker', properties={})

        self.assertEqual(len(self.configurator.elastic.profiles), 1)

    def test_doesnt_add_same_plugin_twice_and_equality_is_only_by_id(self):
        self.configurator.ensure_elastic(). \
            ensure_profiles(). \
            ensure_profile(profile_id='unit-test', plugin_id='cd.go.contrib.elastic-agent.docker', properties={})
        self.configurator.ensure_elastic(). \
            ensure_profiles(). \
            ensure_profile(profile_id='unit-test', plugin_id='cd.go.contrib.elastic-agent.docker-swarm', properties={})

        self.assertEqual(self.configurator.elastic.profiles[0].profile_id, 'unit-test')
        self.assertEqual(self.configurator.elastic.profiles[0].plugin_id, 'cd.go.contrib.elastic-agent.docker')
        self.assertEqual(self.configurator.elastic.profiles[0].properties, {})


class TestGoCdConfigurator(unittest.TestCase):
    def test_can_tell_if_there_is_no_change_to_save(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))

        p = configurator.ensure_pipeline_group('Second.Group').ensure_replacement_of_pipeline('smoke-tests')
        p.set_git_url('git@bitbucket.org:springersbm/gomatic.git')
        p.ensure_stage('build').ensure_job('compile').ensure_task(ExecTask(['make', 'source code']))

        self.assertFalse(configurator.has_changes)

    def test_can_tell_if_there_is_a_change_to_save(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))

        p = configurator.ensure_pipeline_group('Second.Group').ensure_replacement_of_pipeline('smoke-tests')
        p.set_git_url('git@bitbucket.org:springersbm/gomatic.git')
        p.ensure_stage('moo').ensure_job('bar')

        self.assertTrue(configurator.has_changes)

    def test_saves_local_config_files_if_flag_is_true(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        configurator.save_updated_config(save_config_locally=True, dry_run=True)
        self.assertTrue(os.path.exists('config-before.xml'))
        self.assertTrue(os.path.exists('config-after.xml'))

    def test_keeps_schema_version(self):
        empty_config = FakeHostRestClient(empty_config_xml.replace('schemaVersion="72"', 'schemaVersion="73"'), "empty_config()")
        configurator = GoCdConfigurator(empty_config)
        self.assertEqual(1, configurator.config.count('schemaVersion="73"'.encode()))

    def test_can_find_out_server_settings(self):
        configurator = GoCdConfigurator(config('config-with-server-settings'))
        self.assertEqual("/some/dir", configurator.artifacts_dir)
        self.assertEqual("http://10.20.30.40/", configurator.site_url)
        self.assertEqual("my_ci_server", configurator.agent_auto_register_key)
        self.assertEqual(Decimal("55.0"), configurator.purge_start)
        self.assertEqual(Decimal("75.0"), configurator.purge_upto)

    def test_can_find_out_server_settings_when_not_set(self):
        configurator = GoCdConfigurator(config('config-with-no-server-settings'))
        self.assertEqual(None, configurator.artifacts_dir)
        self.assertEqual(None, configurator.site_url)
        self.assertEqual(None, configurator.agent_auto_register_key)
        self.assertEqual(None, configurator.purge_start)
        self.assertEqual(None, configurator.purge_upto)

    def test_can_set_server_settings(self):
        configurator = GoCdConfigurator(config('config-with-no-server-settings'))
        configurator.artifacts_dir = "/a/dir"
        configurator.site_url = "http://1.2.3.4/"
        configurator.agent_auto_register_key = "a_ci_server"
        configurator.purge_start = Decimal("44.0")
        configurator.purge_upto = Decimal("88.0")
        configurator.default_job_timeout = 42
        self.assertEqual("/a/dir", configurator.artifacts_dir)
        self.assertEqual("http://1.2.3.4/", configurator.site_url)
        self.assertEqual("a_ci_server", configurator.agent_auto_register_key)
        self.assertEqual(Decimal("44.0"), configurator.purge_start)
        self.assertEqual(Decimal("88.0"), configurator.purge_upto)
        self.assertEqual(Decimal("42"), configurator.default_job_timeout)

    def test_can_have_no_pipeline_groups(self):
        self.assertEqual(0, len(GoCdConfigurator(empty_config()).pipeline_groups))

    def test_gets_all_pipeline_groups(self):
        self.assertEqual(2, len(GoCdConfigurator(config('config-with-two-pipeline-groups')).pipeline_groups))

    def test_can_get_initial_config_md5(self):
        configurator = GoCdConfigurator(empty_config())
        self.assertEqual("42", configurator._initial_md5)

    def test_config_is_updated_as_result_of_updating_part_of_it(self):
        configurator = GoCdConfigurator(config('config-with-just-agents'))
        agent = configurator.agents[0]
        self.assertEqual(2, len(agent.resources))
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        configurator_based_on_new_config = GoCdConfigurator(FakeHostRestClient(configurator.config))
        self.assertEqual(3, len(configurator_based_on_new_config.agents[0].resources))

    def test_can_remove_agent(self):
        configurator = GoCdConfigurator(config('config-with-just-agents'))
        self.assertEqual(2, len(configurator.agents))
        configurator.ensure_removal_of_agent('go-agent-1')
        self.assertEqual(1, len(configurator.agents))
        self.assertEqual('go-agent-2', configurator.agents[0].hostname)

    def test_can_add_pipeline_group(self):
        configurator = GoCdConfigurator(empty_config())
        self.assertEqual(0, len(configurator.pipeline_groups))
        new_pipeline_group = configurator.ensure_pipeline_group("a_new_group")
        self.assertEqual(1, len(configurator.pipeline_groups))
        self.assertEqual(new_pipeline_group, configurator.pipeline_groups[-1])
        self.assertEqual("a_new_group", new_pipeline_group.name)

    def test_can_add_repository(self):
        configurator = GoCdConfigurator(empty_config())
        self.assertEqual(0, len(configurator.repositories))
        new_repository = configurator.ensure_repository("repo-one")
        self.assertEqual(1, len(configurator.repositories))
        self.assertEqual(new_repository, configurator.repositories[-1])
        self.assertEqual("repo-one", new_repository.name)

    def test_can_ensure_pipeline_group_exists(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        self.assertEqual(2, len(configurator.pipeline_groups))
        pre_existing_pipeline_group = configurator.ensure_pipeline_group('Second.Group')
        self.assertEqual(2, len(configurator.pipeline_groups))
        self.assertEqual('Second.Group', pre_existing_pipeline_group.name)

    def test_can_remove_all_pipeline_groups(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        s = configurator.remove_all_pipeline_groups()
        self.assertEqual(s, configurator)
        self.assertEqual(0, len(configurator.pipeline_groups))

    def test_can_remove_pipeline_group(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        s = configurator.ensure_removal_of_pipeline_group('P.Group')
        self.assertEqual(s, configurator)
        self.assertEqual(1, len(configurator.pipeline_groups))

    def test_can_ensure_removal_of_pipeline_group(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        configurator.ensure_removal_of_pipeline_group('pipeline-group-that-has-already-been-removed')
        self.assertEqual(2, len(configurator.pipeline_groups))

    def test_can_have_templates(self):
        templates = GoCdConfigurator(config('config-with-just-templates')).templates
        self.assertEqual(2, len(templates))
        self.assertEqual('api-component', templates[0].name)
        self.assertEqual('deploy-stack', templates[1].name)
        self.assertEqual('deploy-components', templates[1].stages[0].name)

    def test_can_have_no_templates(self):
        self.assertEqual(0, len(GoCdConfigurator(empty_config()).templates))

    def test_can_add_template(self):
        configurator = GoCdConfigurator(empty_config())
        template = configurator.ensure_template('foo')
        self.assertEqual(1, len(configurator.templates))
        self.assertEqual(template, configurator.templates[0])
        self.assertTrue(isinstance(configurator.templates[0], Pipeline), "so all methods that use to configure pipeline don't need to be tested for template")

    def test_can_ensure_template(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        template = configurator.ensure_template('deploy-stack')
        self.assertEqual('deploy-components', template.stages[0].name)

    def test_can_ensure_replacement_of_template(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        template = configurator.ensure_replacement_of_template('deploy-stack')
        self.assertEqual(0, len(template.stages))

    def test_can_remove_template(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        self.assertEqual(2, len(configurator.templates))
        configurator.ensure_removal_of_template('deploy-stack')
        self.assertEqual(1, len(configurator.templates))

    def test_if_remove_all_templates_also_remove_templates_element(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        self.assertEqual(2, len(configurator.templates))
        configurator.ensure_removal_of_template('api-component')
        configurator.ensure_removal_of_template('deploy-stack')
        self.assertEqual(0, len(configurator.templates))
        xml = configurator.config
        root = ET.fromstring(xml)
        self.assertEqual(['server'], [element.tag for element in root])

    def test_top_level_elements_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-agents-and-templates-but-without-pipelines'))
        configurator.ensure_pipeline_group("some_group").ensure_pipeline("some_pipeline")
        xml = configurator.config
        root = ET.fromstring(xml)
        self.assertEqual("pipelines", root[0].tag)
        self.assertEqual("templates", root[1].tag)
        self.assertEqual("agents", root[2].tag)

    def test_top_level_elements_with_environment_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-pipelines-environments-and-agents'))
        configurator.ensure_pipeline_group("P.Group").ensure_pipeline("some_pipeline")

        xml = configurator.config
        root = ET.fromstring(xml)
        self.assertEqual(['server', 'pipelines', 'environments', 'agents'], [element.tag for element in root])

    def test_top_level_elements_that_cannot_be_created_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-many-of-the-top-level-elements-that-cannot-be-added'))
        configurator.ensure_pipeline_group("P.Group").ensure_pipeline("some_pipeline")

        xml = configurator.config
        root = ET.fromstring(xml)
        self.assertEqual(['server', 'repositories', 'scms', 'pipelines', 'environments', 'agents'],
                         [element.tag for element in root])

    def test_elements_can_be_created_in_order_to_please_go(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline = configurator.ensure_pipeline_group("some_group").ensure_pipeline("some_pipeline")
        pipeline.ensure_parameters({'p': 'p'})
        pipeline.set_timer("some timer")
        pipeline.ensure_environment_variables({'pe': 'pe'})
        pipeline.set_git_url("gurl")
        stage = pipeline.ensure_stage("s")
        stage.ensure_environment_variables({'s': 's'})
        job = stage.ensure_job("j")
        job.ensure_environment_variables({'j': 'j'})
        job.ensure_task(ExecTask(['ls']))
        job.ensure_tab(Tab("n", "p"))
        job.ensure_resource("r")
        job.ensure_artifacts({Artifact.get_build_artifact('s', 'd')})

        xml = configurator.config
        pipeline_root = ET.fromstring(xml).find('pipelines').find('pipeline')
        self.assertEqual("params", pipeline_root[0].tag)
        self.assertEqual("timer", pipeline_root[1].tag)
        self.assertEqual("environmentvariables", pipeline_root[2].tag)
        self.assertEqual("materials", pipeline_root[3].tag)
        self.assertEqual("stage", pipeline_root[4].tag)

        self.__check_stage(pipeline_root)

    def test_elements_are_reordered_in_order_to_please_go(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline = configurator.ensure_pipeline_group("some_group").ensure_pipeline("some_pipeline")
        pipeline.set_git_url("gurl")
        pipeline.ensure_environment_variables({'pe': 'pe'})
        pipeline.set_timer("some timer")
        pipeline.ensure_parameters({'p': 'p'})

        self.__configure_stage(pipeline)
        self.__configure_stage(configurator.ensure_template('templ'))

        xml = configurator.config

        pipeline_root = ET.fromstring(xml).find('pipelines').find('pipeline')
        self.assertEqual("params", pipeline_root[0].tag)
        self.assertEqual("timer", pipeline_root[1].tag)
        self.assertEqual("environmentvariables", pipeline_root[2].tag)
        self.assertEqual("materials", pipeline_root[3].tag)
        self.assertEqual("stage", pipeline_root[4].tag)

        self.__check_stage(pipeline_root)

        template_root = ET.fromstring(xml).find('templates').find('pipeline')
        self.assertEqual("stage", template_root[0].tag)

        self.__check_stage(template_root)

    def __check_stage(self, pipeline_root):
        stage_root = pipeline_root.find('stage')
        self.assertEqual("environmentvariables", stage_root[0].tag)
        self.assertEqual("jobs", stage_root[1].tag)
        job_root = stage_root.find('jobs').find('job')
        self.assertEqual("environmentvariables", job_root[0].tag)
        self.assertEqual("tasks", job_root[1].tag)
        self.assertEqual("tabs", job_root[2].tag)
        self.assertEqual("resources", job_root[3].tag)
        self.assertEqual("artifacts", job_root[4].tag)

    def __configure_stage(self, pipeline):
        stage = pipeline.ensure_stage("s")
        job = stage.ensure_job("j")
        stage.ensure_environment_variables({'s': 's'})
        job.ensure_tab(Tab("n", "p"))
        job.ensure_artifacts({Artifact.get_build_artifact('s', 'd')})
        job.ensure_task(ExecTask(['ls']))
        job.ensure_resource("r")
        job.ensure_environment_variables({'j': 'j'})


class TestRepository(unittest.TestCase):
    def test_can_read_yum_repo_from_xml(self):
        configurator = GoCdConfigurator(config('config-with-pipeline-and-yum-repo'))
        self.assertEqual(len(configurator.repositories), 1)
        yum_repository = configurator.repositories[-1]
        self.assertEqual(yum_repository.name, 'ts-yum-repo')
        self.assertEqual(yum_repository.repo_url, 'http://yum-server/releases/component-name/')
        self.assertEqual(yum_repository.id, 'ee6a8a7b-96d0-452e-aa99-26e4af46d646')
        self.assertEqual(len(yum_repository.properties), 1)

        self.assertEqual(len(yum_repository.packages), 1)
        package = yum_repository.packages[-1]
        self.assertEqual(package.name ,"yum-component-name")
        self.assertEqual(package.id ,"eca7f187-73c2-4f62-971a-d15233937256")
        self.assertEqual(len(package.properties), 1)
        self.assertEqual(package.package_spec, 'component-name.*')

    def test_can_ensure_type_on_populated_repository(self):
        configurator = GoCdConfigurator(config('config-with-pipeline-and-yum-repo'))
        yum_repository = configurator.ensure_repository('ts-yum-repo')
        self.assertEqual(yum_repository.type, 'yum')
        p = yum_repository.ensure_type('yum', '1')
        self.assertEqual(p.attrib['id'], 'yum')
        self.assertEqual(p.attrib['version'], '1')
        self.assertEqual(p.tag, 'pluginConfiguration')

        prop = yum_repository.ensure_property('REPO_URL', 'http://yum-server/releases/component-name/')
        self.assertEqual(prop.key, 'REPO_URL')
        self.assertEqual(prop.value, 'http://yum-server/releases/component-name/')

    def test_can_ensure_type_on_empty_config(self):
        configurator = GoCdConfigurator(empty_config())
        yum_repository = configurator.ensure_repository('ts-yum-repo')
        self.assertIsNotNone(yum_repository.id, 'shoudl have random id')
        p = yum_repository.ensure_type('yum', '1')
        self.assertEqual(p.attrib['id'], 'yum')

        self.assertEqual(p.tag, 'pluginConfiguration')
        self.assertEqual(p.attrib['version'], '1')

    def test_can_ensure_property_on_empty_config(self):
        configurator = GoCdConfigurator(empty_config())
        yum_repository = configurator.ensure_repository('ts-yum-repo')
        prop = yum_repository.ensure_property('REPO_URL', 'http://yum-server/releases/component-name/')
        self.assertEqual(prop.key, 'REPO_URL')
        self.assertEqual(prop.value, 'http://yum-server/releases/component-name/')

    def test_can_ensure_package_on_repo_from_config(self):
        configurator = GoCdConfigurator(config('config-with-pipeline-and-yum-repo'))
        yum_repository = configurator.ensure_repository('ts-yum-repo')
        package = yum_repository.ensure_package('yum-component-name')

        self.assertEqual(package.id, 'eca7f187-73c2-4f62-971a-d15233937256')

        prop = package.ensure_property('PACKAGE_SPEC', 'component-name.*')
        self.assertEqual(prop.key, 'PACKAGE_SPEC')
        self.assertEqual(prop.value, 'component-name.*')

    def test_can_ensure_package_on_repo_from_empty_config(self):
        configurator = GoCdConfigurator(empty_config())
        yum_repository = configurator.ensure_repository('ts-yum-repo')
        package = yum_repository.ensure_package('yum-component-name')

        self.assertIsNotNone(package.id, 'should have a package id')

        prop = package.ensure_property('PACKAGE_SPEC', 'component-name.*')
        self.assertEqual(prop.key, 'PACKAGE_SPEC')
        self.assertEqual(prop.value, 'component-name.*')


def simplified(s):
    return s.strip().replace("\t", "").replace("\n", "").replace("\\", "").replace(" ", "")


def sneakily_converted_to_xml(pipeline):
    if pipeline.is_template:
        return ET.tostring(pipeline.element)
    else:
        return ET.tostring(pipeline.parent.element)


class TestReverseEngineering(unittest.TestCase):
    def check_round_trip_pipeline(self, configurator, before, show=False):
        reverse_engineered_python = configurator.as_python(before, with_save=False)
        if show:
            print('r' * 88)
            print(reverse_engineered_python)
        pipeline = "evaluation failed"
        template = "evaluation failed"

        # http://bugs.python.org/issue4831
        _locals = locals()
        exec(reverse_engineered_python, globals(), _locals)
        pipeline = _locals['pipeline']
        template = _locals['template']

        #exec(reverse_engineered_python.replace("from gomatic import *", "from gomatic.go_cd_configurator import *"))
        xml_before = sneakily_converted_to_xml(before)
        # noinspection PyTypeChecker
        xml_after = sneakily_converted_to_xml(pipeline)
        if show:
            print('b' * 88)
            print(prettify(xml_before))
            print('a' * 88)
            print(prettify(xml_after))
        self.assertEqual(xml_before, xml_after)

        if before.is_based_on_template:
            # noinspection PyTypeChecker
            self.assertEqual(sneakily_converted_to_xml(before.template), sneakily_converted_to_xml(template))

    def test_can_round_trip_simplest_pipeline(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_standard_label(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_default_label_template()
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_non_standard_label(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_label_template("non standard")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_automatic_pipeline_locking(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_automatic_pipeline_locking()
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_lock_behavior(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_lock_behavior("lockOnFailure")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_material(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").ensure_material(PipelineMaterial("p", "s", "m"))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_multiple_git_materials(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        before.ensure_material(GitMaterial("giturl1", "b", "m1"))
        before.ensure_material(GitMaterial("giturl2"))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_url(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_url("some git url")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_extras(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(
            GitMaterial("some git url",
                        branch="some branch",
                        material_name="some material name",
                        polling=False,
                        ignore_patterns={"excluded", "things"},
                        destination_directory='foo/bar'))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_branch_only(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(GitMaterial("some git url", branch="some branch"))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_material_only(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(GitMaterial("some git url", material_name="m name"))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_polling_only(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(GitMaterial("some git url", polling=False))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_ignore_patterns_only_ISSUE_4(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(GitMaterial("git url", ignore_patterns={"ex", "cluded"}))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_git_destination_directory_only(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_git_material(GitMaterial("git url", destination_directory='foo/bar'))
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_parameters(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").ensure_parameters({"p": "v"})
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_environment_variables(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").ensure_environment_variables({"p": "v"})
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_encrypted_environment_variables(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").ensure_encrypted_environment_variables({"p": "v"})
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_unencrypted_secure_environment_variables(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").ensure_unencrypted_secure_environment_variables({"p": "v"})
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_timer(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_timer("some timer")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_timer_only_on_changes(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_timer("some timer", only_on_changes=True)
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_stage_bits(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        before.ensure_stage("stage1").ensure_environment_variables({"k": "v"}).set_clean_working_dir().set_has_manual_approval().set_fetch_materials(False)
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_stages(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        before.ensure_stage("stage1")
        before.ensure_stage("stage2")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_job(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        before.ensure_stage("stage").ensure_job("job")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_job_bits(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        before.ensure_stage("stage").ensure_job("job") \
            .ensure_artifacts({Artifact.get_build_artifact("s", "d"), Artifact.get_test_artifact("sauce")}) \
            .ensure_environment_variables({"k": "v"}) \
            .ensure_resource("r") \
            .ensure_tab(Tab("n", "p")) \
            .set_timeout("23") \
            .set_runs_on_all_agents()
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_jobs(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        stage = before.ensure_stage("stage")
        stage.ensure_job("job1")
        stage.ensure_job("job2")
        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_tasks(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line")
        job = before.ensure_stage("stage").ensure_job("job")

        job.add_task(ExecTask(["one", "two"], working_dir="somewhere", runif="failed"))
        job.add_task(ExecTask(["one", "two"], working_dir="somewhere", runif="failed"))
        job.ensure_task(ExecTask(["one"], working_dir="somewhere else"))
        job.ensure_task(ExecTask(["two"], runif="any"))

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactFile('f'), runif="any"))
        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('d')))
        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('d'), dest="somewhere-else"))
        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('d'), dest="somewhere-else", runif="any"))

        job.ensure_task(RakeTask('t1', runif="any"))
        job.ensure_task(RakeTask('t2'))

        self.check_round_trip_pipeline(configurator, before)

    def test_can_round_trip_pipeline_base_on_template(self):
        configurator = GoCdConfigurator(empty_config())
        before = configurator.ensure_pipeline_group("group").ensure_pipeline("line").set_template_name("temple")
        configurator.ensure_template("temple").ensure_stage("stage").ensure_job("job")

        self.check_round_trip_pipeline(configurator, before)

    def test_can_reverse_engineer_pipeline(self):
        configurator = GoCdConfigurator(config('config-with-more-options-pipeline'))
        actual = configurator.as_python(more_options_pipeline(), with_save=False)
        expected = """#!/usr/bin/env python
from gomatic import *

configurator = GoCdConfigurator(FakeConfig(whatever))
pipeline = configurator\
	.ensure_pipeline_group("P.Group")\
	.ensure_replacement_of_pipeline("more-options")\
	.set_timer("0 15 22 * * ?")\
	.set_git_material(GitMaterial("git@bitbucket.org:springersbm/gomatic.git", branch="a-branch", material_name="some-material-name", polling=False))\
	.ensure_material(PipelineMaterial("pipeline2", "build")).ensure_environment_variables({'JAVA_HOME': '/opt/java/jdk-1.7'})\
	.ensure_parameters({'environment': 'qa'})
stage = pipeline.ensure_stage("earlyStage")
job = stage.ensure_job("earlyWorm").ensure_artifacts(set([BuildArtifact("scripts/*", "files"), BuildArtifact("target/universal/myapp*.zip", "artifacts"), TestArtifact("from", "to")])).set_runs_on_all_agents()
job.add_task(ExecTask(['ls']))
job.add_task(ExecTask(['bash', '-c', 'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"']))
stage = pipeline.ensure_stage("middleStage")
job = stage.ensure_job("middleJob")
stage = pipeline.ensure_stage("s1").set_fetch_materials(False)
job = stage.ensure_job("rake-job").ensure_artifacts({BuildArtifact("things/*")})
job.add_task(RakeTask("boo", "passed"))
job = stage.ensure_job("run-if-variants")
job.add_task(ExecTask(['t-passed']))
job.add_task(ExecTask(['t-none']))
job.add_task(ExecTask(['t-failed'], runif="failed"))
job.add_task(ExecTask(['t-any'], runif="any"))
job.add_task(ExecTask(['t-both'], runif="any"))
job = stage.ensure_job("variety-of-tasks")
job.add_task(RakeTask("sometarget", "passed"))
job.add_task(FetchArtifactTask("more-options", "earlyStage", "earlyWorm", FetchArtifactDir("sourceDir"), dest="destDir"))
job.add_task(FetchArtifactTask("more-options", "middleStage", "middleJob", FetchArtifactFile("someFile")))
job.add_task(ExecTask(['true']))
        """
        self.assertEqual(simplified(expected), simplified(actual))


class TestXmlFormatting(unittest.TestCase):
    def test_can_format_simple_xml(self):
        expected = '<?xml version="1.0" ?>\n<top>\n\t<middle>stuff</middle>\n</top>'
        non_formatted = "<top><middle>stuff</middle></top>"
        formatted = prettify(non_formatted)
        self.assertEqual(expected, formatted)

    def test_can_format_more_complicated_xml(self):
        expected = '<?xml version="1.0" ?>\n<top>\n\t<middle>\n\t\t<innermost>stuff</innermost>\n\t</middle>\n</top>'
        non_formatted = "<top><middle><innermost>stuff</innermost></middle></top>"
        formatted = prettify(non_formatted)
        self.assertEqual(expected, formatted)

    def test_can_format_actual_config(self):
        with open("test-data/config-unformatted.xml") as unformatted_xml:
            formatted = prettify(unformatted_xml.read())
        with open("test-data/config-formatted.xml") as formatted_xml:
            expected = formatted_xml.read()

        def head(s):
            return "\n".join(s.split('\n')[:10])

        self.assertEqual(expected, formatted, "expected=\n%s\n%s\nactual=\n%s" % (head(expected), "=" * 88, head(formatted)))

class TestArtifacts(unittest.TestCase):
    def test_renders_build_artifact_version_gocd_18_2_and_below_by_default(self):
        element = ET.Element('artifacts')
        artifact = BuildArtifact('src', 'dest')
        artifact.append_to(element)
        self.assertEqual(element[0].tag, 'artifact')
        self.assertEqual('type' in element[0].attrib, False)

    def test_renders_test_artifact_version_gocd_18_2_and_below_by_default(self):
        element = ET.Element('artifacts')
        artifact = TestArtifact('src', 'dest')
        artifact.append_to(element)
        self.assertEqual(element[0].tag, 'test')
        self.assertEqual('type' in element[0].attrib, False)

    def test_renders_build_artifact_version_gocd_18_3_and_above(self):
        element = ET.Element('artifacts')
        artifact = BuildArtifact('src', 'dest')
        artifact.append_to(element, gocd_18_3_and_above=True)
        self.assertEqual(element[0].tag, 'artifact')
        self.assertEqual(element[0].attrib['type'], 'build')

    def test_renders_test_artifact_version_gocd_18_3_and_above(self):
        element = ET.Element('artifacts')
        artifact = TestArtifact('src', 'dest')
        artifact.append_to(element, gocd_18_3_and_above=True)
        self.assertEqual(element[0].tag, 'artifact')
        self.assertEqual(element[0].attrib['type'], 'test')

    def test_can_go_from_xml_to_build_artifact_object_with_version_gocd_18_2_and_below(self):
        element = ET.Element('artifact')
        element.attrib['src'] = 'src'
        artifact = ArtifactFor(element)
        self.assertEqual(artifact._src, 'src')
        self.assertEqual(artifact._dest, None)
        self.assertEqual(artifact._type, 'build')

    def test_can_go_from_xml_to_test_artifact_object_with_version_gocd_18_2_and_below(self):
        element = ET.Element('test')
        element.attrib['src'] = 'src'
        artifact = ArtifactFor(element)
        self.assertEqual(artifact._src, 'src')
        self.assertEqual(artifact._dest, None)
        self.assertEqual(artifact._type, 'test')

    def test_can_go_from_xml_to_build_artifact_object_with_version_gocd_18_3_and_above(self):
        element = ET.Element('artifact')
        element.attrib['src'] = 'src'
        element.attrib['type'] = 'build'
        artifact = ArtifactFor(element)
        self.assertEqual(artifact._src, 'src')
        self.assertEqual(artifact._dest, None)
        self.assertEqual(artifact._type, 'build')

    def test_can_go_from_xml_to_test_artifact_object_with_version_gocd_18_3_and_above(self):
        element = ET.Element('artifact')
        element.attrib['src'] = 'src'
        element.attrib['type'] = 'test'
        artifact = ArtifactFor(element)
        self.assertEqual(artifact._src, 'src')
        self.assertEqual(artifact._dest, None)
        self.assertEqual(artifact._type, 'test')
