FROM python:3.11.5-bookworm as build

RUN apt-get update && apt-get install --assume-yes \
    gcc \
    curl \
    python3 \
    python3-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/unit_cooler

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

FROM python:3.11.5-slim-bookworm as prod

ENV TZ=Asia/Tokyo

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

WORKDIR /opt/unit_cooler

COPY . .

EXPOSE 2222
EXPOSE 5000
EXPOSE 5001

CMD ["./app/unit_cooler.py"]
