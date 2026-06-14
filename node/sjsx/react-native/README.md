# React Native — sjsx Vocabulary

[React Native Core Components and APIs](https://reactnative.dev/docs/components-and-apis)를 sjsx UI 레이어 vocabulary로 등록한 노드 정의 모음.

## 경로

```
node/sjsx/react-native/
├── manifest.json      # 카테고리·팔레트 메타
├── basic.json         # View, Text, Image, …
├── ui.json            # Button, Switch
├── lists.json         # FlatList, SectionList, …
├── touchable.json     # TouchableOpacity, …
├── layout.json        # Modal, KeyboardAvoidingView, …
├── feedback.json      # ActivityIndicator, StatusBar, …
├── android.json       # DrawerLayoutAndroid, …
└── ios.json           # InputAccessoryView, SafeAreaView
```

ComfyUI 팔레트 카테고리: `sjsx/react-native/<category>`

## 공통 속성

모든 UI 노드는 sjsx [Vocabulary layers](../../../doc/Sementic-JSX/README.md#vocabulary-layers)에 따라 다음을 공유한다.

| 속성 | 설명 |
|---|---|
| `cx` | Tailwind 클래스 문자열 (design layer) |
| `style` | RN `style` 객체 또는 참조 (선택) |
| `testID` | 테스트·에이전트 식별자 (선택) |

## 사용

Phase 3 vocabulary 로더(`node/sjsx/load.py` → `load_react_native_vocabulary()`)가 `manifest.json` → 카테고리 JSON을 읽어 `/sjsx/vocabulary` 및 프론트 팔레트에 **추가**한다. ComfyUI diffusion 노드는 제거하지 않는다.

## 출처

- [Core Components and APIs · React Native](https://reactnative.dev/docs/components-and-apis) (v0.85)
