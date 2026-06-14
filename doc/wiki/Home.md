# Sementic UI Wiki

> ComfyUI 기반 AI 생성 엔진 + Semantic JSX(`.sjsx`) 의도 레이어

---

## 이 저장소는 무엇인가

**Sementic UI**는 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 코어를 기반으로 한 작업 공간입니다. 노드 그래프로 이미지·비디오·오디오·3D 콘텐츠를 생성하는 런타임(ComfyUI)과, 구현 전에 사람과 에이전트가 합의할 수 있는 **의도(intent) 표현 레이어**([Semantic JSX](../Sementic-JSX/README.md))를 함께 다룹니다.

| 레이어 | 역할 | 위치 |
|---|---|---|
| **Runtime** | 워크플로 실행, 모델 추론, HTTP/WebSocket 서버 | 저장소 루트 (`main.py`, `comfy/`, `server.py` …) |
| **Design** | 아키텍처·UI·시스템 의도 기록, 합의 상태 관리 | `doc/Sementic-JSX/` |
| **Docs** | 모듈 구조, 운영 가이드 | `doc/wiki/` (이 디렉토리) |

ComfyUI는 *어떻게* 동작하는지를 코드로 담고, `.sjsx`는 *무엇을·왜* 만들기로 했는지를 담습니다. 두 레이어를 분리하면 에이전트 세션이 매번 `src/` 전체를 역추적하지 않고도 설계 의도를 읽을 수 있습니다.

---

## Wiki 목차

| 문서 | 설명 |
|---|---|
| **[module-map.md](./module-map.md)** | 최상위 디렉터리·핵심 모듈 의존 관계 |
| **[Semantic JSX README](../Sementic-JSX/README.md)** | `.sjsx` 문법, 합의 루프, CLI 사용법 |
| **[Semantic JSX README (한국어)](../Sementic-JSX/README.ko.md)** | 위 문서의 한국어 버전 |
| **[ComfyUI README](../../README.md)** | 설치, GPU 설정, CLI 플래그, 업스트림 기능 목록 |

---

## 빠른 시작

### ComfyUI 서버 실행

```bash
pip install -r requirements.txt
python main.py
```

브라우저에서 `http://127.0.0.1:8188` 접속.

자주 쓰는 옵션:

| 플래그 | 설명 |
|---|---|
| `--enable-manager` | ComfyUI-Manager 활성화 |
| `--cpu` | GPU 없이 CPU 전용 실행 |
| `--front-end-version Comfy-Org/ComfyUI_frontend@latest` | 최신 프론트엔드 사용 |
| `--disable-api-nodes` | 외부 API 노드 비활성화 |
| `--enable-assets` | 에셋 관리 API 활성화 |

모델 파일은 `models/` 하위 폴더에 배치합니다. 경로는 `folder_paths.py`와 `extra_model_paths.yaml`로 조정할 수 있습니다.

### Semantic JSX CLI

```bash
cd doc/Sementic-JSX
node index.mjs status .
node index.mjs diff todo-ui.sjsx
node index.mjs scaffold todo-ui.sjsx
```

Python API (서버 내장):

```bash
# designs CRUD · parse/emit · vocabulary
curl http://127.0.0.1:8188/sjsx/designs
curl http://127.0.0.1:8188/sjsx/vocabulary
```

sjsx POC UI: **http://127.0.0.1:8188/sjsx-app/** (새 문서 ComfyUI/sjsx 분기 다이얼로그)

합의 항목 `[ ]` → `[x]` 로 표시하면 설계가 확정된 것으로 간주합니다. 자세한 내용은 [Semantic JSX README](../Sementic-JSX/README.md)를 참고하세요.

---

