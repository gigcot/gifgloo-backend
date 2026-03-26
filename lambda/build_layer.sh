#!/bin/bash
# ffmpeg Lambda Layer 빌드 스크립트
# Amazon Linux 2 (x86_64) 환경용 정적 바이너리 사용
#
# 실행: bash lambda/build_layer.sh

set -e

LAYER_DIR="lambda/layer/ffmpeg"
ZIP_OUT="lambda/layer/ffmpeg-layer.zip"
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
DOWNLOAD_PATH="/tmp/ffmpeg-static.tar.xz"

echo "▶ ffmpeg 정적 바이너리 다운로드 중..."
curl -L "$FFMPEG_URL" -o "$DOWNLOAD_PATH"

echo "▶ 압축 해제 중..."
mkdir -p "$LAYER_DIR/bin"
tar -xf "$DOWNLOAD_PATH" -C /tmp

# 압축 해제된 디렉토리 이름 찾기 (버전마다 다름)
FFMPEG_DIR=$(tar -tf "$DOWNLOAD_PATH" 2>/dev/null | head -1 | cut -d/ -f1 || ls /tmp/ffmpeg-*-amd64-static 2>/dev/null | head -1)
FFMPEG_DIR=$(ls -d /tmp/ffmpeg-*-amd64-static 2>/dev/null | head -1)

cp "$FFMPEG_DIR/ffmpeg" "$LAYER_DIR/bin/ffmpeg"
cp "$FFMPEG_DIR/ffprobe" "$LAYER_DIR/bin/ffprobe"
chmod +x "$LAYER_DIR/bin/ffmpeg" "$LAYER_DIR/bin/ffprobe"

echo "▶ Layer zip 패키징 중..."
cd "$LAYER_DIR"
zip -r "../../../$ZIP_OUT" bin/
cd -

echo "✓ Layer zip 생성 완료: $ZIP_OUT"
echo "  ffmpeg 버전: $($LAYER_DIR/bin/ffmpeg -version 2>&1 | head -1)"
