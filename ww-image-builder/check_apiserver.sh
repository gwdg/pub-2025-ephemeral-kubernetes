#!/bin/sh

errorExit() {
    echo "*** $*" 1>&2
    exit 1
}

APISERVER_DEST_PORT=8443

curl -sfk --max-time 2 https://localhost:${APISERVER_DEST_PORT}/healthz -o /dev/null || errorExit "Error GET https://localhost:${APISERVER_DEST_PORT}/healthz"
