# 호프: 마지막 거리

영화 *호프*의 시가전 장면을 3D FPS로 옮긴 게임입니다. 폐허가 된 한국 상가
거리에서 밀려오는 그림자를 상대로 웨이브를 버팁니다.

## 설치해서 플레이

데스크톱 앱으로 설치해서 실행할 수 있습니다. 설치 파일은 **각자의 OS에서**
빌드해야 합니다 — 리눅스에서 Windows·macOS 설치 파일은 만들 수 없습니다.

```
npm install
npm run dist:win      # Windows: release/HopeLastStreet-Setup-1.0.0.exe
npm run dist:mac      # macOS:   release/*.dmg
npm run dist:linux    # Linux:   release/*.AppImage
```

`npm start`로 설치 없이 앱 창에서 바로 실행할 수도 있습니다.

## 브라우저에서 플레이

`dist/index.html`을 브라우저에서 열어도 됩니다. 외부 리소스를 전혀 받지 않는
단일 파일이라 오프라인에서도 그대로 돌아갑니다.

조작: **WASD** 이동 · **마우스** 조준 · **클릭** 사격 · **우클릭** 정조준 ·
**R** 재장전 · **SHIFT** 달리기 · **V** 3인칭/1인칭 전환

원본 스틸이 오버숄더 구도라 3인칭이 기본 시점입니다.

## 빌드

소스는 `src/`에 있고, esbuild로 번들해 `dist/index.html` 한 장으로 인라인합니다.

```
npm install
npm run build
```

| 파일 | 내용 |
| --- | --- |
| `src/tex.js` | 절차적 텍스처 도구 — 타일링 노이즈, 높이맵→노멀맵 변환, PBR 재질 팩토리 |
| `src/materials.js` | 아스팔트·콘크리트·벽돌·셔터·간판·유리 등 재질 정의 |
| `src/env.js` | 촬영된 도시 HDRI를 디코드·그레이딩해 IBL 환경맵 생성 |
| `src/world.js` | 하늘과 조명, 창이 실제로 파인 건물, 거리 구성 |
| `src/actors.js` | 그림자 괴물과 소총 |
| `src/head.js` | 머리 스캔 GLB와 스킨 텍스처 디코드 |
| `src/player.js` | 경찰 캐릭터 모델과 포즈 리깅 |
| `src/main.js` | 렌더 파이프라인, 후처리, 게임 루프, HUD |
| `electron/main.js` | 데스크톱 앱 창(샌드박스 렌더러, 외부 요청 차단) |
| `scripts/make-icon.mjs` | 런처 아이콘 PNG 생성 (이미지 라이브러리 없이 직접 인코딩) |

텍스처와 지오메트리는 대부분 코드로 생성합니다. 외부 자산은 조명용 HDRI,
미세 노멀맵, 그리고 캐릭터 머리의 포토그래메트리 스캔과 스킨 텍스처 세트이며,
전부 base64로 번들에 인라인되어 네트워크 요청 없이 메모리에서 디코드합니다.
출처와 라이선스는 [ATTRIBUTION.md](ATTRIBUTION.md)를 참고하세요.
