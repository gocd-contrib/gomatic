#!/bin/bash

# Use at your own risk. Tries to convert code that uses gomatic version 0.3.* into code for using gomatic version 0.4.0
# Can be very slow because it does the "find" repeatedly
# Usage: ./convert-from-0.3-to-0.4.sh <root-directory-of-my-python-code-that-uses-gomatic-version-0.3.*>

set -e

ROOT_DIR=$1

if [ -z ${ROOT_DIR} ] || [ ! -d ${ROOT_DIR} ]; then
    echo Must specify existant root directory
    exit 1
fi

for method in \
    agents \
    current_config \
    config \
    pipeline_groups \
    pipelines \
    templates \
    git_urls \
    has_changes \
    hostname \
    resources \
    as_xml_type_and_value \
    environment_variables \
    encrypted_environment_variables \
    unencrypted_secure_environment_variables \
    is_on_master \
    url \
    polling \
    branch \
    material_name \
    ignore_patterns \
    destination_directory \
    name \
    has_timeout \
    runs_on_all_agents \
    timeout \
    artifacts \
    tabs \
    tasks \
    jobs \
    clean_working_dir \
    has_manual_approval \
    fetch_materials \
    is_template \
    has_label_template \
    has_automatic_pipeline_locking \
    label_template \
    materials \
    git_materials \
    git_material \
    has_single_git_material \
    git_url \
    is_git \
    git_branch \
    is_based_on_template \
    template \
    parameters \
    stages \
    timer_triggers_only_on_changes \
    timer \
    has_timer \
    runif \
    pipeline \
    stage \
    job \
    src \
    dest \
    command_and_args \
    working_dir \
    target; do
    echo About to fix "$method"
    find $ROOT_DIR -type f -name "*.py" -exec sed -i "s/\\.$method()/\\.$method/g" "{}" \;
done