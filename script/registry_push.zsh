#!/usr/bin/env zsh

BUILDER=arm_builder
NAME=outdoor_unit_cooler
REGISTRY=registry.green-rabbit.net:5000/kimata

git pull

# docker buildx rm arm_builder
docker buildx create --name ${BUILDER} --node ${BUILDER}0 --config ${0:a:h}/buildkitd.toml --use
docker buildx use arm_builder
docker buildx build --platform linux/amd64,linux/arm64/v8 \
       --cache-from type=registry,ref=${REGISTRY}/${NAME}:cache \
       --cache-to type=registry,ref=${REGISTRY}/${NAME}:cache \
       --output=type=image,push=true --tag ${REGISTRY}/${NAME} .

