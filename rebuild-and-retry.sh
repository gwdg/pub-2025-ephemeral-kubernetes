#!/bin/bash

wwctl overlay chmod k8s-control /k8s-helper/k8s-install.sh 650
wwctl overlay build

./clean-up.sh

wwctl ssh control[0-999] reboot
wwctl ssh worker[0-999] reboot
