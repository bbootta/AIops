# FlashFind

윈도우의 Everything처럼, 입력하는 즉시 결과가 나오는 macOS 파일 이름 검색 앱.

Spotlight을 거치지 않고 자체 파일명 인덱스를 메모리에 올려 두고 부분 문자열 검색을 한다. 숨김 파일(`.`으로 시작)도 인덱스에 포함된다. 네이티브 SwiftUI 앱이며 외부 의존성이 없다.

## 설치

요구 사항: macOS 13 이상, Xcode Command Line Tools (`xcode-select --install`)

```bash
git clone -b claude/mac-file-search-app-jd40op https://github.com/bbootta/AIops.git
cd AIops/products/flashfind
./install.sh
```

이미 저장소를 갖고 있다면:

```bash
git fetch origin claude/mac-file-search-app-jd40op
git checkout claude/mac-file-search-app-jd40op
cd products/flashfind && ./install.sh
```

스크립트가 하는 일: `swift build -c release`로 컴파일하고, `FlashFind.app` 번들을 만들어 `/Applications`(쓰기 권한이 없으면 `~/Applications`)에 넣고, ad-hoc 서명 후 실행한다. 네트워크 접근이나 sudo는 필요 없다.

## 사용법

- 입력하는 즉시 파일 이름 부분 일치로 검색된다. 스페이스로 구분하면 AND 검색 (예: `보고서 pdf`).
- 완전 일치 > 접두 일치 > 부분 일치, 짧은 이름 우선으로 정렬되고 상위 300건을 보여준다.

| 키 | 동작 |
|---|---|
| ↑ / ↓ | 선택 이동 |
| Enter | 열기 |
| Cmd+Enter | Finder에서 보기 |
| Esc | 검색어 지우기 |

더블클릭으로 열기, 우클릭으로 열기 / Finder에서 보기 / 경로 복사. 하단 "다시 인덱싱" 버튼으로 수동 갱신.

## 인덱스 범위와 동작

- 기본 범위: 홈 디렉터리 전체 + `/Applications`. 앱 번들 등 패키지 내부 파일은 제외한다.
- 범위 변경: `~/Library/Application Support/FlashFind/roots.txt`에 한 줄에 하나씩 절대 경로(`~` 허용)를 적으면 그 경로들만 인덱싱한다. `#`으로 시작하는 줄은 주석.
- 첫 실행 시 전체 스캔을 하고(파일 수십만~수백만 개 기준 수십 초, 진행 상황이 하단에 표시됨) 결과를 캐시에 저장한다. 다음 실행부터는 캐시를 즉시 로드해 바로 검색할 수 있고, 백그라운드에서 다시 스캔해 갱신한다.
- 실시간 파일 변경 감시(FSEvents)는 아직 없다. 실행할 때마다 자동 재스캔하고, 필요하면 "다시 인덱싱"을 누른다.

## 권한

- 데스크톱 / 문서 / 다운로드 폴더에 처음 접근할 때 macOS 권한 창이 뜨면 허용한다.
- 일부 보호 영역(Mail 데이터 등)까지 인덱싱하려면 시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한에 FlashFind를 추가한다(선택).

## 제거

```bash
rm -rf /Applications/FlashFind.app ~/Library/Application\ Support/FlashFind
```

## 구조

```
Package.swift                 SwiftPM 매니페스트 (의존성 없음)
Sources/FlashFind/
  FlashFindApp.swift          앱 진입점
  ContentView.swift           검색창 + 결과 리스트 + 상태바
  SearchViewModel.swift       상태 관리, 디바운스 검색, 키보드 처리
  SearchIndex.swift           크롤러, 바이트 버퍼 인덱스, 검색, 캐시
Info.plist                    앱 번들 메타데이터
install.sh                    빌드 + 번들 + 설치
assets/icon.png               앱 아이콘 원본 (1024x1024)
```

인덱스는 파일명(소문자)과 전체 경로를 각각 하나의 연속 바이트 버퍼에 담고 오프셋 배열로 경계를 기록한다. 엔트리당 String 객체를 만들지 않으므로 수백만 파일에서도 검색 한 번이 수십 ms 안에 끝난다.
