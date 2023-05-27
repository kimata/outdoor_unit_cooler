FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    language-pack-ja \
    python3 python3-pip \
    python3-docopt \
    python3-yaml python3-coloredlogs \
    python3-fluent-logger \
    python3-smbus python3-spidev \
    python3-zmq \
 && apt-get clean \
 && rm -rf /va/rlib/apt/lists/*

WORKDIR /opt/unit_cooler

COPY . .
RUN pip3 install -r requirements.txt

CMD ["./app/unit_cooler.py"]
