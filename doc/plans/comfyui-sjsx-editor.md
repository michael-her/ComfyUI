# ComfyUI → Semantic JSX 그래픽 편집기 개조 계획

> **목표:** [Semantic JSX](../Sementic-JSX/README.md)(`.sjsx`)를 텍스트·CLI가 아닌 **그래픽 UI/UX**로 작성·합의·저장할 수 있도록 ComfyUI를 개조한다.
>
> **상태:** draft · **작성일:** 2026-06-14

---

## 1. 배경과 제품 정의

### 1.1 해결하려는 문제

`.sjsx`는 JSX topology + 합의 상태(`[ ]` / `[x]`) + git history를 한 파일에 담는 **의도 IR**이다. 현재는 `doc/Sementic-JSX/index.mjs` CLI와 텍스트 편집기로만 다룰 수 있다.

에이전트·인간 모두에게 **한 번에 전체 그림이 보이는(legsible in one pass)** 편집 경험이 필요하다. ComfyUI의 노드 캔버스는 이미 다음을 제공한다.

- 컴포넌트(노드) 배치와 계층(그룹)
- 속성 패널(widget)
- 연결(와이어)로 데이터·이벤트 흐름 표현
- JSON 직렬화·저장·diff

→ **워크플로 편집 UX를 재활용**하되, `.sjsx` 의도 그래프 편집 기능을 **기존 ComfyUI 위에 추가**한다.

### 1.2 추가형(Additive) 구현 원칙

기존 ComfyUI 화면·동작을 **제거·대체하지 않는다.** sjsx 기능은 플러그인처럼 얹는다.

| 원칙 | 설명 |
|---|---|
| **기존 UI 유지** | 메뉴, 툴바, 큐, 히스토리, 노드 팔레트 레이아웃 그대로 |
| **ComfyUI 노드 유지** | KSampler, LoadImage 등 **전용 노드는 당분간 숨기지 않음** — 팔레트에 계속 노출 |
| **sjsx 노드 추가** | vocabulary 노드(`View`, `ThreadPool` …)를 **별 카테고리로 추가** |
| **문서 타입 분기** | 새 워크플로 생성 시 ComfyUI / sjsx 중 선택 — 이후 UX·저장·실행이 분기 |
| **실행 경로 보존** | ComfyUI 문서는 기존 `execution.py` 그대로; sjsx 문서는 queue 미사용 |

### 1.3 문서 타입별 동작

| | ComfyUI workflow | sjsx design |
|---|---|---|
| 파일 형식 | `.json` (기존 workflow) | `.sjsx` |
| 캔버스 객체 | KSampler, LoadImage … | `View`, `ThreadPool`, `Store` … |
| 노드 팔레트 | ComfyUI 전용 노드 **전체 표시** | sjsx vocabulary **+** ComfyUI 노드 (당분간 모두 표시) |
| 와이어 | tensor / latent / image | props, state, event handler |
| Queue / Execute | GPU 추론 (기존) | validate / emit / scaffold (실행 아님) |
| 출력 | PNG, latent | `.sjsx` 텍스트, scaffold 파일 |
| 합의 | 없음 | `[ ]` / `[x]` 패널 + 진행률 |

**Phase 0~2까지는 diffusion 실행 경로(`comfy/`, `execution.py`)를 건드리지 않는다.** sjsx 문서가 queue에 들어가지 않도록 **문서 타입 메타데이터**로 가드한다.

---

## 2. 개념 매핑 (ComfyUI ↔ `.sjsx`)

```
ComfyUI                    Semantic JSX
─────────────────────────────────────────────────
Node                       JSX element  (<View>, <DbJob>, …)
class_type                 tag name
inputs (widgets)           attributes (cx, query, data, …)
output slot + link         prop binding / children nesting
Group                      domain 또는 layer 블록
Subgraph                   const Component = ( … ) 서브트리
Workflow JSON              SjsxGraph (중간 IR, 아래 정의)
Save / Load API            design/*.sjsx read/write
Node palette               Vocabulary registry (ui / system / state)
Property panel             attribute + agreement item 편집
Execute button             Emit .sjsx / Run scaffold (실행 아님)
```

### 2.1 중간 표현: `SjsxGraph`

`.sjsx` 텍스트와 ComfyUI 프론트엔드가 공유하는 JSON IR. ComfyUI workflow 형식과 **유사하되 별도 스키마**로 둔다 (실행기 혼동 방지).

