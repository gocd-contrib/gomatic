# Gomatic

This is a Python API for configuring ThoughtWorks [GoCD](http://www.go.cd/).

## What does it do?

If you wanted to configure a pipeline something like that shown in the [GoCD documentation](http://www.thoughtworks.com/products/docs/go/current/help/quick_pipeline_setup.html) then you could run the following script:

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

Gomatic doesn't use the [RESTful Go API](http://www.thoughtworks.com/products/docs/go/current/help/go_api.html) because that is (currently) far too limited for our needs.

## Limitations

We wrote it for our purposes and find it very useful; however, the current version has limitations (e.g. only really supports "Custom Command" task type) and allows you to try to configure GoCD incorrectly (which GoCD will refuse to allow). We will continue to work on it and will address its current limitations.

We believe it works for the following versions (as indicated by `integration-test.py`):

* 13.2.2-17585
* 13.3.1-18130
* 13.4.0-18334
* 13.4.1-18342
* 14.1.0-18882
* 14.2.0-377
* 14.3.0-1186
* 14.4.0-1356
* 15.1.0-1863

## Install

We've written it using Python 2.7 (for the moment - should be simple to port to Python 3 - which we might do in the future). You can install it using "pip":

    sudo pip install gomatic

which will install the [gomatic package](https://pypi.python.org/pypi/gomatic/).

## Usage

We won't document all of the options. Most of the behaviour is covered by [unit tests](https://github.com/SpringerSBM/gomatic/blob/master/gomatic/go_cd_configurator_test.py), so look at them.

### Dry run

You can see what effect Gomatic will have on the config XML by using `configurator.save_updated_config(save_config_locally=True, dry_run=True)`.
If you have `kdiff3` installed, Gomatic will open it showing the diff (if there is a difference) between the config XML before and after the changes made by the `GoCdConfigurator`.
If you don't have `kdiff3` installed, use a diff tool of your choice to diff the files `config-before.xml` vs `config-after.xml`.

### Reverse engineering of existing pipeline

If you have already set up a pipeline through the UI and now want to retrospectively write a script to do the equivalent, you can get Gomatic to show you the script to create an existing pipeline.
We will include an easier way to run this in the future - for the moment, you can run something like the following:

```python
#!/usr/bin/env python
from gomatic import *

configurator = GoCdConfigurator(HostRestClient("localhost:8153"))
pipeline = configurator\
    .ensure_pipeline_group("Group")\
    .find_pipeline("first_pipeline")
print configurator.as_python(pipeline)
```

This mechanism can also be useful if you can't work out how to script something; you just make the change you want through the GoCD web based UI and then reverse engineer to see how to do it using Gomatic.
Bear in mind that Gomatic does not currently support every configuration option available in GoCD, so it might not be possible to do everything you want to do.

### Gotchas

* Gomatic does not prevent you from creating config XML that GoCD will not accept. For example, if you create a stage that has no jobs, Gomatic won't complain until you try to run `save_updated_config`, at which time the GoCD server will reject the config XML.
* Gomatic currently only supports calling `save_updated_config` once per instance of `GoCdConfigurator`.

## Developing gomatic

You need to install Python's virtualenv tool and create a virtual environment (once):

    pip install virtualenv

Then, if you are using IntelliJ IDEA:

1. File -> Project Structure -> Project SDK
1. New -> Python SDK -> Create VirtualEnv
1. for "Name" use "venv"
1. for path, select Gomatic's directory, and location should become `.../gomatic/venv`
1. follow the command line steps below (apart from "virtualenv venv").

If you only want to use the command line:

1. `virtualenv venv`
1. `source venv/bin/activate`
1. `pip install -r requirements.txt`

Then, each time you want to run gomatic, if you need to activate the virtual environment (if it is not already activated - your command prompt will indicate if it is, e.g. `(venv)ivan@...`):

    source venv/bin/activate

### Run the tests

Unit tests:

1. `cd gomatic`
1. `python go_cd_configurator_test.py`

Integration tests (takes a long time to download many versions of GoCD) (requires [docker](https://www.docker.com/) to be installed in order to run):
 
1. `python integration-test.py`
