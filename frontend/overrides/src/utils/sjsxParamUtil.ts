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
export const SJSX_WIDGET_VALUES_KEY = 'sjsxWidgetValues'
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

function isMeaningfulSjsxParamValue(value: unknown): boolean {
  if (value === undefined || value === null || value === '') return false
  if (typeof value === 'boolean' && value === false) return false
  if (typeof value === 'number' && value === 0) return false
  return true
}

function restoreActiveParamsFromStored(node: LGraphNode, active: Set<string>) {
  const stored = node.properties?.[SJSX_WIDGET_VALUES_KEY]
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return
  for (const [name, value] of Object.entries(stored)) {
    if (isMeaningfulSjsxParamValue(value)) active.add(name)
  }
}

function collectOnChangeKeysFromSubtree(
  graph: NonNullable<LGraphNode['graph']>,
  root: LGraphNode
): string[] {
  const keys: string[] = []

  function resolveLink(linkId: number | string) {
    const links = graph.links
    if (!links) return null
    if (typeof links === 'object' && 'get' in links && typeof links.get === 'function') {
      return links.get(Number(linkId)) ?? null
    }
    return (links as Record<string, unknown>)[String(linkId)] ?? null
  }

  function getChildNodes(parent: LGraphNode): LGraphNode[] {
    const children: LGraphNode[] = []
    for (const input of parent.inputs ?? []) {
      if (input.type !== 'SJSX' || input.link == null) continue
      const link = resolveLink(input.link) as {
        origin_id?: number
        1?: number
      } | null
      if (!link) continue
      const originId = link.origin_id ?? link[1]
      const child = graph.getNodeById(originId)
      if (child) children.push(child)
    }
    return children
  }

  function walk(parent: LGraphNode) {
    for (const child of getChildNodes(parent)) {
      const nodeType = child.type || child.constructor?.comfyClass
      if (nodeType === 'Sjsx_TextInput') {
        const active = getSjsxActiveParams(child)
        if (active.includes('onChange')) {
          const widget = findSjsxWidget(child, 'onChange')
          const stored = child.properties?.[SJSX_WIDGET_VALUES_KEY]
          const fromStored =
            stored &&
            typeof stored === 'object' &&
            !Array.isArray(stored) &&
            typeof stored.onChange === 'string'
              ? stored.onChange
              : ''
          const value = String(widget?.value ?? fromStored ?? '').trim()
          if (value && value !== 'value') keys.push(value)
        }
      }
      walk(child)
    }
  }

  walk(root)
  return [...new Set(keys)].sort()
}

export function ensureViewStateFromChildren(node: LGraphNode): void {
  const nodeType = node.type || node.constructor?.comfyClass
  if (nodeType !== 'Sjsx_View') return

  const graph = node.graph ?? app.graph ?? app.rootGraph
  if (!graph) return

  const stored = node.properties?.[SJSX_WIDGET_VALUES_KEY]
  const existing =
    stored &&
    typeof stored === 'object' &&
    !Array.isArray(stored) &&
    typeof stored.state === 'string'
      ? stored.state.trim()
      : ''
  if (existing) return

  const derived = collectOnChangeKeysFromSubtree(graph, node)
  if (!derived.length) return

  const state = derived.length === 1 ? derived[0] : derived.join(', ')
  const active = new Set(getSjsxActiveParams(node))
  active.add('state')
  setSjsxActiveParams(node, [...active])

  const widget = findSjsxWidget(node, 'state') ?? addCustomSjsxWidget(node, 'state')
  widget.value = state as typeof widget.value
  setSjsxWidgetVisible(node, widget, true)
  syncSjsxWidgetValuesToProperties(node)
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

function readLiveSjsxWidgetValue(node: LGraphNode, name: string): unknown {
  const graphId = getGraphId(node)
  if (graphId) {
    const storeState = useWidgetValueStore().getWidget(
      graphId,
      String(node.id),
      name
    )
    if (storeState && 'value' in storeState && storeState.value !== undefined) {
      return storeState.value
    }
  }
  return findSjsxWidget(node, name)?.value ?? ''
}

function ensureSjsxWidgetValueSyncHook(node: LGraphNode, widget: IBaseWidget) {
  const tagged = widget as IBaseWidget & { _sjsxValueSyncHook?: boolean }
  if (tagged._sjsxValueSyncHook) return
  tagged._sjsxValueSyncHook = true
  const original = widget.callback
  widget.callback = function (...args) {
    const result = original?.apply(this, args)
    syncSjsxWidgetValuesToProperties(node)
    node.setDirtyCanvas(true, true)
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('sjsx:widget-values-changed', {
          detail: { nodeId: node.id }
        })
      )
    }
    return result
  }
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
  ensureSjsxWidgetValueSyncHook(node, widget)
  syncSjsxWidgetValuesToProperties(node)
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
  syncSjsxWidgetValuesToProperties(node)
  bumpParamsVersion(node)
  notifyWidgetsChanged(node)
  node.expandToFitContent()
  node.setDirtyCanvas(true, true)
  return true
}

