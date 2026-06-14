import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { IBaseWidget } from '@/lib/litegraph/src/types/widgets'
import { ref } from 'vue'
import { app } from '@/scripts/app'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { useWidgetValueStore } from '@/stores/widgetValueStore'
import { getWidgetDefaultValue } from '@/utils/widgetUtil'

import { isSjsxNodeType } from '@/utils/sjsxNodeUtil'

/** @deprecated Read-only legacy workflow key; migrated to {@link SJSX_ACTIVE_PARAMS_KEY}. */
const SJSX_ACTIVE_PROPS_LEGACY_KEY = 'sjsxActiveProps'
/** @deprecated Read-only legacy workflow key; migrated to {@link SJSX_PARAMS_VERSION_KEY}. */
const SJSX_PARAMS_VERSION_LEGACY_KEY = 'sjsxPropsVersion'

export const SJSX_ACTIVE_PARAMS_KEY = 'sjsxActiveParams'
export const SJSX_PARAMS_VERSION_KEY = 'sjsxParamsVersion'
export const sjsxParamsRevision = ref(0)

export interface SjsxParamSuggestion {
  name: string
  kind: 'attr' | 'event' | 'content'
  description?: string
}

function getGraphId(node: LGraphNode): string | undefined {
  return node.graph?.rootGraph?.id ?? node.graph?.id
}

export function getSjsxLGraphNode(
  nodeId: string | number | undefined
): LGraphNode | null {
  if (nodeId == null) return null
  const graph = app.graph ?? app.rootGraph
  return graph?.getNodeById(nodeId) ?? null
}

function migrateLegacyParamKeys(node: LGraphNode) {
  node.properties ??= {}
  const props = node.properties

  if (
    props[SJSX_ACTIVE_PARAMS_KEY] === undefined &&
    Array.isArray(props[SJSX_ACTIVE_PROPS_LEGACY_KEY])
  ) {
    props[SJSX_ACTIVE_PARAMS_KEY] = props[SJSX_ACTIVE_PROPS_LEGACY_KEY]
    delete props[SJSX_ACTIVE_PROPS_LEGACY_KEY]
  }

  if (
    props[SJSX_PARAMS_VERSION_KEY] === undefined &&
    props[SJSX_PARAMS_VERSION_LEGACY_KEY] !== undefined
  ) {
    props[SJSX_PARAMS_VERSION_KEY] = props[SJSX_PARAMS_VERSION_LEGACY_KEY]
    delete props[SJSX_PARAMS_VERSION_LEGACY_KEY]
  }
}

export function getSjsxActiveParams(node: LGraphNode): string[] {
  migrateLegacyParamKeys(node)
  const stored = node.properties?.[SJSX_ACTIVE_PARAMS_KEY]
  return Array.isArray(stored) ? stored.filter((v) => typeof v === 'string') : []
}

export function isSjsxWidgetShownInUi(
  node: LGraphNode,
  widget: IBaseWidget,
  includesAdvanced = false
): boolean {
  sjsxParamsRevision.value
  const nodeType = node.type || node.constructor?.comfyClass
  if (isSjsxNodeType(nodeType)) {
    return getSjsxActiveParams(node).includes(widget.name)
  }
  return !(
    widget.options?.canvasOnly ||
    widget.options?.hidden ||
    (widget.options?.advanced && !includesAdvanced)
  )
}

function setSjsxActiveParams(node: LGraphNode, names: string[]) {
  node.properties ??= {}
  node.properties[SJSX_ACTIVE_PARAMS_KEY] = [...new Set(names)]
  delete node.properties[SJSX_ACTIVE_PROPS_LEGACY_KEY]
}

function bumpParamsVersion(node: LGraphNode) {
  node.properties ??= {}
  const current = Number(node.properties[SJSX_PARAMS_VERSION_KEY] ?? 0)
  node.properties[SJSX_PARAMS_VERSION_KEY] = current + 1
  delete node.properties[SJSX_PARAMS_VERSION_LEGACY_KEY]
  sjsxParamsRevision.value++
}

function notifyWidgetsChanged(node: LGraphNode) {
  const widgets = node.widgets
  if (!widgets?.length) return
  widgets.splice(0, widgets.length, ...widgets)
}

