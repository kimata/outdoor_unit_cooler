FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y language-pack-ja
RUN apt-get install -y python3 python3-pip

RUN apt-get install -y python3-yaml python3-coloredlogs
RUN apt-get install -y python3-fluent-logger
RUN apt-get install -y python3-smbus python3-spidev

RUN pip3 install 'influxdb-client[ciso]'

WORKDIR /opt/unit_cooler
COPY . .

CMD ["./app/unit_cooler.py"]
