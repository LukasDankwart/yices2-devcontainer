FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    autoconf \
    gperf \
    git \
    libgmp-dev \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/SRI-CSL/yices2.git
WORKDIR /opt/yices2
RUN autoconf \
    && ./configure \
    && make \
    && make install

WORKDIR /opt
RUN git clone https://github.com/SRI-CSL/yices2_python_bindings.git
WORKDIR /opt/yices2_python_bindings
RUN pip3 install .

RUN pip install onnx onnxruntime numpy

WORKDIR /workspace

CMD ["/bin/bash"]
