FROM quay.io/pypa/manylinux_2_28_x86_64:2026.05.07-2

ARG PYTHON_VERSION=3.12.15
ARG PYTHON_SHA256=c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a

RUN sed -i \
      -e 's|^mirrorlist=|#mirrorlist=|' \
      -e 's|^# baseurl=https://repo.almalinux.org/almalinux/|baseurl=https://repo.almalinux.org/almalinux/|' \
      /etc/yum.repos.d/almalinux*.repo \
    && sed -i \
      -e 's|^metalink=|#metalink=|' \
      -e 's|^#baseurl=https://download.example/pub/epel/|baseurl=https://download.fedoraproject.org/pub/epel/|' \
      /etc/yum.repos.d/epel*.repo \
    && dnf install --assumeyes \
      alsa-lib bzip2-devel libffi-devel libXcomposite libXdamage libXi libXrandr libxslt \
      libXtst libxkbcommon libxkbcommon-x11 libxkbfile nspr nss openssl-devel pulseaudio-libs \
      xcb-util-cursor xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm xz-devel \
    && dnf clean all \
    && curl --fail --location --silent --show-error \
      "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
      --output /tmp/python.tar.xz \
    && echo "${PYTHON_SHA256}  /tmp/python.tar.xz" | sha256sum --check --strict \
    && tar --extract --file /tmp/python.tar.xz --directory /tmp \
    && cd "/tmp/Python-${PYTHON_VERSION}" \
    && ./configure --prefix=/opt/bse-python --enable-shared --with-ensurepip=install \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf "/tmp/Python-${PYTHON_VERSION}" /tmp/python.tar.xz

ENV PATH=/opt/bse-python/bin:${PATH}
ENV LD_LIBRARY_PATH=/opt/bse-python/lib

COPY requirements.txt requirements-dev.txt requirements-linux.txt /tmp/requirements/
RUN python3 -m venv /opt/bse-venv \
    && /opt/bse-venv/bin/python -m pip install --disable-pip-version-check \
      -r /tmp/requirements/requirements-linux.txt \
    && rm -rf /tmp/requirements

ENV PATH=/opt/bse-venv/bin:${PATH}
