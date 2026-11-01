#!/bin/sh
# Build an unpatched LGPL FFmpeg for the PyAV binding; system CLI stays separate.
set -eu
version=8.1.2
sha=464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c
# Debian mirrors the byte-identical upstream release; verify the pinned hash below.
curl --fail --location --connect-timeout 20 --max-time 180 --proto '=https' --tlsv1.2 \
  "https://deb.debian.org/debian/pool/main/f/ffmpeg/ffmpeg_${version}.orig.tar.xz" -o /tmp/ffmpeg-source.tar.xz
printf '%s  %s\n' "$sha" /tmp/ffmpeg-source.tar.xz | sha256sum --check --strict
mkdir -p /tmp/ffmpeg-build /opt/asr-media/share/licenses
tar -xJf /tmp/ffmpeg-source.tar.xz -C /tmp/ffmpeg-build --strip-components=1
cd /tmp/ffmpeg-build
./configure --prefix=/opt/asr-media --disable-static --enable-shared \
  --disable-programs --disable-doc --disable-autodetect --disable-network \
  --disable-gpl --disable-nonfree --disable-x86asm \
  --extra-ldflags=-Wl,-rpath,/opt/asr-media/lib
make -j 8
make install
cp COPYING.LGPLv2.1 LICENSE.md /opt/asr-media/share/licenses/
cp config.h /opt/asr-media/share/licenses/build-config.h
printf '%s  %s\n' "$sha" "ffmpeg-${version}.tar.xz" > /opt/asr-media/share/licenses/SOURCE.sha256
rm -rf /tmp/ffmpeg-build /tmp/ffmpeg-source.tar.xz
