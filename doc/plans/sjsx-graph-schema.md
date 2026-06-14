# SjsxGraph JSON Schema (v1)

`.sjsx` ↔ ComfyUI sjsx 편집기 ↔ `/sjsx/*` API 공통 IR.

## Root

| Field | Type | Required | Description |
|---|---|---|---|
| `document_type` | `"sjsx"` | yes | ComfyUI workflow(`comfyui`)와 구분 |
| `version` | `number` | yes | 현재 `1` |
| `header` | `string` | no | `@sjsx` JSDoc 블록 원문 |
| `meta` | `object` | yes | domain / layer / status |
| `agreement` | `object` | yes | `[x]` / `[ ]` 합의 상태 |
| `sections` | `array` | yes | 섹션 코멘트 + const 정의 |
| `components` | `string[]` | no | 파일 내 JSX 태그 목록 |
| `nodes` | `object` | no | shallow graph (Phase 0) |
| `bindings` | `object` | no | 이벤트 바인딩 (Phase 3+) |
| `comments` | `string[]` | no | 기타 주석 |

## meta

```json
{
  "domain": "TodoApp",
  "layer": "ui",
  "status": "design"
}
```

| layer | 설명 |
|---|---|
| `ui` | React Native UI (`node/sjsx/react-native/`) |
| `system` | workers, DB (`node/sjsx/system/`) |
| `state` | Store, Connect |

## agreement

```json
{
  "agreed": ["화면 구조"],
  "pending": ["에러 상태 처리"]
}
```

## sections[]

```json
{
  "comment": "// ─── UI Layer ───",
  "definitions": [
    {
      "name": "TodoApp",
      "body": "(\\n  <View cx=\\\"...\\\">\\n  ...\\n)"
    }
  ]
}
```

Round-trip: `emit(parse(source))` preserves `header`, `sections[].definitions[].name/body`, `agreement`.

## nodes{} (optional shallow view)

```json
{
  "1": {
    "type": "View",
    "attrs": { "cx": "flex-1" },
    "children": [],
    "content": null
  }
}
```

## document_type 분기

| Type | Extension | Queue |
|---|---|---|
| `comfyui` | `.json` | allowed |
| `sjsx` | `.sjsx` | blocked (`extra_data.document_type === "sjsx"`) |

## API

See [comfyui-sjsx-editor.md](./comfyui-sjsx-editor.md) Phase 1.
