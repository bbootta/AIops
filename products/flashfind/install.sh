#!/bin/bash
# FlashFind 빌드 + 설치 스크립트 (macOS 전용)
# 하는 일: swift build -c release 후 FlashFind.app 번들을 만들어
# /Applications(권한 없으면 ~/Applications)에 넣고 ad-hoc 서명 후 실행한다.
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "이 스크립트는 macOS에서 실행해야 합니다." >&2
  exit 1
fi

if ! command -v swift >/dev/null 2>&1; then
  echo "Swift 컴파일러가 없습니다. 먼저 Xcode Command Line Tools를 설치하세요:" >&2
  echo "  xcode-select --install" >&2
  exit 1
fi

echo "==> FlashFind 빌드 중 (swift build -c release)"
swift build -c release

BIN=".build/release/FlashFind"
if [[ ! -f "$BIN" ]]; then
  echo "빌드 결과물을 찾을 수 없습니다: $BIN" >&2
  exit 1
fi

DEST_DIR="/Applications"
if [[ ! -w "$DEST_DIR" ]]; then
  DEST_DIR="$HOME/Applications"
  mkdir -p "$DEST_DIR"
fi
APP="$DEST_DIR/FlashFind.app"

echo "==> 앱 번들 생성: $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/FlashFind"
cp Info.plist "$APP/Contents/Info.plist"

if [[ -f assets/icon.png ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  echo "==> 앱 아이콘 생성"
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z "$s" "$s" assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z "$d" "$d" assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi

codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "==> 설치 완료: $APP"
open "$APP"
