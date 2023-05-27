#!/usr/bin/env zsh

NAME=outdoor_unit_cooler
REGISTRY=registry.green-rabbit.net:5000/kimata

git pull

# docker buildx rm arm_builder
docker buildx create --name arm_builder --config ${0:a:h}/../buildkitd.toml --use
docker buildx use arm_builder
docker buildx build --platform linux/amd64,linux/arm64/v8 . --output=type=image,push=true --tag ${REGISTRY}/${NAME}

