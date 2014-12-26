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

    go_server = GoServer(HostRestClient("localhost:8153"))
    pipeline = go_server \
        .ensure_pipeline_group("Group") \
        .ensure_replacement_of_pipeline("first_pipeline") \
        .set_git_url("http://git.url")
    stage = pipeline.ensure_stage("a_stage")
    job = stage.ensure_job("a_job")
    job.add_task(ExecTask(['thing']))

    go_server.save_updated_config()
