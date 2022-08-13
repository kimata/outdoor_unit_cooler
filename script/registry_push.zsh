#!/usr/bin/env zsh

NAME=unit_cooler
REGISTRY=registry.green-rabbit.net/library

if [ $(uname -m) != "aarch64" ]; then
    echo "Raspberry Pi 上で実行してください．"
    exit -1
fi

git push
docker build --platform linux/arm64 . -t ${NAME}
docker tag ${NAME} ${REGISTRY}/${NAME}
docker push ${REGISTRY}/${NAME}