export function repairSjsxWidgetValues(node: LGraphNode): void {
  const stored = node.properties?.[SJSX_WIDGET_VALUES_KEY]
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return

  for (const widget of node.widgets ?? []) {
    const name = widget.name
    if (!name || !(name in stored)) continue
    widget.value = stored[name] as typeof widget.value
  }
}

export function syncSjsxWidgetValuesToProperties(node: LGraphNode): void {
  if (!isSjsxNodeType(node.type || node.constructor?.comfyClass)) return

  const map: Record<string, unknown> = {}
  for (const name of getSjsxActiveParams(node)) {
    map[name] = readLiveSjsxWidgetValue(node, name)
  }

  node.properties ??= {}
  node.properties[SJSX_WIDGET_VALUES_KEY] = map
}

export function initSjsxNodeParams(
  node: LGraphNode,
  { restoreFromValues = false }: { restoreFromValues?: boolean } = {}
) {
  if (!isSjsxNodeType(node.type || node.constructor?.comfyClass)) return

  repairSjsxWidgetValues(node)

  migrateLegacyParamKeys(node)
  node.properties ??= {}
  if (!Array.isArray(node.properties[SJSX_ACTIVE_PARAMS_KEY])) {
    node.properties[SJSX_ACTIVE_PARAMS_KEY] = []
  }

  hideAllSjsxWidgets(node)

  const active = new Set<string>(getSjsxActiveParams(node))
  const stored = node.properties?.[SJSX_WIDGET_VALUES_KEY]
  restoreActiveParamsFromStored(node, active)

  if (restoreFromValues) {
    for (const widget of node.widgets ?? []) {
      if (isMeaningfulSjsxParamValue(widget.value)) active.add(widget.name)
    }
    if ((node.type || node.constructor?.comfyClass) === 'Sjsx_View') {
      ensureViewStateFromChildren(node)
      restoreActiveParamsFromStored(node, active)
      for (const name of getSjsxActiveParams(node)) active.add(name)
    }
  }

  setSjsxActiveParams(node, [...active])

  const valuesSnapshot = node.properties?.[SJSX_WIDGET_VALUES_KEY]

  for (const name of active) {
    const widget = findSjsxWidget(node, name) ?? addCustomSjsxWidget(node, name)
    setSjsxWidgetVisible(node, widget, true)
    ensureSjsxWidgetValueSyncHook(node, widget)
    if (
      valuesSnapshot &&
      typeof valuesSnapshot === 'object' &&
      !Array.isArray(valuesSnapshot) &&
      name in valuesSnapshot &&
      isMeaningfulSjsxParamValue(valuesSnapshot[name])
    ) {
      widget.value = valuesSnapshot[name] as typeof widget.value
    }
  }

  syncSjsxWidgetValuesToProperties(node)
  bumpParamsVersion(node)
  notifyWidgetsChanged(node)
}
