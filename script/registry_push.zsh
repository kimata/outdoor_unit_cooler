#!/usr/bin/env zsh

NAME=outdoor_unit_cooler
REGISTRY=registry.green-rabbit.net:5000/kimata

if [ $(uname -m) != "aarch64" ]; then
    echo "Raspberry Pi 上で実行してください．"
    exit -1
fi

git pull
docker build --platform linux/arm64 . -t ${NAME}
docker tag ${NAME} ${REGISTRY}/${NAME}
docker push ${REGISTRY}/${NAME}
