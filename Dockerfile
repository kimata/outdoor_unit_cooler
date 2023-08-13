FROM python:3.11.4-bookworm as build

ENV TZ=Asia/Tokyo

RUN apt-get update && apt-get install --assume-yes \
    gcc \
    curl \
    python3 \
    python3-dev \
 && apt-get clean \
 && rm -rf /va/rlib/apt/lists/*

WORKDIR /opt/unit_cooler

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

FROM python:3.11.4-slim-bookworm as prod

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

WORKDIR /opt/unit_cooler

COPY . .

ENV PATH="/root/.local/bin:$PATH"

EXPOSE 2222
EXPOSE 5000
EXPOSE 5001

CMD ["./app/unit_cooler.py"]
