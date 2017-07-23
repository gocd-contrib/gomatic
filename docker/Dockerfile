FROM java:8

CMD /etc/init.d/go-server start && tail -F /var/log/go-server/go-server.log

EXPOSE 8153
EXPOSE 8154

ARG GO_VERSION
ARG GO_DOWNLOAD_VERSION_STRING

ADD https://download.go.cd/binaries/${GO_VERSION}/deb/go-server${GO_DOWNLOAD_VERSION_STRING}.deb /tmp/go-server-${GO_VERSION}.deb

RUN dpkg -i /tmp/go-server-${GO_VERSION}.deb

RUN rm -f /tmp/go-server-${GO_VERSION}.deb

