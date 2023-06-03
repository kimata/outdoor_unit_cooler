#!/usr/bin/env zsh

NAME=outdoor_unit_cooler
REGISTRY=registry.green-rabbit.net:5000/kimata

git pull
docker pull ${REGISTRY}/${NAME}
