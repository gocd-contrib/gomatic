#!/usr/bin/env python

import unittest

from go_cd_configurator import *

empty_config_xml = """<?xml version="1.0" encoding="utf-8"?>
<cruise xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="cruise-config.xsd" schemaVersion="72">
  <server artifactsdir="artifacts" commandRepositoryLocation="default" serverId="96eca4bf-210e-499f-9dc9-0cefdae38d0c" />
</cruise>"""


class FakeResponse(object):
    def __init__(self, text):
        self.text = text
        self.headers = {'x-cruise-config-md5': '42'}


class FakeHostRestClient:
    def __init__(self, config_string, thing_to_recreate_itself=None):
        self.config_string = config_string
        self.thing_to_recreate_itself = thing_to_recreate_itself

    def __repr__(self):
        if self.thing_to_recreate_itself is None:
            return 'FakeConfig(whatever)'
        else:
            return self.thing_to_recreate_itself

    def get(self, path):
        # sorry for the duplication/shared knowledge of code but this is easiest way to test
        # what we want in a controlled way
        if path == "/go/admin/restful/configuration/file/GET/xml":
            return FakeResponse(self.config_string)
        raise RuntimeError("not expecting to be asked for anything else")


def config(config_name):
    return FakeHostRestClient(open('test-data/' + config_name + '.xml').read())


def empty_config():
    return FakeHostRestClient(empty_config_xml, "empty_config()")


def find_with_matching_name(things, name):
    return [thing for thing in things if thing.name() == name]


def standard_pipeline_group():
    return GoCdConfigurator(config('config-with-typical-pipeline')).ensure_pipeline_group('P.Group')


def typical_pipeline():
    return standard_pipeline_group().find_pipeline('typical')


def more_options_pipeline():
    return GoCdConfigurator(config('config-with-more-options-pipeline')).ensure_pipeline_group('P.Group').find_pipeline('more-options')


def empty_pipeline():
    return GoCdConfigurator(empty_config()).ensure_pipeline_group("pg").ensure_pipeline("pl").set_git_url("gurl")


def empty_stage():
    return empty_pipeline().ensure_stage("deploy-to-dev")


class TestAgents(unittest.TestCase):
    def _agents_from_config(self):
        return GoCdConfigurator(config('config-with-just-agents')).agents()

    def test_could_have_no_agents(self):
        agents = GoCdConfigurator(empty_config()).agents()
        self.assertEquals(0, len(agents))

    def test_agents_have_resources(self):
        agents = self._agents_from_config()
        self.assertEquals(2, len(agents))
        self.assertEquals({'a-resource', 'b-resource'}, agents[0].resources())

    def test_agents_have_names(self):
        agents = self._agents_from_config()
        self.assertEquals('go-agent-1', agents[0].hostname())
        self.assertEquals('go-agent-2', agents[1].hostname())

    def test_agent_could_have_no_resources(self):
        agents = self._agents_from_config()
        self.assertEquals(0, len(agents[1].resources()))

    def test_can_add_resource_to_agent_with_no_resources(self):
        agent = self._agents_from_config()[1]
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        self.assertEquals(1, len(agent.resources()))

    def test_can_add_resource_to_agent(self):
        agent = self._agents_from_config()[0]
        self.assertEquals(2, len(agent.resources()))
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        self.assertEquals(3, len(agent.resources()))


