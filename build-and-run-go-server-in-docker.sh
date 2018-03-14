#! /bin/bash

set -e

GO_VERSION="$1"
GO_DOWNLOAD_VERSION_STRING="$2"
GO_PORT="$3"

if [ -z "$GO_VERSION" ]; then
  echo >&2 "No Go server version was provided"
  exit 1
fi
if [ -z "$GO_DOWNLOAD_VERSION_STRING" ]; then
  echo >&2 "No Go server download version was provided"
  exit 1
fi

IMAGE_NAME=springersbm/gocd:${GO_VERSION}

if [[ "$(docker images -q ${IMAGE_NAME} 2> /dev/null)" == "" ]]; then
    docker build -t ${IMAGE_NAME} --build-arg GO_VERSION=$GO_VERSION --build-arg GO_DOWNLOAD_VERSION_STRING=$GO_DOWNLOAD_VERSION_STRING docker/
fi

docker run -d --name gocd-test-server-${GO_VERSION} -it -p ${GO_PORT}:8153 ${IMAGE_NAME}
