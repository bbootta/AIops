#!/bin/bash
# FlashFind 팀 배포용 DMG 생성 스크립트 (macOS 전용)
# 유니버설(arm64 + x86_64) 바이너리로 빌드해 dist/FlashFind-<버전>.dmg 를 만든다.
# 받은 사람은 DMG를 열고 앱을 Applications로 드래그하면 끝. 안내문이 DMG에 들어간다.
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

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' Info.plist 2>/dev/null || echo 1.0.0)"

echo "==> 유니버설 빌드 시도 (arm64 + x86_64)"
BIN=""
if swift build -c release --arch arm64 --arch x86_64; then
  BIN=".build/apple/Products/Release/FlashFind"
fi
if [[ -z "$BIN" || ! -f "$BIN" ]]; then
  echo "==> 유니버설 빌드가 안 되는 환경, 현재 아키텍처로만 빌드합니다"
  swift build -c release
  BIN=".build/release/FlashFind"
fi
if [[ ! -f "$BIN" ]]; then
  echo "빌드 결과물을 찾을 수 없습니다." >&2
  exit 1
fi

STAGING="$(mktemp -d)/FlashFind"
APP="$STAGING/FlashFind.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/FlashFind"
cp Info.plist "$APP/Contents/Info.plist"

if [[ -f assets/icon.png ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z "$s" "$s" assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z "$d" "$d" assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi

codesign --force --deep --sign - "$APP"

ln -s /Applications "$STAGING/Applications"
cat > "$STAGING/설치 방법.txt" <<'TXT'
FlashFind 설치 방법

1. FlashFind 아이콘을 옆의 Applications 폴더로 드래그하세요.

2. Applications 폴더에서 FlashFind를 처음 열 때 macOS가
   "확인되지 않은 개발자" 경고를 표시할 수 있습니다. 한 번만 허용하면 됩니다.
   - macOS 15 이상: 경고 창을 닫고 시스템 설정 > 개인정보 보호 및 보안
     맨 아래의 "그래도 열기"를 누른 뒤 다시 실행
   - macOS 13~14: 앱을 우클릭(Control+클릭) > 열기 > 열기
   - 터미널이 편하면 한 줄로:
     xattr -dr com.apple.quarantine /Applications/FlashFind.app

3. 첫 실행 시 홈 폴더 전체를 스캔합니다(수십 초, 하단에 진행 표시).
   스캔이 끝나면 입력하는 즉시 파일 이름이 검색됩니다.
   데스크톱/문서/다운로드 접근 권한 팝업이 뜨면 허용해 주세요.

사용법: 스페이스로 AND 검색, Enter 열기, Cmd+Enter는 Finder에서 보기,
우클릭으로 경로 복사. 하단 "다시 인덱싱"으로 수동 갱신.
TXT

mkdir -p dist
OUT="dist/FlashFind-${VERSION}.dmg"
rm -f "$OUT"
hdiutil create -volname "FlashFind" -srcfolder "$STAGING" -ov -format UDZO "$OUT" >/dev/null

echo "==> 완료: $OUT"
lipo -archs "$APP/Contents/MacOS/FlashFind" 2>/dev/null | sed 's/^/    포함 아키텍처: /' || true
echo "    이 파일 하나를 Slack이나 드라이브로 공유하면 됩니다."