class TestJobs(unittest.TestCase):
    def test_jobs_have_resources(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        resources = job.resources()
        self.assertEquals(1, len(resources))
        self.assertEquals({'a-resource'}, resources)

    def test_job_has_nice_tostring(self):
        job = typical_pipeline().stages()[0].jobs()[0]
        self.assertEquals("Job('compile', [ExecTask(['make', 'options', 'source code'])])", str(job))

    def test_jobs_can_have_timeout(self):
        job = typical_pipeline().ensure_stage("deploy").ensure_job("upload")
        self.assertEquals(True, job.has_timeout())
        self.assertEquals('20', job.timeout())

    def test_can_set_timeout(self):
        job = empty_stage().ensure_job("j")
        j = job.set_timeout("42")
        self.assertEquals(j, job)
        self.assertEquals(True, job.has_timeout())
        self.assertEquals('42', job.timeout())

    def test_jobs_do_not_have_to_have_timeout(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        self.assertEquals(False, job.has_timeout())
        try:
            job.timeout()
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_jobs_can_run_on_all_agents(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        self.assertEquals(True, job.runs_on_all_agents())

    def test_jobs_do_not_have_to_run_on_all_agents(self):
        job = typical_pipeline().ensure_stage("build").ensure_job("compile")
        self.assertEquals(False, job.runs_on_all_agents())

    def test_jobs_can_be_made_to_run_on_all_agents(self):
        job = typical_pipeline().ensure_stage("build").ensure_job("compile")
        j = job.set_runs_on_all_agents()
        self.assertEquals(j, job)
        self.assertEquals(True, job.runs_on_all_agents())

    def test_can_ensure_job_has_resource(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        j = job.ensure_resource('moo')
        self.assertEquals(j, job)
        self.assertEquals(2, len(job.resources()))
        self.assertEquals({'a-resource', 'moo'}, job.resources())

    def test_jobs_have_artifacts(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        artifacts = job.artifacts()
        self.assertEquals({
                              BuildArtifact("target/universal/myapp*.zip", "artifacts"),
                              BuildArtifact("scripts/*", "files"),
                              TestArtifact("from", "to")},
                          artifacts)

    def test_artifacts_might_have_no_dest(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("rake-job")
        artifacts = job.artifacts()
        self.assertEquals(1, len(artifacts))
        self.assertEquals({BuildArtifact("things/*")}, artifacts)

    def test_can_add_build_artifacts_to_job(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        job_with_artifacts = job.ensure_artifacts({
            BuildArtifact("a1", "artifacts"),
            BuildArtifact("a2", "others")})
        self.assertEquals(job, job_with_artifacts)
        artifacts = job.artifacts()
        self.assertEquals(5, len(artifacts))
        self.assertTrue({BuildArtifact("a1", "artifacts"), BuildArtifact("a2", "others")}.issubset(artifacts))

    def test_can_add_test_artifacts_to_job(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        job_with_artifacts = job.ensure_artifacts({
            TestArtifact("a1"),
            TestArtifact("a2")})
        self.assertEquals(job, job_with_artifacts)
        artifacts = job.artifacts()
        self.assertEquals(5, len(artifacts))
        self.assertTrue({TestArtifact("a1"), TestArtifact("a2")}.issubset(artifacts))

    def test_can_ensure_artifacts(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")

        job.ensure_artifacts({
            TestArtifact("from", "to"),
            BuildArtifact("target/universal/myapp*.zip", "somewhereElse"),
            TestArtifact("another", "with dest"),
            BuildArtifact("target/universal/myapp*.zip", "artifacts")})
        self.assertEquals({
                              BuildArtifact("target/universal/myapp*.zip", "artifacts"),
                              BuildArtifact("scripts/*", "files"),
                              TestArtifact("from", "to"),
                              BuildArtifact("target/universal/myapp*.zip", "somewhereElse"),
                              TestArtifact("another", "with dest")
                          },
                          job.artifacts())

    def test_jobs_have_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").jobs()[2]
        tasks = job.tasks()
        self.assertEquals(4, len(tasks))
        self.assertEquals('rake', tasks[0].type())
        self.assertEquals('sometarget', tasks[0].target())
        self.assertEquals('passed', tasks[0].runif())

        self.assertEquals('fetchartifact', tasks[1].type())
        self.assertEquals('more-options', tasks[1].pipeline())
        self.assertEquals('earlyStage', tasks[1].stage())
        self.assertEquals('earlyWorm', tasks[1].job())
        self.assertEquals(FetchArtifactDir('sourceDir'), tasks[1].src())
        self.assertEquals('destDir', tasks[1].dest())
        self.assertEquals('passed', tasks[1].runif())

    def test_runif_defaults_to_passed(self):
        pipeline = typical_pipeline()
        tasks = pipeline.ensure_stage("build").ensure_job("compile").tasks()
        self.assertEquals("passed", tasks[0].runif())

    def test_jobs_can_have_rake_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").jobs()[0]
        tasks = job.tasks()
        self.assertEquals(1, len(tasks))
        self.assertEquals('rake', tasks[0].type())
        self.assertEquals("boo", tasks[0].target())

    def test_can_ensure_rake_task(self):
        job = more_options_pipeline().ensure_stage("s1").jobs()[0]
        job.ensure_task(RakeTask("boo"))
        self.assertEquals(1, len(job.tasks()))

    def test_can_add_rake_task(self):
        job = more_options_pipeline().ensure_stage("s1").jobs()[0]
        job.ensure_task(RakeTask("another"))
        self.assertEquals(2, len(job.tasks()))
        self.assertEquals("another", job.tasks()[1].target())

    def test_can_add_exec_task_with_runif(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir', "failed"))
        self.assertEquals(2, len(job.tasks()))
        task = job.tasks()[1]
        self.assertEquals(task, added_task)
        self.assertEquals(['ls', '-la'], task.command_and_args())
        self.assertEquals('some/dir', task.working_dir())
        self.assertEquals('failed', task.runif())

    def test_can_add_exec_task(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir'))
        self.assertEquals(2, len(job.tasks()))
        task = job.tasks()[1]
        self.assertEquals(task, added_task)
        self.assertEquals(['ls', '-la'], task.command_and_args())
        self.assertEquals('some/dir', task.working_dir())

    def test_can_ensure_exec_task(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        t1 = job.ensure_task(ExecTask(['ls', '-la'], 'some/dir'))
        t2 = job.ensure_task(ExecTask(['make', 'options', 'source code']))
        job.ensure_task(ExecTask(['ls', '-la'], 'some/otherdir'))
        job.ensure_task(ExecTask(['ls', '-la'], 'some/dir'))
        self.assertEquals(3, len(job.tasks()))

        self.assertEquals(t2, job.tasks()[0])
        self.assertEquals(['make', 'options', 'source code'], (job.tasks()[0]).command_and_args())

        self.assertEquals(t1, job.tasks()[1])
        self.assertEquals(['ls', '-la'], (job.tasks()[1]).command_and_args())
        self.assertEquals('some/dir', (job.tasks()[1]).working_dir())

        self.assertEquals(['ls', '-la'], (job.tasks()[2]).command_and_args())
        self.assertEquals('some/otherdir', (job.tasks()[2]).working_dir())

    def test_exec_task_args_are_unescaped_as_appropriate(self):
        job = more_options_pipeline().ensure_stage("earlyStage").ensure_job("earlyWorm")
        task = job.tasks()[1]
        self.assertEquals(["bash", "-c",
                           'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"'],
                          task.command_and_args())

    def test_exec_task_args_are_escaped_as_appropriate(self):
        job = empty_stage().ensure_job("j")
        task = job.add_task(ExecTask(["bash", "-c",
                                      'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"']))
        self.assertEquals(["bash", "-c",
                           'curl "http://domain.com/service/check?target=one+two+three&key=2714_beta%40domain.com"'],
                          task.command_and_args())

    def test_can_have_no_tasks(self):
        self.assertEquals(0, len(empty_stage().ensure_job("empty_job").tasks()))

    def test_can_add_fetch_artifact_task_to_job(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        added_task = job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('d'), runif="any"))
        self.assertEquals(2, len(job.tasks()))
        task = job.tasks()[1]
        self.assertEquals(added_task, task)
        self.assertEquals('p', task.pipeline())
        self.assertEquals('s', task.stage())
        self.assertEquals('j', task.job())
        self.assertEquals(FetchArtifactDir('d'), task.src())
        self.assertEquals('any', task.runif())

    def test_fetch_artifact_task_can_have_src_file_rather_than_src_dir(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("variety-of-tasks")
        tasks = job.tasks()

        self.assertEquals(4, len(tasks))
        self.assertEquals('more-options', tasks[1].pipeline())
        self.assertEquals('earlyStage', tasks[1].stage())
        self.assertEquals('earlyWorm', tasks[1].job())
        self.assertEquals(FetchArtifactFile('someFile'), tasks[2].src())
        self.assertEquals('passed', tasks[1].runif())
        self.assertEquals(['true'], tasks[3].command_and_args())

    def test_fetch_artifact_task_can_have_dest(self):
        pipeline = more_options_pipeline()
        job = pipeline.ensure_stage("s1").ensure_job("variety-of-tasks")
        tasks = job.tasks()
        self.assertEquals(FetchArtifactTask("more-options",
                                            "earlyStage",
                                            "earlyWorm",
                                            FetchArtifactDir("sourceDir"),
                                            dest="destDir"),
                          tasks[1])

    def test_can_ensure_fetch_artifact_tasks(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("variety-of-tasks")
        job.ensure_task(FetchArtifactTask("more-options", "middleStage", "middleJob", FetchArtifactFile("someFile")))
        first_added_task = job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        self.assertEquals(5, len(job.tasks()))

        self.assertEquals(first_added_task, job.tasks()[4])

        self.assertEquals('p', (job.tasks()[4]).pipeline())
        self.assertEquals('s', (job.tasks()[4]).stage())
        self.assertEquals('j', (job.tasks()[4]).job())
        self.assertEquals(FetchArtifactDir('dir'), (job.tasks()[4]).src())
        self.assertEquals('passed', (job.tasks()[4]).runif())

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactFile('f')))
        self.assertEquals(FetchArtifactFile('f'), (job.tasks()[5]).src())

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir'), dest="somedest"))
        self.assertEquals("somedest", (job.tasks()[6]).dest())

        job.ensure_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir'), runif="failed"))
        self.assertEquals('failed', (job.tasks()[7]).runif())

    def test_tasks_run_if_defaults_to_passed(self):
        job = empty_stage().ensure_job("j")
        job.add_task(ExecTask(['ls', '-la'], 'some/dir'))
        job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        job.add_task(RakeTask('x'))
        self.assertEquals('passed', (job.tasks()[0]).runif())
        self.assertEquals('passed', (job.tasks()[1]).runif())
        self.assertEquals('passed', (job.tasks()[2]).runif())

    def test_tasks_run_if_variants(self):
        job = more_options_pipeline().ensure_stage("s1").ensure_job("run-if-variants")
        tasks = job.tasks()
        self.assertEquals('t-passed', tasks[0].command_and_args()[0])
        self.assertEquals('passed', tasks[0].runif())

        self.assertEquals('t-none', tasks[1].command_and_args()[0])
        self.assertEquals('passed', tasks[1].runif())

        self.assertEquals('t-failed', tasks[2].command_and_args()[0])
        self.assertEquals('failed', tasks[2].runif())

        self.assertEquals('t-any', tasks[3].command_and_args()[0])
        self.assertEquals('any', tasks[3].runif())

        self.assertEquals('t-both', tasks[4].command_and_args()[0])
        self.assertEquals('any', tasks[4].runif())

    def test_cannot_set_runif_to_random_things(self):
        try:
            ExecTask(['x'], runif='whatever')
            self.fail("should have thrown exception")
        except RuntimeError as e:
            self.assertTrue(e.message.count("whatever") > 0)

    def test_can_set_runif_to_particular_values(self):
        self.assertEquals('passed', ExecTask(['x'], runif='passed').runif())
        self.assertEquals('failed', ExecTask(['x'], runif='failed').runif())
        self.assertEquals('any', ExecTask(['x'], runif='any').runif())

    def test_tasks_dest_defaults_to_none(self):  # TODO: maybe None could be avoided
        job = empty_stage().ensure_job("j")
        job.add_task(FetchArtifactTask('p', 's', 'j', FetchArtifactDir('dir')))
        self.assertEquals(None, (job.tasks()[0]).dest())

    def test_can_add_exec_task_to_empty_job(self):
        job = empty_stage().ensure_job("j")
        added_task = job.add_task(ExecTask(['ls', '-la'], 'some/dir', "any"))
        self.assertEquals(1, len(job.tasks()))
        task = job.tasks()[0]
        self.assertEquals(task, added_task)
        self.assertEquals(['ls', '-la'], task.command_and_args())
        self.assertEquals('some/dir', task.working_dir())
        self.assertEquals('any', task.runif())

    def test_can_remove_all_tasks(self):
        stages = typical_pipeline().stages()
        job = stages[0].jobs()[0]
        self.assertEquals(1, len(job.tasks()))
        j = job.without_any_tasks()
        self.assertEquals(j, job)
        self.assertEquals(0, len(job.tasks()))

    def test_can_add_environment_variables(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.ensure_environment_variables({"new": "one"})
        self.assertEquals(j, job)
        self.assertEquals({"CF_COLOR": "false", "new": "one"}, job.environment_variables())

    def test_environment_variables_get_added_in_sorted_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        job = go_cd_configurator\
            .ensure_pipeline_group('P.Group')\
            .ensure_pipeline('P.Name') \
            .ensure_stage("build") \
            .ensure_job("compile")

        job.ensure_environment_variables({"ant": "a", "badger": "a", "zebra": "a"})

        xml = parseString(go_cd_configurator.config())
        names = [e.getAttribute('name') for e in xml.getElementsByTagName('variable')]
        self.assertEquals([u'ant', u'badger', u'zebra'], names)

    def test_encrypted_environment_variables_get_added_in_sorted_order_to_reduce_config_thrash(self):
        go_cd_configurator = GoCdConfigurator(empty_config())

        pipeline = go_cd_configurator \
            .ensure_pipeline_group('P.Group') \
            .ensure_pipeline('P.Name')

        pipeline.ensure_encrypted_environment_variables({"ant": "a", "badger": "a", "zebra": "a"})

        xml = parseString(go_cd_configurator.config())
        names = [e.getAttribute('name') for e in xml.getElementsByTagName('variable')]
        self.assertEquals([u'ant', u'badger', u'zebra'], names)

    def test_can_remove_all_environment_variables(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.without_any_environment_variables()
        self.assertEquals(j, job)
        self.assertEquals({}, job.environment_variables())

    def test_job_can_haveTabs(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        self.assertEquals([Tab("Time_Taken", "artifacts/test-run-times.html")], job.tabs())

    def test_can_addTab(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        j = job.ensure_tab(Tab("n", "p"))
        self.assertEquals(j, job)
        self.assertEquals([Tab("Time_Taken", "artifacts/test-run-times.html"), Tab("n", "p")], job.tabs())

    def test_can_ensure_tab(self):
        job = typical_pipeline() \
            .ensure_stage("build") \
            .ensure_job("compile")
        job.ensure_tab(Tab("Time_Taken", "artifacts/test-run-times.html"))
        self.assertEquals([Tab("Time_Taken", "artifacts/test-run-times.html")], job.tabs())


class TestStages(unittest.TestCase):
    def test_pipelines_have_stages(self):
        self.assertEquals(2, len(typical_pipeline().stages()))

    def test_stages_have_names(self):
        stages = typical_pipeline().stages()
        self.assertEquals('build', stages[0].name())
        self.assertEquals('deploy', stages[1].name())

    def test_stages_can_have_manual_approval(self):
        self.assertEquals(False, typical_pipeline().stages()[0].has_manual_approval())
        self.assertEquals(True, typical_pipeline().stages()[1].has_manual_approval())

    def test_can_set_manual_approval(self):
        stage = typical_pipeline().stages()[0]
        s = stage.set_has_manual_approval()
        self.assertEquals(s, stage)
        self.assertEquals(True, stage.has_manual_approval())

    def test_stages_have_fetch_materials_flag(self):
        stage = typical_pipeline().ensure_stage("build")
        self.assertEquals(True, stage.fetch_materials())
        stage = more_options_pipeline().ensure_stage("s1")
        self.assertEquals(False, stage.fetch_materials())

    def test_can_set_fetch_materials_flag(self):
        stage = typical_pipeline().ensure_stage("build")
        s = stage.set_fetch_materials(False)
        self.assertEquals(s, stage)
        self.assertEquals(False, stage.fetch_materials())
        stage = more_options_pipeline().ensure_stage("s1")
        stage.set_fetch_materials(True)
        self.assertEquals(True, stage.fetch_materials())

    def test_stages_have_jobs(self):
        stages = typical_pipeline().stages()
        jobs = stages[0].jobs()
        self.assertEquals(1, len(jobs))
        self.assertEquals('compile', jobs[0].name())

    def test_can_add_job(self):
        stage = typical_pipeline().ensure_stage("deploy")
        self.assertEquals(1, len(stage.jobs()))
        ensured_job = stage.ensure_job("new-job")
        self.assertEquals(2, len(stage.jobs()))
        self.assertEquals(ensured_job, stage.jobs()[1])
        self.assertEquals("new-job", stage.jobs()[1].name())

    def test_can_add_job_to_empty_stage(self):
        stage = empty_stage()
        self.assertEquals(0, len(stage.jobs()))
        ensured_job = stage.ensure_job("new-job")
        self.assertEquals(1, len(stage.jobs()))
        self.assertEquals(ensured_job, stage.jobs()[0])
        self.assertEquals("new-job", stage.jobs()[0].name())

    def test_can_ensure_job_exists(self):
        stage = typical_pipeline().ensure_stage("deploy")
        self.assertEquals(1, len(stage.jobs()))
        ensured_job = stage.ensure_job("upload")
        self.assertEquals(1, len(stage.jobs()))
        self.assertEquals("upload", ensured_job.name())

    def test_can_set_environment_variables(self):
        stage = typical_pipeline().ensure_stage("deploy")
        s = stage.ensure_environment_variables({"new": "one"})
        self.assertEquals(s, stage)
        self.assertEquals({"BASE_URL": "http://myurl", "new": "one"}, stage.environment_variables())

    def test_can_remove_all_environment_variables(self):
        stage = typical_pipeline().ensure_stage("deploy")
        s = stage.without_any_environment_variables()
        self.assertEquals(s, stage)
        self.assertEquals({}, stage.environment_variables())


class TestPipeline(unittest.TestCase):
    def test_pipelines_have_names(self):
        pipeline = typical_pipeline()
        self.assertEquals('typical', pipeline.name())

    def test_can_add_stage(self):
        pipeline = empty_pipeline()
        self.assertEquals(0, len(pipeline.stages()))
        new_stage = pipeline.ensure_stage("some_stage")
        self.assertEquals(1, len(pipeline.stages()))
        self.assertEquals(new_stage, pipeline.stages()[0])
        self.assertEquals("some_stage", new_stage.name())

    def test_can_ensure_stage(self):
        pipeline = typical_pipeline()
        self.assertEquals(2, len(pipeline.stages()))
        ensured_stage = pipeline.ensure_stage("deploy")
        self.assertEquals(2, len(pipeline.stages()))
        self.assertEquals("deploy", ensured_stage.name())

    def test_can_remove_stage(self):
        pipeline = typical_pipeline()
        self.assertEquals(2, len(pipeline.stages()))
        p = pipeline.ensure_removal_of_stage("deploy")
        self.assertEquals(p, pipeline)
        self.assertEquals(1, len(pipeline.stages()))
        self.assertEquals(0, len([s for s in pipeline.stages() if s.name() == "deploy"]))

    def test_can_ensure_removal_of_stage(self):
        pipeline = typical_pipeline()
        self.assertEquals(2, len(pipeline.stages()))
        pipeline.ensure_removal_of_stage("stage-that-has-already-been-deleted")
        self.assertEquals(2, len(pipeline.stages()))

    def test_can_ensure_initial_stage(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("first")
        self.assertEquals(stage, pipeline.stages()[0])
        self.assertEquals(3, len(pipeline.stages()))

    def test_can_ensure_initial_stage_if_already_exists_as_initial(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("build")
        self.assertEquals(stage, pipeline.stages()[0])
        self.assertEquals(2, len(pipeline.stages()))

    def test_can_ensure_initial_stage_if_already_exists(self):
        pipeline = typical_pipeline()
        stage = pipeline.ensure_initial_stage("deploy")
        self.assertEquals(stage, pipeline.stages()[0])
        self.assertEquals("build", pipeline.stages()[1].name())
        self.assertEquals(2, len(pipeline.stages()))

    def test_can_set_stage_clean_policy(self):
        pipeline = empty_pipeline()
        stage1 = pipeline.ensure_stage("some_stage1").set_clean_working_dir()
        stage2 = pipeline.ensure_stage("some_stage2")
        self.assertEquals(True, pipeline.stages()[0].clean_working_dir())
        self.assertEquals(True, stage1.clean_working_dir())
        self.assertEquals(False, pipeline.stages()[1].clean_working_dir())
        self.assertEquals(False, stage2.clean_working_dir())

    def test_pipelines_can_have_git_urls(self):
        pipeline = typical_pipeline()
        self.assertEquals("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url())

    def test_git_is_polled_by_default(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.set_git_url("some git url")
        self.assertEquals(True, pipeline.git_material().polling())

    def test_pipelines_can_have_git_material_with_material_name(self):
        pipeline = more_options_pipeline()
        self.assertEquals("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url())
        self.assertEquals("some-material-name", pipeline.git_material().material_name())

    def test_git_material_can_ignore_sources(self):
        pipeline = GoCdConfigurator(config('config-with-source-exclusions')).ensure_pipeline_group("P.Group").find_pipeline("with-exclusions")
        self.assertEquals({"excluded-folder", "another-excluded-folder"}, pipeline.git_material().ignore_patterns())

    def test_can_set_pipeline_git_url(self):
        pipeline = typical_pipeline()
        p = pipeline.set_git_url("git@bitbucket.org:springersbm/changed.git")
        self.assertEquals(p, pipeline)
        self.assertEquals("git@bitbucket.org:springersbm/changed.git", pipeline.git_url())
        self.assertEquals('master', pipeline.git_branch())

    def test_can_set_pipeline_git_url_with_options(self):
        pipeline = typical_pipeline()
        p = pipeline.set_git_material(GitMaterial(
            "git@bitbucket.org:springersbm/changed.git",
            branch="branch",
            material_name="material-name",
            ignore_patterns={"ignoreMe", "ignoreThisToo"},
            polling=False))
        self.assertEquals(p, pipeline)
        self.assertEquals("branch", pipeline.git_branch())
        self.assertEquals("material-name", pipeline.git_material().material_name())
        self.assertEquals({"ignoreMe", "ignoreThisToo"}, pipeline.git_material().ignore_patterns())
        self.assertFalse(pipeline.git_material().polling(), "git polling")

    def test_throws_exception_if_no_git_url(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        self.assertEquals(False, pipeline.has_single_git_material())
        try:
            pipeline.git_url()
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_git_url_throws_exception_if_multiple_git_materials(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/one.git"))
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/two.git"))
        self.assertEquals(False, pipeline.has_single_git_material())
        try:
            pipeline.git_url()
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
        self.assertEquals(p, pipeline)
        self.assertEquals("git@bitbucket.org:springersbm/changed.git", pipeline.git_url())

    def test_can_ensure_git_material(self):
        pipeline = typical_pipeline()
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/gomatic.git"))
        self.assertEquals("git@bitbucket.org:springersbm/gomatic.git", pipeline.git_url())
        self.assertEquals([GitMaterial("git@bitbucket.org:springersbm/gomatic.git")], pipeline.materials())

    def test_can_have_multiple_git_materials(self):
        pipeline = typical_pipeline()
        pipeline.ensure_material(GitMaterial("git@bitbucket.org:springersbm/changed.git"))
        self.assertEquals([GitMaterial("git@bitbucket.org:springersbm/gomatic.git"), GitMaterial("git@bitbucket.org:springersbm/changed.git")],
                          pipeline.materials())

    def test_pipelines_can_have_pipeline_materials(self):
        pipeline = more_options_pipeline()
        self.assertEquals(2, len(pipeline.materials()))
        self.assertEquals(GitMaterial('git@bitbucket.org:springersbm/gomatic.git', branch="a-branch", material_name="some-material-name", polling=False),
                          pipeline.materials()[0])

    def test_pipelines_can_have_more_complicated_pipeline_materials(self):
        pipeline = more_options_pipeline()
        self.assertEquals(2, len(pipeline.materials()))
        self.assertEquals(True, pipeline.materials()[0].is_git())
        self.assertEquals(PipelineMaterial('pipeline2', 'build'), pipeline.materials()[1])

    def test_pipelines_can_have_no_materials(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        self.assertEquals(0, len(pipeline.materials()))

    def test_can_add_pipeline_material(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        p = pipeline.ensure_material(PipelineMaterial('deploy-qa', 'baseline-user-data'))
        self.assertEquals(p, pipeline)
        self.assertEquals(PipelineMaterial('deploy-qa', 'baseline-user-data'), pipeline.materials()[0])

    def test_can_add_more_complicated_pipeline_material(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group("g").ensure_pipeline("p")
        p = pipeline.ensure_material(PipelineMaterial('p', 's', 'm'))
        self.assertEquals(p, pipeline)
        self.assertEquals(PipelineMaterial('p', 's', 'm'), pipeline.materials()[0])

    def test_can_ensure_pipeline_material(self):
        pipeline = more_options_pipeline()
        self.assertEquals(2, len(pipeline.materials()))
        pipeline.ensure_material(PipelineMaterial('pipeline2', 'build'))
        self.assertEquals(2, len(pipeline.materials()))

    def test_materials_are_sorted(self):
        go_cd_configurator = GoCdConfigurator(empty_config())
        pipeline = go_cd_configurator.ensure_pipeline_group("g").ensure_pipeline("p")
        pipeline.ensure_material(PipelineMaterial('zeta', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/zebra.git'))
        pipeline.ensure_material(PipelineMaterial('alpha', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/art.git'))
        pipeline.ensure_material(PipelineMaterial('theta', 'build'))
        pipeline.ensure_material(GitMaterial('git@bitbucket.org:springersbm/this.git'))

        xml = parseString(go_cd_configurator.config())
        materials = xml.getElementsByTagName('materials')[0].childNodes
        self.assertEquals('git', materials[0].tagName)
        self.assertEquals('git', materials[1].tagName)
        self.assertEquals('git', materials[2].tagName)
        self.assertEquals('pipeline', materials[3].tagName)
        self.assertEquals('pipeline', materials[4].tagName)
        self.assertEquals('pipeline', materials[5].tagName)

        self.assertEquals('git@bitbucket.org:springersbm/art.git', materials[0].attributes['url'].value)
        self.assertEquals('git@bitbucket.org:springersbm/this.git', materials[1].attributes['url'].value)
        self.assertEquals('git@bitbucket.org:springersbm/zebra.git', materials[2].attributes['url'].value)
        self.assertEquals('alpha', materials[3].attributes['pipelineName'].value)
        self.assertEquals('theta', materials[4].attributes['pipelineName'].value)
        self.assertEquals('zeta', materials[5].attributes['pipelineName'].value)

    def test_can_set_pipeline_git_url_for_new_pipeline(self):
        pipeline_group = standard_pipeline_group()
        new_pipeline = pipeline_group.ensure_pipeline("some_name")
        new_pipeline.set_git_url("git@bitbucket.org:springersbm/changed.git")
        self.assertEquals("git@bitbucket.org:springersbm/changed.git", new_pipeline.git_url())

    def test_pipelines_do_not_have_to_be_based_on_template(self):
        pipeline = more_options_pipeline()
        self.assertFalse(pipeline.is_based_on_template())

    def test_pipelines_can_be_based_on_template(self):
        pipeline = GoCdConfigurator(config('pipeline-based-on-template')).ensure_pipeline_group('defaultGroup').find_pipeline('siberian')
        assert isinstance(pipeline, Pipeline)
        self.assertTrue(pipeline.is_based_on_template())
        template = GoCdConfigurator(config('pipeline-based-on-template')).templates()[0]
        self.assertEquals(template, pipeline.template())

    def test_pipelines_can_be_created_based_on_template(self):
        configurator = GoCdConfigurator(empty_config())
        configurator.ensure_template('temple').ensure_stage('s').ensure_job('j')
        pipeline = configurator.ensure_pipeline_group("g").ensure_pipeline('p').set_template_name('temple')
        self.assertEquals('temple', pipeline.template().name())

    def test_pipelines_have_environment_variables(self):
        pipeline = typical_pipeline()
        self.assertEquals({"JAVA_HOME": "/opt/java/jdk-1.8"}, pipeline.environment_variables())

    def test_pipelines_have_encrypted_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-encrypted-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        self.assertEquals({"MY_SECURE_PASSWORD": "yq5qqPrrD9/htfwTWMYqGQ=="}, pipeline.encrypted_environment_variables())

    def test_pipelines_have_unencrypted_secure_environment_variables(self):
        pipeline = GoCdConfigurator(config('config-with-unencrypted-secure-variable')).ensure_pipeline_group("defaultGroup").find_pipeline("example")
        self.assertEquals({"MY_SECURE_PASSWORD": "hunter2"}, pipeline.unencrypted_secure_environment_variables())

    def test_can_add_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        pipeline.ensure_environment_variables({"new": "one", "again": "two"})
        self.assertEquals({"new": "one", "again": "two"}, pipeline.environment_variables())

    def test_can_add_encrypted_secure_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        pipeline.ensure_encrypted_environment_variables({"new": "one", "again": "two"})
        self.assertEquals({"new": "one", "again": "two"}, pipeline.encrypted_environment_variables())

    def test_can_add_unencrypted_secure_environment_variables_to_pipeline(self):
        pipeline = empty_pipeline()
        pipeline.ensure_unencrypted_secure_environment_variables({"new": "one", "again": "two"})
        self.assertEquals({"new": "one", "again": "two"}, pipeline.unencrypted_secure_environment_variables())

    def test_can_add_environment_variables_to_new_pipeline(self):
        pipeline = typical_pipeline()
        pipeline.ensure_environment_variables({"new": "one"})
        self.assertEquals({"JAVA_HOME": "/opt/java/jdk-1.8", "new": "one"}, pipeline.environment_variables())

    def test_can_modify_environment_variables_of_pipeline(self):
        pipeline = typical_pipeline()
        pipeline.ensure_environment_variables({"new": "one", "JAVA_HOME": "/opt/java/jdk-1.1"})
        self.assertEquals({"JAVA_HOME": "/opt/java/jdk-1.1", "new": "one"}, pipeline.environment_variables())

    def test_can_remove_all_environment_variables(self):
        pipeline = typical_pipeline()
        p = pipeline.without_any_environment_variables()
        self.assertEquals(p, pipeline)
        self.assertEquals({}, pipeline.environment_variables())

    def test_can_remove_specific_environment_variable(self):
        pipeline = empty_pipeline()
        pipeline.ensure_encrypted_environment_variables({'a': 's'})
        pipeline.ensure_environment_variables({'c': 'v', 'd': 'f'})

        pipeline.remove_environment_variable('d')
        p = pipeline.remove_environment_variable('unknown')

        self.assertEquals(p, pipeline)
        self.assertEquals({'a': 's'}, pipeline.encrypted_environment_variables())
        self.assertEquals({'c': 'v'}, pipeline.environment_variables())

    def test_pipelines_have_parameters(self):
        pipeline = more_options_pipeline()
        self.assertEquals({"environment": "qa"}, pipeline.parameters())

    def test_pipelines_have_no_parameters(self):
        pipeline = typical_pipeline()
        self.assertEquals({}, pipeline.parameters())

    def test_can_add_params_to_pipeline(self):
        pipeline = typical_pipeline()
        p = pipeline.ensure_parameters({"new": "one", "again": "two"})
        self.assertEquals(p, pipeline)
        self.assertEquals({"new": "one", "again": "two"}, pipeline.parameters())

    def test_can_modify_parameters_of_pipeline(self):
        pipeline = more_options_pipeline()
        pipeline.ensure_parameters({"new": "one", "environment": "qa55"})
        self.assertEquals({"environment": "qa55", "new": "one"}, pipeline.parameters())

    def test_can_remove_all_parameters(self):
        pipeline = more_options_pipeline()
        p = pipeline.without_any_parameters()
        self.assertEquals(p, pipeline)
        self.assertEquals({}, pipeline.parameters())

    def test_can_have_timer(self):
        pipeline = more_options_pipeline()
        self.assertEquals(True, pipeline.has_timer())
        self.assertEquals("0 15 22 * * ?", pipeline.timer())
        self.assertEquals(False, pipeline.timer_triggers_only_on_changes())

    def test_can_have_timer_with_onlyOnChanges_option(self):
        pipeline = GoCdConfigurator(config('config-with-more-options-pipeline')).ensure_pipeline_group('P.Group').find_pipeline('pipeline2')
        self.assertEquals(True, pipeline.has_timer())
        self.assertEquals("0 0 22 ? * MON-FRI", pipeline.timer())
        self.assertEquals(True, pipeline.timer_triggers_only_on_changes())

    def test_need_not_have_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        self.assertEquals(False, pipeline.has_timer())
        try:
            pipeline.timer()
            self.fail('should have thrown an exception')
        except RuntimeError:
            pass

    def test_can_set_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_timer("one two three")
        self.assertEquals(p, pipeline)
        self.assertEquals("one two three", pipeline.timer())

    def test_can_remove_timer(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        pipeline.set_timer("one two three")
        p = pipeline.remove_timer()
        self.assertEquals(p, pipeline)
        self.assertFalse(pipeline.has_timer())

    def test_can_have_label_template(self):
        pipeline = typical_pipeline()
        self.assertEquals("something-${COUNT}", pipeline.label_template())
        self.assertEquals(True, pipeline.has_label_template())

    def test_might_not_have_label_template(self):
        pipeline = more_options_pipeline()  # TODO swap label with typical
        self.assertEquals(False, pipeline.has_label_template())
        try:
            pipeline.label_template()
            self.fail('should have thrown an exception')
        except RuntimeError:
            pass

    def test_can_set_label_template(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_label_template("some label")
        self.assertEquals(p, pipeline)
        self.assertEquals("some label", pipeline.label_template())

    def test_can_set_default_label_template(self):
        pipeline = GoCdConfigurator(empty_config()).ensure_pipeline_group('Group').ensure_pipeline('Pipeline')
        p = pipeline.set_default_label_template()
        self.assertEquals(p, pipeline)
        self.assertEquals(DEFAULT_LABEL_TEMPLATE, pipeline.label_template())

    def test_can_set_automatic_pipeline_locking(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline = configurator.ensure_pipeline_group("new_group").ensure_pipeline("some_name")
        p = pipeline.set_automatic_pipeline_locking()
        self.assertEquals(p, pipeline)
        self.assertEquals(True, pipeline.has_automatic_pipeline_locking())


class TestPipelineGroup(unittest.TestCase):
    def _pipeline_group_from_config(self):
        return GoCdConfigurator(config('config-with-two-pipelines')).ensure_pipeline_group('P.Group')

    def test_pipeline_groups_have_names(self):
        pipeline_group = standard_pipeline_group()
        self.assertEquals("P.Group", pipeline_group.name())

    def test_pipeline_groups_have_pipelines(self):
        pipeline_group = self._pipeline_group_from_config()
        self.assertEquals(2, len(pipeline_group.pipelines()))

    def test_can_add_pipeline(self):
        configurator = GoCdConfigurator(empty_config())
        pipeline_group = configurator.ensure_pipeline_group("new_group")
        new_pipeline = pipeline_group.ensure_pipeline("some_name")
        self.assertEquals(1, len(pipeline_group.pipelines()))
        self.assertEquals(new_pipeline, pipeline_group.pipelines()[0])
        self.assertEquals("some_name", new_pipeline.name())
        self.assertEquals(False, new_pipeline.has_single_git_material())
        self.assertEquals(False, new_pipeline.has_label_template())
        self.assertEquals(False, new_pipeline.has_automatic_pipeline_locking())

    def test_can_find_pipeline(self):
        found_pipeline = self._pipeline_group_from_config().find_pipeline("pipeline2")
        self.assertEquals("pipeline2", found_pipeline.name())
        self.assertTrue(self._pipeline_group_from_config().has_pipeline("pipeline2"))

    def test_does_not_find_missing_pipeline(self):
        self.assertFalse(self._pipeline_group_from_config().has_pipeline("unknown-pipeline"))
        try:
            self._pipeline_group_from_config().find_pipeline("unknown-pipeline")
            self.fail("should have thrown exception")
        except RuntimeError as e:
            self.assertTrue(e.message.count("unknown-pipeline"))

    def test_can_remove_pipeline(self):
        pipeline_group = self._pipeline_group_from_config()
        pipeline_group.ensure_removal_of_pipeline("pipeline1")
        self.assertEquals(1, len(pipeline_group.pipelines()))
        try:
            pipeline_group.find_pipeline("pipeline1")
            self.fail("should have thrown exception")
        except RuntimeError:
            pass

    def test_ensuring_replacement_of_pipeline_leaves_it_empty_but_in_same_place(self):
        pipeline_group = self._pipeline_group_from_config()
        self.assertEquals("pipeline1", pipeline_group.pipelines()[0].name())
        pipeline = pipeline_group.find_pipeline("pipeline1")
        pipeline.set_label_template("something")
        self.assertEquals(True, pipeline.has_label_template())

        p = pipeline_group.ensure_replacement_of_pipeline("pipeline1")
        self.assertEquals(p, pipeline_group.pipelines()[0])
        self.assertEquals("pipeline1", p.name())
        self.assertEquals(False, p.has_label_template())

    def test_can_ensure_pipeline_removal(self):
        pipeline_group = self._pipeline_group_from_config()
        pg = pipeline_group.ensure_removal_of_pipeline("already-removed-pipeline")
        self.assertEquals(pg, pipeline_group)
        self.assertEquals(2, len(pipeline_group.pipelines()))
        try:
            pipeline_group.find_pipeline("already-removed-pipeline")
            self.fail("should have thrown exception")
        except RuntimeError:
            pass


class TestGoCdConfigurator(unittest.TestCase):
    def test_can_tell_if_there_is_no_change_to_save(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))

        p = configurator.ensure_pipeline_group('Second.Group').ensure_replacement_of_pipeline('smoke-tests')
        p.set_git_url('git@bitbucket.org:springersbm/gomatic.git')
        p.ensure_stage('build').ensure_job('compile').ensure_task(ExecTask(['make', 'source code']))

        self.assertFalse(configurator.has_changes())

    def test_can_tell_if_there_is_a_change_to_save(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))

        p = configurator.ensure_pipeline_group('Second.Group').ensure_replacement_of_pipeline('smoke-tests')
        p.set_git_url('git@bitbucket.org:springersbm/gomatic.git')
        p.ensure_stage('moo').ensure_job('bar')

        self.assertTrue(configurator.has_changes())

    def test_keeps_schema_version(self):
        empty_config = FakeHostRestClient(empty_config_xml.replace('schemaVersion="72"', 'schemaVersion="73"'), "empty_config()")
        configurator = GoCdConfigurator(empty_config)
        self.assertEquals(1, configurator.config().count('schemaVersion="73"'))

    def test_can_have_no_pipeline_groups(self):
        self.assertEquals(0, len(GoCdConfigurator(empty_config()).pipeline_groups()))

    def test_gets_all_pipeline_groups(self):
        self.assertEquals(2, len(GoCdConfigurator(config('config-with-two-pipeline-groups')).pipeline_groups()))

    def test_can_get_initial_config_md5(self):
        configurator = GoCdConfigurator(empty_config())
        self.assertEquals("42", configurator._initial_md5)

    def test_config_is_updated_as_result_of_updating_part_of_it(self):
        configurator = GoCdConfigurator(config('config-with-just-agents'))
        agent = configurator.agents()[0]
        self.assertEquals(2, len(agent.resources()))
        agent.ensure_resource('a-resource-that-it-does-not-already-have')
        configurator_based_on_new_config = GoCdConfigurator(FakeHostRestClient(configurator.config()))
        self.assertEquals(3, len(configurator_based_on_new_config.agents()[0].resources()))

    def test_can_add_pipeline_group(self):
        configurator = GoCdConfigurator(empty_config())
        self.assertEquals(0, len(configurator.pipeline_groups()))
        new_pipeline_group = configurator.ensure_pipeline_group("a_new_group")
        self.assertEquals(1, len(configurator.pipeline_groups()))
        self.assertEquals(new_pipeline_group, configurator.pipeline_groups()[-1])
        self.assertEquals("a_new_group", new_pipeline_group.name())

    def test_can_ensure_pipeline_group_exists(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        self.assertEquals(2, len(configurator.pipeline_groups()))
        pre_existing_pipeline_group = configurator.ensure_pipeline_group('Second.Group')
        self.assertEquals(2, len(configurator.pipeline_groups()))
        self.assertEquals('Second.Group', pre_existing_pipeline_group.name())

    def test_can_remove_all_pipeline_groups(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        s = configurator.remove_all_pipeline_groups()
        self.assertEquals(s, configurator)
        self.assertEquals(0, len(configurator.pipeline_groups()))

    def test_can_remove_pipeline_group(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        s = configurator.ensure_removal_of_pipeline_group('P.Group')
        self.assertEquals(s, configurator)
        self.assertEquals(1, len(configurator.pipeline_groups()))

    def test_can_ensure_removal_of_pipeline_group(self):
        configurator = GoCdConfigurator(config('config-with-two-pipeline-groups'))
        configurator.ensure_removal_of_pipeline_group('pipeline-group-that-has-already-been-removed')
        self.assertEquals(2, len(configurator.pipeline_groups()))

    def test_can_have_templates(self):
        templates = GoCdConfigurator(config('config-with-just-templates')).templates()
        self.assertEquals(2, len(templates))
        self.assertEquals('api-component', templates[0].name())
        self.assertEquals('deploy-stack', templates[1].name())
        self.assertEquals('deploy-components', templates[1].stages()[0].name())

    def test_can_have_no_templates(self):
        self.assertEquals(0, len(GoCdConfigurator(empty_config()).templates()))

    def test_can_add_template(self):
        configurator = GoCdConfigurator(empty_config())
        template = configurator.ensure_template('foo')
        self.assertEquals(1, len(configurator.templates()))
        self.assertEquals(template, configurator.templates()[0])
        self.assertTrue(isinstance(configurator.templates()[0], Pipeline), "so all methods that use to configure pipeline don't need to be tested for template")

    def test_can_ensure_template(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        template = configurator.ensure_template('deploy-stack')
        self.assertEquals('deploy-components', template.stages()[0].name())

    def test_can_ensure_replacement_of_template(self):
        configurator = GoCdConfigurator(config('config-with-just-templates'))
        template = configurator.ensure_replacement_of_template('deploy-stack')
        self.assertEquals(0, len(template.stages()))

    def test_top_level_elements_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-agents-and-templates-but-without-pipelines'))
        configurator.ensure_pipeline_group("some_group").ensure_pipeline("some_pipeline")
        xml = configurator.config()
        root = ET.fromstring(xml)
        self.assertEquals("pipelines", root[0].tag)
        self.assertEquals("templates", root[1].tag)
        self.assertEquals("agents", root[2].tag)

    def test_top_level_elements_with_environment_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-pipelines-environments-and-agents'))
        configurator.ensure_pipeline_group("P.Group").ensure_pipeline("some_pipeline")

        xml = configurator.config()
        root = ET.fromstring(xml)
        self.assertEqual(['server', 'pipelines', 'environments', 'agents'], [element.tag for element in root])

    def test_top_level_elements_that_cannot_be_created_get_reordered_to_please_go(self):
        configurator = GoCdConfigurator(config('config-with-many-of-the-top-level-elements-that-cannot-be-added'))
        configurator.ensure_pipeline_group("P.Group").ensure_pipeline("some_pipeline")

        xml = configurator.config()
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
        job.ensure_artifacts({BuildArtifact('s', 'd')})

        xml = configurator.config()
        pipeline_root = ET.fromstring(xml).find('pipelines').find('pipeline')
        self.assertEquals("params", pipeline_root[0].tag)
        self.assertEquals("timer", pipeline_root[1].tag)
        self.assertEquals("environmentvariables", pipeline_root[2].tag)
        self.assertEquals("materials", pipeline_root[3].tag)
        self.assertEquals("stage", pipeline_root[4].tag)

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

        xml = configurator.config()

        pipeline_root = ET.fromstring(xml).find('pipelines').find('pipeline')
        self.assertEquals("params", pipeline_root[0].tag)
        self.assertEquals("timer", pipeline_root[1].tag)
        self.assertEquals("environmentvariables", pipeline_root[2].tag)
        self.assertEquals("materials", pipeline_root[3].tag)
        self.assertEquals("stage", pipeline_root[4].tag)

        self.__check_stage(pipeline_root)

        template_root = ET.fromstring(xml).find('templates').find('pipeline')
        self.assertEquals("stage", template_root[0].tag)

        self.__check_stage(template_root)

    def __check_stage(self, pipeline_root):
        stage_root = pipeline_root.find('stage')
        self.assertEquals("environmentvariables", stage_root[0].tag)
        self.assertEquals("jobs", stage_root[1].tag)
        job_root = stage_root.find('jobs').find('job')
        self.assertEquals("environmentvariables", job_root[0].tag)
        self.assertEquals("tasks", job_root[1].tag)
        self.assertEquals("tabs", job_root[2].tag)
        self.assertEquals("resources", job_root[3].tag)
        self.assertEquals("artifacts", job_root[4].tag)

    def __configure_stage(self, pipeline):
        stage = pipeline.ensure_stage("s")
        job = stage.ensure_job("j")
        stage.ensure_environment_variables({'s': 's'})
        job.ensure_tab(Tab("n", "p"))
        job.ensure_artifacts({BuildArtifact('s', 'd')})
        job.ensure_task(ExecTask(['ls']))
        job.ensure_resource("r")
        job.ensure_environment_variables({'j': 'j'})


def simplified(s):
    return s.strip().replace("\t", "").replace("\n", "").replace("\\", "").replace(" ", "")


def sneakily_converted_to_xml(pipeline):
    if pipeline.is_template():
        return ET.tostring(pipeline.element)
    else:
        return ET.tostring(pipeline.parent.element)


class TestReverseEngineering(unittest.TestCase):
    def check_round_trip_pipeline(self, configurator, before, show=False):
        reverse_engineered_python = configurator.as_python(before, with_save=False)
        if show:
            print
            print reverse_engineered_python
        pipeline = "evaluation failed"
        template = "evaluation failed"
        exec reverse_engineered_python.replace("from gomatic import *", "from go_cd_configurator import *")
        # noinspection PyTypeChecker
        self.assertEquals(sneakily_converted_to_xml(before), sneakily_converted_to_xml(pipeline))

        if before.is_based_on_template():
            # noinspection PyTypeChecker
            self.assertEquals(sneakily_converted_to_xml(before.template()), sneakily_converted_to_xml(template))

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
            GitMaterial("some git url", "some branch", "some material name", False, {"excluded", "things"}))
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
            .ensure_artifacts({BuildArtifact("s", "d"), TestArtifact("sauce")}) \
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
        self.assertEquals(simplified(expected), simplified(actual))


class TestXmlFormatting(unittest.TestCase):
    def test_can_format_simple_xml(self):
        expected = '<?xml version="1.0" ?>\n<top>\n\t<middle>stuff</middle>\n</top>'
        non_formatted = "<top><middle>stuff</middle></top>"
        formatted = prettify(non_formatted)
        self.assertEquals(expected, formatted)

    def test_can_format_more_complicated_xml(self):
        expected = '<?xml version="1.0" ?>\n<top>\n\t<middle>\n\t\t<innermost>stuff</innermost>\n\t</middle>\n</top>'
        non_formatted = "<top><middle><innermost>stuff</innermost></middle></top>"
        formatted = prettify(non_formatted)
        self.assertEquals(expected, formatted)

    def test_can_format_actual_config(self):
        formatted = prettify(open("test-data/config-unformatted.xml").read())
        expected = open("test-data/config-formatted.xml").read()

        def head(s):
            return "\n".join(s.split('\n')[:10])

        self.assertEquals(expected, formatted, "expected=\n%s\n%s\nactual=\n%s" % (head(expected), "=" * 88, head(formatted)))


if __name__ == '__main__':
    unittest.main()
