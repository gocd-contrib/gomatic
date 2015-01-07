# Gomatic

This is a Python API for configuring ThoughtWorks [GoCD](http://www.go.cd/).

## Limitations

We wrote it for our purposes and find it very useful; however, the current version has limitations (e.g. only really supports "Custom Command" task type) and allows you to try to configure GoCD incorrectly (which GoCD will refuse to allow). We will continue to work on it and will address its current limitations.

It has only been tested using GoCD version 14.2.0-377 - I think it doesn't yet work with other versions. 

## Install

We've written it using Python 2 (for the moment - should be simple to port to Python 3 - which we might do in the future). You can install it using "pip":

    sudo pip install gomatic

## Create a pipeline

If you wanted to configure a pipeline something like that shown in the [GoCD documentation](http://www.thoughtworks.com/products/docs/go/current/help/quick_pipeline_setup.html) then you could run the following script:

    #!/usr/bin/env python
    from gomatic import *

    go_server = GoServerConfigurator(HostRestClient("localhost:8153"))
    pipeline = go_server \
        .ensure_pipeline_group("Group") \
        .ensure_replacement_of_pipeline("first_pipeline") \
        .set_git_url("http://git.url")
    stage = pipeline.ensure_stage("a_stage")
    job = stage.ensure_job("a_job")
    job.add_task(ExecTask(['thing']))

    go_server.save_updated_config()

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
