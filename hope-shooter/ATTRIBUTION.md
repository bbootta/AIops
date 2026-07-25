# 외부 자산 출처

이 게임의 텍스처와 지오메트리는 대부분 코드로 생성하지만, 아래 자산은
외부에서 가져왔습니다. 모두 번들에 base64로 인라인되어 실행 시 네트워크
요청을 하지 않습니다.

## 머리 스캔 및 스킨 텍스처

`assets/head-scan.glb`, `assets/head-albedo.jpg`, `assets/head-normal.jpg`

Lee Perry-Smith의 머리 포토그래메트리 스캔(Infinite-Realities)입니다.
three.js 예제 저장소의 `examples/models/gltf/LeePerrySmith/`에서 가져왔고,
three.js는 이 자산의 출처를 [casual-effects.com/data](https://casual-effects.com/data/)로
표기하고 있습니다. 원 배포 조건은 **CC BY 3.0**(저작자 표시)입니다.

- 원본: https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith
- 파일명만 용도에 맞게 바꿨고 지오메트리·텍스처 내용은 원본 그대로입니다.
  (로드 시 코드에서 크기를 정규화할 뿐 파일은 수정하지 않았습니다.)

배포·재사용 시 위 저작자 표시를 유지해야 합니다.

## 환경 조명 HDRI · 미세 노멀맵

npm 패키지 [`@pmndrs/assets`](https://github.com/pmndrs/assets)의
`hdri/city.exr`와 `normals/0007.webp`, `normals/0021.webp`를 사용합니다.
해당 저장소는 **CC0**(퍼블릭 도메인 기여)로 배포됩니다.

## three.js

렌더링은 [three.js](https://github.com/mrdoob/three.js) (MIT)를 사용합니다.