function syncWidgetStoreVisibility(
  node: LGraphNode,
  widget: IBaseWidget,
  visible: boolean
) {
  const graphId = getGraphId(node)
  if (!graphId) return
  const state = useWidgetValueStore().getWidget(
    graphId,
    String(node.id),
    widget.name
  )
  if (!state) return
  state.options = {
    ...(state.options ?? {}),
    hidden: !visible,
    advanced: !visible
  }
}

export function setSjsxWidgetVisible(
  node: LGraphNode,
  widget: IBaseWidget,
  visible: boolean
) {
  widget.hidden = !visible
  widget.advanced = !visible
  widget.options ??= {}
  widget.options.hidden = !visible
  widget.options.advanced = !visible
  syncWidgetStoreVisibility(node, widget, visible)
}

function findSjsxWidget(
  node: LGraphNode,
  name: string
): IBaseWidget | undefined {
  return node.widgets?.find((widget) => widget.name === name)
}

function addCustomSjsxWidget(node: LGraphNode, name: string): IBaseWidget {
  return node.addWidget('text', name, '', name, {
    socketless: true,
    hidden: false,
    advanced: false
  })
}

export function hideAllSjsxWidgets(
  node: LGraphNode,
  except = new Set<string>()
) {
  for (const widget of node.widgets ?? []) {
    if (except.has(widget.name)) continue
    setSjsxWidgetVisible(node, widget, false)
  }
}

export function showSjsxParam(node: LGraphNode, name: string): boolean {
  const trimmed = name.trim()
  if (!trimmed) return false

  const active = getSjsxActiveParams(node)
  if (active.includes(trimmed)) return false

  let widget = findSjsxWidget(node, trimmed)
  if (!widget) {
    widget = addCustomSjsxWidget(node, trimmed)
  }

  setSjsxWidgetVisible(node, widget, true)
  setSjsxActiveParams(node, [...active, trimmed])
  bumpParamsVersion(node)
  notifyWidgetsChanged(node)
  node.expandToFitContent()
  node.setDirtyCanvas(true, true)
  return true
}

function resetSjsxWidgetValue(node: LGraphNode, widget: IBaseWidget) {
  const spec = useNodeDefStore().getInputSpecForWidget(node, widget.name)
  const defaultValue = getWidgetDefaultValue(spec)
  if (defaultValue !== undefined) {
    widget.value = defaultValue as typeof widget.value
    return
  }
  if (widget.type === 'toggle' || widget.type === 'boolean') {
    widget.value = false as typeof widget.value
    return
  }
  widget.value = '' as typeof widget.value
}

export function removeSjsxParam(node: LGraphNode, name: string): boolean {
  const trimmed = name.trim()
  if (!trimmed) return false

  const active = getSjsxActiveParams(node)
  if (!active.includes(trimmed)) return false

  const widget = findSjsxWidget(node, trimmed)
  if (widget) {
    resetSjsxWidgetValue(node, widget)
    const spec = useNodeDefStore().getInputSpecForWidget(node, trimmed)
    if (spec) {
      setSjsxWidgetVisible(node, widget, false)
    } else {
      node.ensureWidgetRemoved(widget)
    }
  }

  setSjsxActiveParams(
    node,
    active.filter((param) => param !== trimmed)
  )
  bumpParamsVersion(node)
  notifyWidgetsChanged(node)
  node.expandToFitContent()
  node.setDirtyCanvas(true, true)
  return true
}

export function initSjsxNodeParams(
  node: LGraphNode,
  { restoreFromValues = false }: { restoreFromValues?: boolean } = {}
) {
  if (!isSjsxNodeType(node.type || node.constructor?.comfyClass)) return

  migrateLegacyParamKeys(node)
  node.properties ??= {}
  if (!Array.isArray(node.properties[SJSX_ACTIVE_PARAMS_KEY])) {
    node.properties[SJSX_ACTIVE_PARAMS_KEY] = []
  }

  hideAllSjsxWidgets(node)

  const active = new Set<string>(getSjsxActiveParams(node))

  if (restoreFromValues) {
    for (const widget of node.widgets ?? []) {
      const value = widget.value
      const hasValue =
        value !== undefined &&
        value !== null &&
        value !== '' &&
        !(typeof value === 'boolean' && value === false)
      if (hasValue) active.add(widget.name)
    }
    setSjsxActiveParams(node, [...active])
  }

  for (const name of active) {
    const widget = findSjsxWidget(node, name) ?? addCustomSjsxWidget(node, name)
    setSjsxWidgetVisible(node, widget, true)
  }

  bumpParamsVersion(node)
  notifyWidgetsChanged(node)
}