## 아키텍처 한눈에 보기

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (comfyui-frontend-package)                           │
│  Vue/TS — 노드 캔버스, 큐, 히스토리 UI                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│  server.py — PromptServer                                     │
│  app/ — 사용자·모델·프론트엔드·에셋·DB 관리                    │
│  api_server/ — 내부 라우트                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ prompt queue
┌──────────────────────────▼──────────────────────────────────┐
│  execution.py + comfy_execution/                              │
│  그래프 검증 → 캐시 → 노드 실행 → 진행률 보고                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  nodes.py + comfy_extras/ + custom_nodes/ + comfy_api_nodes/  │
│  노드 정의 (입력/출력, CATEGORY, FUNCTION)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  comfy/ — 모델 로딩, 샘플링, VAE, ControlNet, LDM 구현         │
│  models/ — 체크포인트, LoRA, VAE 등 가중치 파일               │
└─────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────┐
        │  doc/Sementic-JSX/*.sjsx  (Design)   │
        │  의도 · 합의 · topology — 빌드 미포함  │
        └──────────────────────────────────────┘
```

실행 흐름의 핵심 진입점은 `main.py` → `start_comfyui()` → `server.PromptServer` → `execution.py`입니다. 모듈별 상세는 [module-map.md](./module-map.md)를 참고하세요.

---

## 디렉터리 요약

| 경로 | 한 줄 설명 |
|---|---|
| `main.py` | 프로세스 진입점, CLI 인자, DB·노드 초기화 |
| `server.py` | aiohttp 기반 PromptServer, 라우트 등록 |
| `execution.py` | 워크플로 실행 엔진 |
| `nodes.py` | 코어 노드 정의 및 custom node 로더 |
| `folder_paths.py` | 모델·입출력 경로 레지스트리 |
| `comfy/` | PyTorch 모델·샘pler·LDM 구현 |
| `comfy_extras/` | 추가 내장 노드 (~118개) |
| `comfy_api_nodes/` | 외부 API 파트너 노드 |
| `comfy_execution/` | 그래프·캐시·진행률·잡 큐 유틸 |
| `comfy_api/` | 노드 API 버전(v0_0_1, latest …) 및 타입 스텁 |
| `app/` | 프론트엔드·사용자·에셋·DB 애플리케이션 레이어 |
| `blueprints/` | 템플릿 워크플로 JSON |
| `custom_nodes/` | 서드파티·로컬 커스텀 노드 |
| `design/` | sjsx 설계 파일 (`*.sjsx`) |
| `node/sjsx/` | vocabulary (react-native, system) |
| `web/sjsx/` | sjsx POC UI (`/sjsx-app/`) |
| `app/sjsx/` | parse/emit, API, agreement, scaffold |

---

## Semantic JSX와의 관계

Sementic UI에서 UI·시스템 설계는 **빌드 파이프라인 밖**에서 관리합니다.

1. **의도 먼저** — `doc/Sementic-JSX/` 또는 향후 `design/`에 `.sjsx`로 스케치
2. **합의** — `[ ]` 항목을 리뷰 후 `[x]`로 확정
3. **구현** — ComfyUI 노드, 프론트엔드, 서비스 코드 작성
4. **동기화** — 구현이 바뀌면 `.sjsx`도 함께 갱신 (drift 방지)

예시 파일:

- `doc/Sementic-JSX/todo-ui.sjsx` — UI 레이어 (View, FlatList, 이벤트 바인딩)
- `doc/Sementic-JSX/todo-system.sjsx` — 시스템 레이어 (ThreadPool, DbJob, Store)

`.sjsx`는 JSX/TS 문법을 쓰지만 **실행되지 않습니다**. ESLint/에디터 하이라이트만 재사용하고, `sjsx scaffold`로 구현 뼈대를 생성할 수 있습니다.

---

## 개발 시 참고

- **프론트엔드**는 별도 저장소 [ComfyUI_frontend](https://github.com/Comfy-Org/ComfyUI_frontend)에서 관리되며, PyPI 패키지 `comfyui-frontend-package`로 설치됩니다. `app/frontend_management.py`가 버전·경로를 담당합니다.
- **커스텀 노드**는 `custom_nodes/`에 두거나 ComfyUI-Manager로 설치합니다. `nodes.init_extra_nodes()`가 import 시점에 등록합니다.
- **테스트**: `tests/` (통합), `tests-unit/` (단위). CI는 `.github/workflows/` 참고.
- **DB 마이그레이션**: `alembic_db/` — 에셋·태그 등 앱 DB 스키마.

---

## 외부 링크

- [ComfyUI 공식 문서](https://docs.comfy.org/)
- [ComfyUI 예제 워크플로](https://comfyanonymous.github.io/ComfyUI_examples/)
- [ComfyUI Frontend](https://github.com/Comfy-Org/ComfyUI_frontend)
- [ComfyUI-Manager](https://github.com/Comfy-Org/ComfyUI-Manager)

---

## Wiki 기여

모듈 추가·이름 변경·새 `.sjsx` 도메인이 생기면 [module-map.md](./module-map.md)와 이 페이지의 **디렉터리 요약** 표를 함께 업데이트해 주세요. 설계 의도는 코드 PR과 별도로 `.sjsx` diff에 남기는 것을 권장합니다.
