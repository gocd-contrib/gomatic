# Gomatic

This is a Python API for configuring ThoughtWorks [GoCD](http://www.go.cd/).

## What does it do?

If you wanted to configure a pipeline something like that shown in the [GoCD documentation](http://www.thoughtworks.com/products/docs/go/current/help/quick_pipeline_setup.html) then you could run the following script:

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

## How does it work?

Gomatic uses the same mechanism as editing the config XML through the GoCD web based UI.
The `GoCdConfigurator` gets the current config XML from the GoCD server, re-writes it as a result of the methods called, then posts the re-written config XML back to the GoCD server when `save_updated_config` is called.

Gomatic doesn't use the [RESTful Go API](http://www.thoughtworks.com/products/docs/go/current/help/go_api.html) because that is (currently) far too limited for our needs.

## Limitations

We wrote it for our purposes and find it very useful; however, the current version has limitations (e.g. only really supports "Custom Command" task type) and allows you to try to configure GoCD incorrectly (which GoCD will refuse to allow). We will continue to work on it and will address its current limitations.

It has only been tested using GoCD versions 13.4.0 and 14.2.0-377 - I think it doesn't yet work with the newest versions.

## Install

We've written it using Python 2 (for the moment - should be simple to port to Python 3 - which we might do in the future). You can install it using "pip":

    sudo pip install gomatic

## Getting Started with Developing gomatic

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