```json
{
  "version": 1,
  "meta": {
    "domain": "TodoApp",
    "layer": "ui",
    "status": "design"
  },
  "agreement": {
    "agreed": ["화면 구조", "이벤트 바인딩"],
    "pending": ["빈 상태 UI 디자인", "에러 상태 처리"]
  },
  "nodes": {
    "1": {
      "type": "View",
      "attrs": { "cx": "flex-1 bg-neutral-950" },
      "children": ["2", "3"]
    },
    "2": {
      "type": "Text",
      "attrs": { "cx": "text-2xl font-bold text-white" },
      "children": [],
      "content": "todos"
    }
  },
  "bindings": {
    "3": { "onSubmit": { "target": "TodoStore", "action": "addTodo" } }
  },
  "comments": []
}
```

**Round-trip invariant:** `parse(emit(parse(src))) ≈ parse(src)` — Phase 0의 합격 기준.

### 2.2 문서 타입 메타데이터

워크플로·디자인 파일 공통으로 **문서 타입**을 명시한다. 프론트엔드는 이 값으로 UX를 분기한다.

```json
{
  "document_type": "comfyui",
  "version": 0.4,
  "nodes": { "...": "..." }
}
```

```json
{
  "document_type": "sjsx",
  "version": 1,
  "meta": { "domain": "TodoApp", "layer": "ui" },
  "nodes": { "...": "..." }
}
```

| `document_type` | 저장 확장자 | Queue | 비고 |
|---|---|---|---|
| `comfyui` | `.json` | ✅ 기존 동작 | `document_type` 없으면 하위 호환으로 `comfyui` 간주 |
| `sjsx` | `.sjsx` | ❌ 차단 | SjsxGraph 스키마 |

---

## 3. 아키텍처 (목표 상태)

```
┌─────────────────────────────────────────────────────────────┐
│  ComfyUI Frontend (+ sjsx 확장, --front-end-root)              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  기존 UI (유지) — canvas, queue, history, ComfyUI 팔레트  │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  추가 UI — New Workflow 다이얼로그 (ComfyUI | sjsx)       │ │
│  │           sjsx vocabulary 카테고리, Agreement 패널        │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + WebSocket (기존 ComfyUI 패턴 재사용)
┌──────────────────────────▼──────────────────────────────────┐
│  app/sjsx/  (신규 — 이 저장소)                                 │
│  · parser.py / emitter.py  — .sjsx ↔ SjsxGraph               │
│  · vocabulary.py           — 레이어별 허용 태그·속성           │
│  · agreement.py            — [ ]/[x] CRUD                      │
│  · routes.py               — /sjsx/* API                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ read/write
┌──────────────────────────▼──────────────────────────────────┐
│  design/  (sjsx)          user/default/workflows/  (comfyui)   │
│  · *.sjsx                 · *.json (기존)                       │
└─────────────────────────────────────────────────────────────┘

        doc/Sementic-JSX/index.mjs  →  Phase 0에서 로직 흡수·대체
        comfy/, execution.py        →  ComfyUI 문서만 사용 (변경 최소)
```

### 3.1 새 워크플로 생성 — 문서 타입 선택 다이얼로그

**트리거:** File → New, `Ctrl+N`, 빈 캔버스 시작, Welcome 화면 "New" 등 기존 진입점.

```
┌──────────────────────────────────────────┐
│  새 문서 만들기                            │
│                                          │
│  ┌────────────────┐  ┌────────────────┐  │
│  │  ComfyUI       │  │  Semantic JSX  │  │
│  │  Workflow      │  │  Design        │  │
│  │                │  │                │  │
│  │  이미지·비디오   │  │  UI/시스템      │  │
│  │  생성 워크플로   │  │  의도 설계      │  │
│  └────────────────┘  └────────────────┘  │
│                                          │
│              [ 취소 ]                     │
└──────────────────────────────────────────┘
```

**분기 후 동작**

| 선택 | 초기 상태 | 저장 형식 | Queue 버튼 | 추가 UI |
|---|---|---|---|---|
| **ComfyUI Workflow** | 빈 ComfyUI graph (`document_type: comfyui`) | `.json` | 기존 그대로 | 없음 (기존 UX 100%) |
| **Semantic JSX Design** | 빈 SjsxGraph + `@sjsx` meta 템플릿 | `.sjsx` | 비활성 또는 "Emit / Scaffold" | Agreement 패널, sjsx 툴바 |

**Open / Load 시:** 파일 확장자·`document_type` 필드로 자동 분기. 다이얼로그는 **새로 만들 때만** 표시.

**당분간 팔레트 정책:** sjsx 문서에서도 ComfyUI 노드는 **숨기지 않고** 표시한다. 다만 sjsx 문서에 ComfyUI 노드를 놓았을 때 Queue 실행 시 **경고** (Phase 2). 추후 "sjsx only" 필터 토글 추가 가능.

