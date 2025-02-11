#!/bin/bash

rm /share/leader || true
rm /share/leader_ready || true
rm /share/logs/* || true
rm /share/pki/*.* || true
rm /share/pki/etcd/*.* || true
rm /share/kube.config || true
rm /share/phylactery/*.txt || true
