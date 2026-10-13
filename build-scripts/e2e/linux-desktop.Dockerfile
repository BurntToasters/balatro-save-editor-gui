# Desktop-like Linux target for the Linux E2E: a real X server (Xvfb) with the distribution's own
# Mesa, plus only the packages that provide build-scripts/linux-host-libs.txt. No GPU and no
# software-rendering overrides, so the app goes through the same GLX path as on a user's desktop.
# (AlmaLinux 8 ships xwd, used for the screenshot, in PowerTools.)
ARG BASE
FROM ${BASE}
RUN if command -v apt-get >/dev/null; then \
      apt-get update \
      && asound="$(apt-cache show libasound2t64 >/dev/null 2>&1 && echo libasound2t64 || echo libasound2)" \
      && DEBIAN_FRONTEND=noninteractive apt-get install --assume-yes --no-install-recommends \
        xvfb x11-utils x11-apps libgl1 libegl1 libglx-mesa0 libgl1-mesa-dri libgbm1 \
        "$asound" libcom-err2 libexpat1 libfontconfig1 libfreetype6 libgmp10 libgpg-error0 \
        libice6 libsm6 libstdc++6 libuuid1 libx11-6 libx11-xcb1 zlib1g fonts-dejavu-core \
      && rm -rf /var/lib/apt/lists/*; \
    else \
      dnf install --assumeyes --enablerepo=powertools \
        xorg-x11-server-Xvfb xorg-x11-utils xorg-x11-apps mesa-dri-drivers mesa-libGL \
        mesa-libEGL mesa-libgbm alsa-lib libcom_err expat fontconfig freetype gmp libgpg-error \
        libICE libSM libstdc++ libuuid libX11 libX11-xcb zlib dejavu-sans-fonts \
      && dnf clean all; \
    fi
