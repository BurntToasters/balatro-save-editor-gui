#!/bin/bash
# Runs inside a linux-desktop.Dockerfile container for the Linux E2E (build-scripts/e2e/linux.py).
# 1. Links the host's GLX/EGL/GBM/DRI libraries with and without the bundle on LD_LIBRARY_PATH
#    (PyInstaller's bootloader puts it there) and writes any errors the bundle adds.
# 2. Starts the frozen app on Xvfb with the host's Mesa and screenshots its window.
# Usage: linux-desktop.sh NAME BUNDLE_DIR OUT_DIR. Prints key=value lines; files go to OUT_DIR/NAME.*
set -u
name=$1 app=$2 out=$3
title='Balatro Save Editor'

link_errors() {
  ldd -r "$1" 2>&1 | grep -E 'not found|undefined symbol' | sed 's/ (0x[0-9a-f]*)//' | sort -u
}

: > "$out/$name-gl.txt"
for lib in /usr/lib64/libGLX_mesa.so.0 /usr/lib64/libEGL_mesa.so.0 /usr/lib64/libgbm.so.1 \
    /usr/lib64/dri/swrast_dri.so /usr/lib/x86_64-linux-gnu/libGLX_mesa.so.0 \
    /usr/lib/x86_64-linux-gnu/libEGL_mesa.so.0 /usr/lib/x86_64-linux-gnu/libgbm.so.1 \
    /usr/lib/x86_64-linux-gnu/dri/swrast_dri.so; do
  [ -e "$lib" ] || continue
  echo "gl_checked=$lib"
  comm -13 <(link_errors "$lib") <(LD_LIBRARY_PATH="$app/_internal" link_errors "$lib") >> "$out/$name-gl.txt"
done

Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 &
export DISPLAY=:99
for _ in $(seq 50); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.2; done

cd /tmp || exit 1
"$app/balatro-save-editor" > "$out/$name.log" 2>&1 &
pid=$!
shown=
for second in $(seq 30); do
  if xwininfo -name "$title" 2>/dev/null | grep -q 'IsViewable'; then shown=$second; break; fi
  kill -0 "$pid" 2>/dev/null || break
  sleep 1
done
echo "window_after=${shown:-never}"
if [ -n "$shown" ]; then
  sleep 4  # let the page finish painting
  xwd -silent -name "$title" -out "$out/$name.xwd"
fi
sleep 2
kill -0 "$pid" 2>/dev/null && echo 'alive=yes' || echo 'alive=no'
kill "$pid" 2>/dev/null
wait "$pid" 2>/dev/null
exit 0
