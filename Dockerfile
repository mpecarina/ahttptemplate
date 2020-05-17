FROM python:3.8.2-buster as builder

RUN apt-get update && \
    apt-get install -y gcc git build-essential libtool automake && \
    if [ ! -e /usr/bin/python ]; then ln -sf python3 /usr/bin/python ; fi

RUN python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --no-cache --upgrade pip setuptools wheel && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi

FROM builder as ahttptemplate

LABEL maintainer="mattp@hbci.com" \
      name="ahttptemplate" \
      description="AioHTTP REST API Template"

WORKDIR /ahttptemplate

ENV PROJECT_NAME="ahttptemplate"

COPY . .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    mypy ahttptemplate/*.py

CMD ["python", "-m", "unittest", "discover", "-s", "tests"]