프론트엔드는 [ComfyUI_frontend](https://github.com/Comfy-Org/ComfyUI_frontend) pip 패키지(`comfyui-frontend-package`)로 배포된다. **장기적으로는 포크 + `--front-end-root` 로컬 개발**, 단기적으로는 **백엔드 API + 최소 오버레이**로 검증한다.

관련 기존 모듈: [module-map.md](../wiki/module-map.md)

---

## 4. 어디서부터 시작할까 — 권장 순서

> **첫 커밋은 UI가 아니라 IR + round-trip이다.**
> 캔버스를 먼저 바꾸면 `.sjsx` ↔ 그래프 변환 규칙 없이 UX만 그려지고, 나중에 전면 재작업이 된다.

### Phase 0 — IR & Round-trip (시작점) ⭐

**목표:** `todo-ui.sjsx`, `todo-system.sjsx`를 파싱해 `SjsxGraph` JSON을 만들고, 다시 `.sjsx` 텍스트로 내보낸다.

| 작업 | 경로 | 산출물 |
|---|---|---|
| `design/` 디렉터리 생성 | `design/` | 예제 `.sjsx` 이동 또는 symlink |
| SjsxGraph 스키마 문서화 | `doc/plans/sjsx-graph-schema.md` | JSON 필드 정의 |
| 파서·이mitter 포팅 | `app/sjsx/parser.py`, `emitter.py` | `index.mjs` 로직을 Python(+ 테스트)으로 |
| CLI 래퍼 (선택) | `app/sjsx/cli.py` 또는 `index.mjs` 개선 | `parse`, `emit`, `status` |
| 단위 테스트 | `tests-unit/sjsx_test/` | round-trip, agreement 추출, vocabulary |

**완료 기준**

- [x] `todo-ui.sjsx` parse → emit → parse 구조 동일
- [x] `agreement.agreed` / `pending` CLI `status` 출력과 일치
- [x] `layer: ui | system` 자동 분류

**건드리지 않을 것:** `server.py` 라우트, 프론트엔드, `execution.py`

**참고 코드:** `doc/Sementic-JSX/index.mjs` (`extractMeta`, `extractTodos`, `extractComponents`)

---

### Phase 1 — Backend API

**목표:** Design Mode용 HTTP API. ComfyUI 서버 기동만으로 `.sjsx` CRUD·변환 가능.

| 작업 | 경로 | 산출물 |
|---|---|---|
| 모듈 패키지 | `app/sjsx/__init__.py`, `routes.py` | aiohttp 라우트 |
| 라우트 등록 | `server.py` | `/sjsx/designs`, `/sjsx/parse`, `/sjsx/emit` |
| 파일 저장소 | `design/` | GET/PUT by filename |
| vocabulary endpoint | `/sjsx/vocabulary` | ui/system/state 태그·속성 목록 |
| agreement endpoint | `/sjsx/designs/{id}/agreement` | PATCH `[ ]`↔`[x]` |

**API 초안**

```
GET    /sjsx/designs              → 목록 + agreement % (status)
GET    /sjsx/designs/{name}       → .sjsx 원문 또는 SjsxGraph
PUT    /sjsx/designs/{name}       → 저장 (graph 또는 text)
POST   /sjsx/parse                → { "source": "..." } → SjsxGraph
POST   /sjsx/emit                 → { "graph": {...} } → .sjsx string
POST   /sjsx/scaffold/{name}      → scaffold 파일 생성 (index.mjs 로직)
GET    /sjsx/vocabulary           → 레이어별 노드 정의
```

**완료 기준**

- [x] curl/httpx로 CRUD 동작
- [x] `tests-unit/sjsx_test/test_routes.py` 통과
- [x] Wiki [Home.md](../wiki/Home.md)에 API 한 줄 링크

**건드리지 않을 것:** 프론트엔드 패키지, diffusion 노드

---

### Phase 2 — 프론트엔드 추가 (기존 UI 유지)

**목표:** ComfyUI UX를 **건드리지 않고** sjsx 편집 경로를 추가한다. 새 문서 생성 시 타입 선택 다이얼로그로 분기.

**전략:** ComfyUI_frontend **포크** + `--front-end-root` 로컬 서빙 (기존 화면 구조 위에 확장)

| 작업 | 위치 (포크 repo) | 설명 |
|---|---|---|
| **문서 타입 선택 다이얼로그** | New workflow 진입점 | ComfyUI / sjsx 카드 선택 → `document_type` 설정 |
| `document_type` store | workflow state | `comfyui` \| `sjsx` — 저장·로드·Open 시 복원 |
| SjsxGraph 로더/세이버 | save/load 분기 | sjsx → `/sjsx/designs` 또는 `.sjsx` emit; comfyui → 기존 경로 |
| sjsx vocabulary 팔레트 | node palette **추가** | `sjsx/ui`, `sjsx/system` 카테고리 — **ComfyUI 카테고리는 그대로** |
| Queue 버튼 조건부 | toolbar | `comfyui`: 기존 / `sjsx`: 비활성 + "Emit"·"Scaffold" **추가** (교체 아님) |
| Agreement sidebar | **추가** 패널 | sjsx 문서일 때만 표시; ComfyUI 문서에서는 hidden |
| ComfyUI 노드 가시성 | palette | **당분간 필터링 없음** — 모든 ComfyUI 노드 계속 표시 |

**하지 않을 것 (Phase 2)**

- 기존 메뉴·툴바 항목 삭제
- ComfyUI 노드 팔레트에서 diffusion 노드 제거
- ComfyUI workflow 저장/queue 로직 변경 (sjsx 분기만 추가)

**완료 기준**

- [ ] New → 다이얼로그 → ComfyUI 선택 시 **기존과 동일** UX
- [ ] New → 다이얼로그 → sjsx 선택 시 `.sjsx` 편집 + Agreement 패널
- [ ] sjsx 문서에서 ComfyUI 노드(KSampler 등)가 팔레트에 **보임**
- [ ] Open `.json` / `.sjsx` 시 다이얼로그 없이 자동 분기
- [ ] `todo-ui.sjsx` 로드 → 편집 → Save round-trip

**시작 파일 (ComfyUI_frontend 포크 시):**

- New workflow / blank graph 생성 핸들러 → 다이얼로그 hook
- workflow 저장/로드 (`document_type` 분기)
- node definition registry — sjsx vocabulary **append** (기존 defs 유지)
- properties panel — sjsx attrs 위젯 **추가**

---

### Phase 3 — Vocabulary & Palette

**목표:** Semantic JSX [Vocabulary layers](../Sementic-JSX/README.md#vocabulary-layers)를 ComfyUI 노드 팔레트로 등록.

| Layer | Source | Palette 카테고리 | 예시 노드 |
|---|---|---|---|
| Design | Tailwind | `sjsx/design` | (attrs `cx` only — 별도 노드 없음) |
| UI/Event | React Native | `sjsx/ui` | View, Text, FlatList, TouchableOpacity |
| State | Redux | `sjsx/state` | Store, Connect |
| System | Java/Rust-like | `sjsx/system` | ThreadPool, DbJob |

| 작업 | 경로 |
|---|---|
| vocabulary manifest | `node/sjsx/react-native/manifest.json` + 카테고리 JSON |
| 노드 메타 로더 | `node/sjsx/load.py` | `load_react_native_vocabulary()` |
| 프론트 palette 등록 | frontend: sjsx defs **추가** (ComfyUI defs 유지, 실행 no-op) |

**완료 기준**

- [x] 팔레트에 ComfyUI 노드 + sjsx 노드 **동시** 표시 (vocabulary API)
- [ ] sjsx 문서에서 `View` 드래그 → emit 시 유효 JSX (Phase 2 frontend)
- [x] system layer 파일에 ui-only 태그 경고 (layer mismatch)

---

### Phase 4 — Agreement UX & Scaffold

**목표:** README의 [Agreement loop](../Sementic-JSX/README.md#agreement-loop)를 UI에 내장.

| 기능 | 설명 |
|---|---|
| Status bar | `sjsx status` 와 동일 — 파일별 ████░░ % |
| Inline markers | pending 노드/속성에 `[ ]` 배지 |
| Review diff | 저장 전 pending 항목 요약 |
| Scaffold | UI 버튼 → `POST /sjsx/scaffold/{name}` → `*.scaffold.ts` |

**완료 기준**

- [ ] 합의 100% 미만일 때 scaffold에 TODO 주석 (index.mjs 동작과 동일)
- [ ] git diff가 의미 있는 "의도 변경"만 담음

---

### Phase 5 — 팔레트·UX 정교화 (선택, 장기)

추가형 원칙 유지한 채 **선택적** 개선.

| 항목 | 설명 |
|---|---|
| 팔레트 필터 토글 | sjsx 문서에서 "sjsx only" / "show all" — **default는 show all** |
| 크로스 타입 경고 | sjsx 문서에 KSampler 배치 시 queue·save 전 경고 |
| 템플릿 갤러리 | New 다이얼로그에 todo-ui 등 sjsx 템플릿 카드 추가 |
| upstream 머지 | `document_type` 분기를 플러그인 모듈로 격리 |

ComfyUI workflow와 sjsx design은 **별 문서**로 공존. 탭 전환 없이 File → New 다이얼로그로만 분기.

---

## 5. 첫 스프린트 작업 목록 (1~2주)

아래 순서대로 착수한다.

```
1. design/ 생성
   └── doc/Sementic-JSX/todo-ui.sjsx, todo-system.sjsx 복사 (또는 이동)

2. app/sjsx/ 스켈레톤
   ├── parser.py      ← index.mjs extractMeta/Todos/Components 발Port
   ├── emitter.py
   ├── models.py      ← SjsxGraph dataclass / pydantic
   └── vocabulary.py  ← 최소 ui + system 태그

3. tests-unit/sjsx_test/test_roundtrip.py
   └── todo-ui.sjsx, todo-system.sjsx green

4. doc/plans/sjsx-graph-schema.md (Phase 0 산출물)

5. (Phase 1 착수) app/sjsx/routes.py + server.py 5~10줄 등록
```

**첫 PR 범위:** `app/sjsx/*`, `tests-unit/sjsx_test/*`, `design/*`, `doc/plans/sjsx-graph-schema.md` — **프론트엔드 제외**.

---

## 6. 리스크와 결정 사항

| 항목 | 리스크 | 완화 |
|---|---|---|
| 프론트엔드 pip 패키지 | 소스 수정이 pip install에 덮임 | `--front-end-root` + 포크 repo |
| JSX 파싱 | `index.mjs`는 regex 기반, 불완전 | Phase 0에서 `@babel/parser` 또는 `tree-sitter` 검토 |
| ComfyUI workflow와 혼동 | sjsx graph가 queue에 들어감 | `document_type === 'sjsx'` 시 queue 차단 |
| sjsx 문서에 ComfyUI 노드 혼재 | 잘못된 emit / 실행 시도 | 당분간 노드는 보이되 경고; Phase 5에서 필터 옵션 |
| 업스트림 머지 | ComfyUI fast-moving | `app/sjsx/` + frontend sjsx 모듈 격리, 기존 코드 diff 최소 |
| 중첩 JSX / `{map}` | `forEach` in JSX — 파싱 어려움 | Phase 0는 **todo 예제 subset**; iteration은 Phase 3+ |

### 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| **UX 전략** | 추가형 — 기존 ComfyUI UI·노드 **제거하지 않음** |
| **노드 팔레트** | ComfyUI 노드 **당분간 전부 표시** + sjsx vocabulary 추가 |
| **문서 분기** | 새 워크플로 생성 시 **ComfyUI / sjsx 선택 다이얼로그** |
| **Open / Load** | 확장자·`document_type`으로 자동 분기 (다이얼로그 없음) |

### 아직 결정하지 않은 것

1. **파서 구현 언어:** Python 단일 vs Node(`index.mjs`) 유지 + Python subprocess
2. **`design/` 위치:** repo root `design/` vs `doc/Sementic-JSX/design/`
3. **다이얼로그 "다시 보지 않기"** 및 기본 선택 기억 여부

**권장 default**

- 파서: Python (`app/sjsx/`) — ComfyUI 서버와 동일 프로세스
- design: **`design/` at repo root** — README convention 준수
- 프론트: ComfyUI_frontend **포크** — New 다이얼로그 + palette append

---

## 7. 성공 지표

| 단계 | 지표 |
|---|---|
| Phase 0 | 2개 예제 `.sjsx` round-trip 테스트 green |
| Phase 1 | REST only로 `.sjsx` CRUD + parse/emit |
| Phase 2 | New 다이얼로그 분기 + sjsx 문서 편집; ComfyUI 새 문서는 기존과 동일 |
| Phase 3 | vocabulary 전체로 새 화면 scratch 작성 |
| Phase 4 | agreement % + scaffold가 CLI와 동일 출력 |

---

## 8. 관련 문서

- [Semantic JSX README](../Sementic-JSX/README.md)
- [Wiki Home](../wiki/Home.md)
- [Module Map](../wiki/module-map.md)
- [ComfyUI Frontend](https://github.com/Comfy-Org/ComfyUI_frontend)
- [ComfyUI Contributing](../../CONTRIBUTING.md)

---

## 9. 변경 이력

| 날짜 | 변경 |
|---|---|
| 2026-06-14 | 초안 작성 — Phase 0~5, 첫 스프린트, API 초안 |
| 2026-06-14 | Phase 0–1 구현: app/sjsx, design/, tests, /sjsx API, queue guard, /sjsx-app POC |
