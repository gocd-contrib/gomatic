# Gomatic
[![Travis](https://img.shields.io/travis/gocd-contrib/gomatic.svg)](https://travis-ci.org/gocd-contrib/gomatic)
[![Pypi](https://img.shields.io/pypi/v/gomatic.svg)](https://pypi.python.org/pypi/gomatic)
[![Gitter chat](https://badges.gitter.im/gocd-gomatic.png)](https://gitter.im/gocd-gomatic)

This is a Python API for configuring ThoughtWorks [GoCD](http://www.gocd.org/).

## What does it do?

If you wanted to configure a pipeline something like that shown in the [GoCD documentation](https://docs.gocd.org/current/) then you could run the following script:

```python
#!/usr/bin/env python
from gomatic import *

configurator = GoCdConfigurator(HostRestClient("localhost:8153"))
pipeline = configurator \
    .ensure_pipeline_group("Group") \
    .ensure_replacement_of_pipeline("first_pipeline") \
    .set_git_url("http://git.url")
stage = pipeline.ensure_stage("a_stage")
job = stage.ensure_job("a_job")
job.add_task(ExecTask(['thing']))

configurator.save_updated_config()
```

## How does it work?

Gomatic uses the same mechanism as editing the config XML through the GoCD web based UI.
The `GoCdConfigurator` gets the current config XML from the GoCD server, re-writes it as a result of the methods called, then posts the re-written config XML back to the GoCD server when `save_updated_config` is called.

Gomatic doesn't use the [RESTful Go API](https://api.gocd.org/current) because that is (currently) far too limited for our needs.

## Limitations

We wrote it for our purposes and find it very useful; however, the current version has limitations (e.g. only really supports "Custom Command" task type) and allows you to try to configure GoCD incorrectly (which GoCD will refuse to allow). We will continue to work on it and will address its current limitations.

We believe it works for the following versions (as indicated by `integration_test.py`):

* 16.7.0-3819
* 16.8.0-3929
* 16.9.0-4001
* 16.10.0-413
* 16.11.0-418
* 16.12.0-435
* 17.1.0-4511
* 17.2.0-4587
* 17.3.0-4704
* 17.4.0-4892
* 17.5.0-5095
* 17.6.0-5142
* 17.7.0-5147
* 17.8.0-5277
* 17.9.0-5368
* 17.10.0-5380
* 17.11.0-5520
* 17.12.0-5626
* 18.1.0-5937
* 18.2.0-6228
* 18.3.0-6540
* 18.4.0-6640
* 18.5.0-6679
* 18.6.0-9515
* 18.7.0-9515
* 18.8.0-7433
* 18.9.0-7478
* 18.10.0-7703
* 18.11.0-8024
* 18.12.0-8222
* 19.1.0-8469
* 19.2.0-8641
* 19.3.0-8959
* 19.4.0-9155
* 19.5.0-9272
* 19.6.0-9515

We don't support the below versions anymore, however we did at some point in time, so it might still work in newer versions:

* 13.1.1-16714
* 13.2.2-17585
* 13.3.1-18130
* 13.4.0-18334
* 13.4.1-18342
* 14.1.0-18882
* 14.2.0-377
* 14.3.0-1186
* 14.4.0-1356
* 15.1.0-1863
* 15.2.0-2248
* 16.1.0-2855
* 16.2.1-3027
* 16.3.0-3183 [unsupported from 0.6.8 onwards]
* 16.4.0-3223 [unsupported from 0.6.8 onwards]
* 16.5.0-3305 [unsupported from 0.6.8 onwards]
* 16.6.0-3590 [unsupported from 0.6.8 onwards]

## Install

We've written it using Python 2.7 but have been working on supporting python 3.5 and use `tox` to ensure that all unit tests are passing for both 2.7 and 3.5. You can install gomatic it using "pip":

    sudo pip install gomatic

which will install the [gomatic package](https://pypi.python.org/pypi/gomatic/).

## Usage

We won't document all of the options. Most of the behaviour is covered by [unit tests](https://github.com/SpringerSBM/gomatic/blob/master/tests/go_cd_configurator_test.py), so look at them.

### Dry run

You can see what effect Gomatic will have on the config XML by using `configurator.save_updated_config(save_config_locally=True, dry_run=True)`.
If you have `kdiff3` installed, Gomatic will open it showing the diff (if there is a difference) between the config XML before and after the changes made by the `GoCdConfigurator`.
If you don't have `kdiff3` installed, use a diff tool of your choice to diff the files `config-before.xml` vs `config-after.xml`.

### Reverse engineering of existing pipeline

If you have already set up a pipeline through the UI and now want to retrospectively write a script to do the equivalent, you can get Gomatic to show you the script to create an existing pipeline:

    python -m gomatic.go_cd_configurator -s <GoCD server hostname> -p <pipeline name>

This mechanism can also be useful if you can't work out how to script something; you just make the change you want through the GoCD web based UI and then reverse engineer to see how to do it using Gomatic.
Bear in mind that Gomatic does not currently support every configuration option available in GoCD, so it might not be possible to do everything you want to do.

### Gotchas

* Gomatic does not prevent you from creating config XML that GoCD will not accept. For example, if you create a stage that has no jobs, Gomatic won't complain until you try to run `save_updated_config`, at which time the GoCD server will reject the config XML.
* Gomatic does not check that the version of GoCD it is configuring supports all the features used. For example, versions of GoCD before 15.2 do not support encrypted environment variables on stages and jobs.

## Developing Gomatic

You need to install Python's virtualenv tool and create a virtual environment (once):

    pip install virtualenv

Then, to create the virtual environment, either:

* install [autoenv](https://github.com/kennethreitz/autoenv) and `cd` into the root directory of Gomatic

Or:

* execute `.env` in the root directory of Gomatic and then execute `source venv/bin/activate`

Then, if you are using IntelliJ IDEA:

1. File -> Project Structure -> Project SDK
1. New -> Python SDK -> Add local
1. select `.../gomatic/venv/bin/python`

### Run the tests

Unit tests:

1. `pip install -r requirements.txt`
2. `./build.sh`

Integration tests (takes a long time to download many versions of GoCD) (requires [docker](https://www.docker.com/) to be installed in order to run):

1. `python -m unittest tests.integration_test`

### Contributing to Gomatic via pull request

To have the best chance of your pull request being merged, please:

1. Include tests for any new functionality
1. Separate out different changes into different pull requests
1. Don't delete any existing tests unless absolutely necessary
1. Don't change too much in one pull request

### CI and releasing packages to pypi

Gomatic uses [travis-ci](https://travis-ci.org/SpringerSBM/gomatic) to run the unit tests and deploy to [pypi](https://pypi.python.org/pypi/gomatic).
Only tagged commits are deployed to pypi.

1. update value of `version` in `setup.py`
1. `git tag -a v<version> -m 'version <version>'` (e.g. `git tag -a v0.3.10 -m 'version 0.3.10'`)
1. `git push origin --tags`

Alternatively, run:

1. `bumpversion [major|minor|patch]`
1. `git push origin --tags`
