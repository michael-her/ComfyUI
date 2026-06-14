import type { LGraph } from '@/lib/litegraph/src/LGraph'
import type { LGraphNode } from '@/lib/litegraph/src/LGraphNode'
import type { INodeInputSlot, Point } from '@/lib/litegraph/src/interfaces'
import type { LLink } from '@/lib/litegraph/src/LLink'
import type { Reroute } from '@/lib/litegraph/src/Reroute'
import {
  LGraph as LGraphClass,
  LGraphCanvas as LGraphCanvasClass,
  LGraphNode as LGraphNodeClass,
  LiteGraph
} from '@/lib/litegraph/src/litegraph'
import { parseSlotTypes } from '@/lib/litegraph/src/strings'
import { LinkRenderType } from '@/lib/litegraph/src/types/globalEnums'
import { findFreeSlotOfType } from '@/lib/litegraph/src/utils/collections'
import { getSlotPosition } from '@/renderer/core/canvas/litegraph/slotCalculations'
import { layoutStore } from '@/renderer/core/layout/store/layoutStore'
import { app } from '@/scripts/app'
import {
  initSjsxNodeParams,
  repairSjsxWidgetValues
} from '@/utils/sjsxParamUtil'
import {
  getSjsxTagName,
  isSjsxNodeType
} from '@/utils/sjsxNodeUtil'

declare global {
  interface Window {
    _sjsxMultiChildConnectInstalled?: boolean
    _sjsxMultiChildMarkersRegistered?: boolean
    _sjsxInspectMultiConnect?: (nodeId: string | number) => Record<string, unknown>
  }
}

export const SJSX_ALLOW_MULTI_CONNECT = '_sjsxAllowMultiConnect'

type SjsxInputSlot = INodeInputSlot & {
  [SJSX_ALLOW_MULTI_CONNECT]?: boolean
}

function getNodeTypeName(node: LGraphNode): string {
  const inst = node as LGraphNode & { comfyClass?: string }
  const ctor = node.constructor as {
    comfyClass?: string
    nodeData?: { name?: string; display_name?: string }
  }
  return String(
    node.type || inst.comfyClass || ctor.comfyClass || ctor.nodeData?.name || ''
  ).trim()
}

function getSjsxTagFromNode(node: LGraphNode): string {
  const ctor = node.constructor as {
    comfyClass?: string
    nodeData?: { name?: string; display_name?: string }
  }
  return getSjsxTagName(getNodeTypeName(node), ctor.nodeData)
}

function isSjsxContainerNode(node: LGraphNode): boolean {
  return isSjsxNodeType(getNodeTypeName(node))
}

function isSjsxSlotType(type: string | null | undefined): boolean {
  if (!type) return false
  return parseSlotTypes(type).includes('sjsx')
}

function getInputSlotName(input: INodeInputSlot): string {
  return String(input.name || input.label || input.localized_name || '').trim()
}

function firstSjsxChildInputIndex(node: LGraphNode): number {
  return (node.inputs ?? []).findIndex((slot) => isSjsxSlotType(slot.type))
}

export function markSjsxMultiChildInputs(node: LGraphNode): void {
  if (!isSjsxContainerNode(node)) return
  for (let index = 0; index < (node.inputs?.length ?? 0); index += 1) {
    const input = node.inputs![index]!
    if (isSjsxMultiChildInput(node, input, index)) {
      ;(input as SjsxInputSlot)[SJSX_ALLOW_MULTI_CONNECT] = true
    }
  }
}

export function isSjsxMultiChildInput(
  node: LGraphNode,
  input: INodeInputSlot | null | undefined,
  inputIndex?: number
): boolean {
  if (!input || !isSjsxSlotType(input.type)) return false
  if ((input as SjsxInputSlot)[SJSX_ALLOW_MULTI_CONNECT]) return true
  if (!isSjsxContainerNode(node)) return false

  const tag = getSjsxTagFromNode(node)
  const name = getInputSlotName(input)
  if (name === tag || name.startsWith(`${tag}.`)) return true

  const resolvedIndex =
    inputIndex ??
    node.inputs?.indexOf(input) ??
    node.inputs?.findIndex(
      (slot) =>
        getInputSlotName(slot) === name && isSjsxSlotType(slot.type)
    ) ??
    -1
  return resolvedIndex >= 0 && resolvedIndex === firstSjsxChildInputIndex(node)
}

function resolveInputIndex(
  node: LGraphNode,
  input: INodeInputSlot
): number {
  const direct = node.inputs?.indexOf(input) ?? -1
  if (direct >= 0) return direct

  const name = getInputSlotName(input)
  if (!name) return -1
  return (
    node.inputs?.findIndex(
      (slot) =>
        slot.name === name ||
        slot.label === name ||
        slot.localized_name === name
    ) ?? -1
  )
}

function slotIsFreeForConnect(
  node: LGraphNode,
  input: INodeInputSlot,
  inputIndex: number
): boolean {
  if (isSjsxMultiChildInput(node, input, inputIndex)) return true
  return (
    input.link == null || !!node.graph?.getLink(input.link)?._dragging
  )
}

function findSiblingLinkId(
  graph: LGraph,
  targetId: LGraphNode['id'],
  targetSlot: number,
  excludeId: number
): number | null {
  for (const link of graph._links.values()) {
    if (link.id === excludeId) continue
    if (link.target_id === targetId && link.target_slot === targetSlot) {
      return link.id
    }
  }
  return null
}

function disconnectSjsxMultiChildLink(
  graph: LGraph,
  node: LGraphNode,
  linkId: number
): void {
  const link = graph._links.get(linkId)
  if (!link) return

  const origin = graph.getNodeById(link.origin_id)
  const output = origin?.outputs?.[link.origin_slot]
  if (output?.links) {
    const index = output.links.indexOf(linkId)
    if (index >= 0) output.links.splice(index, 1)
  }

  const input = node.inputs?.[link.target_slot]
  if (input?.link === linkId) {
    input.link = findSiblingLinkId(
      graph,
      node.id,
      link.target_slot,
      linkId
    )
  }

  link.disconnect(graph)
  graph.incrementVersion()
}

function collectSjsxChildLinkIds(
  graph: LGraph,
  node: LGraphNode,
  inputIndex: number
): number[] {
  const input = node.inputs?.[inputIndex]
  if (!input || !isSjsxMultiChildInput(node, input, inputIndex)) return []

  const ids: number[] = []
  for (const link of graph._links.values()) {
    if (link.target_id === node.id && link.target_slot === inputIndex) {
      ids.push(link.id)
    }
  }
  return ids
}

type LinkDrawingCanvas = {
  graph: LGraph | null
  links_render_mode: LinkRenderType
  _renderAllLinkSegments: (
    ctx: CanvasRenderingContext2D,
    link: LLink,
    startPos: Point,
    endPos: Point,
    visibleReroutes: Reroute[],
    now: number,
    startDir: INodeInputSlot['dir'],
    endDir: INodeInputSlot['dir']
  ) => void
}

function patchSjsxMultiChildLinkDrawing(): void {
  const origDrawConnections = LGraphCanvasClass.prototype.drawConnections
  LGraphCanvasClass.prototype.drawConnections = function drawConnectionsWithSjsxMulti(
    ctx
  ) {
    origDrawConnections.call(this, ctx)

    const canvas = this as LinkDrawingCanvas
    const graph = canvas.graph
    if (!graph || canvas.links_render_mode === LinkRenderType.HIDDEN_LINK) return
    if (LiteGraph.vueNodesMode && layoutStore.pendingSlotSync) return

    const now = LiteGraph.getTime()
    const visibleReroutes: Reroute[] = []

    for (const node of graph._nodes) {
      const inputs = node.inputs
      if (!inputs?.length) continue

      for (const [inputIndex, input] of inputs.entries()) {
        if (!input) continue

        const linkIds = collectSjsxChildLinkIds(graph, node, inputIndex)
        if (linkIds.length <= 1) continue

        const primaryLinkId = input.link
        for (const linkId of linkIds) {
          if (linkId === primaryLinkId) continue

          const link = graph._links.get(linkId)
          if (!link) continue

          const startNode = graph.getNodeById(link.origin_id)
          if (!startNode) continue

          const outputIndex = link.origin_slot
          const output = startNode.outputs?.[outputIndex]
          if (!output) continue

          const endPos: Point = LiteGraph.vueNodesMode
            ? getSlotPosition(node, inputIndex, true)
            : node.getInputPos(inputIndex)

          const startPos: Point =
            outputIndex === -1
              ? [startNode.pos[0] + 10, startNode.pos[1] + 10]
              : LiteGraph.vueNodesMode
                ? getSlotPosition(startNode, outputIndex, false)
                : startNode.getOutputPos(outputIndex)

          canvas._renderAllLinkSegments(
            ctx,
            link,
            startPos,
            endPos,
            visibleReroutes,
            now,
            output.dir,
            input.dir
          )
        }
      }
    }
  }
}

export function installSjsxMultiChildConnect(): void {
  if (window._sjsxMultiChildConnectInstalled) return
  window._sjsxMultiChildConnectInstalled = true

  const origConnectSlots = LGraphNodeClass.prototype.connectSlots
  LGraphNodeClass.prototype.connectSlots = function connectSlotsWithSjsxMulti(
    output,
    inputNode,
    input,
    afterRerouteId
  ) {
    const inputIndex = resolveInputIndex(inputNode, input)
    const slot = inputIndex >= 0 ? inputNode.inputs?.[inputIndex] : input
    const multi = Boolean(
      slot && isSjsxMultiChildInput(inputNode, slot, inputIndex)
    )

    if (multi && inputIndex >= 0 && inputNode.inputs[inputIndex]?.link != null) {
      const previousLink = inputNode.inputs[inputIndex].link
      inputNode.inputs[inputIndex].link = null
      const created = origConnectSlots.call(
        this,
        output,
        inputNode,
        input,
        afterRerouteId
      )
      if (created) {
        inputNode.inputs[inputIndex].link = previousLink ?? created.id
      } else {
        inputNode.inputs[inputIndex].link = previousLink
      }
      return created
    }

    return origConnectSlots.call(this, output, inputNode, input, afterRerouteId)
  }

  const origFindInputByType = LGraphNodeClass.prototype.findInputByType
  LGraphNodeClass.prototype.findInputByType = function findInputByTypeWithSjsxMulti(
    type
  ) {
    const multiAware = findFreeSlotOfType(
      this.inputs ?? [],
      type,
      (input) => {
        const index = this.inputs?.indexOf(input) ?? -1
        return slotIsFreeForConnect(this, input, index)
      }
    )
    if (multiAware) return multiAware
    return origFindInputByType.call(this, type)
  }

  const origRemoveLink = LGraphClass.prototype.removeLink
  LGraphClass.prototype.removeLink = function removeLinkWithSjsxMulti(linkId) {
    const link = this._links.get(linkId)
    if (!link) return
    const node = this.getNodeById(link.target_id)
    const input = node?.inputs?.[link.target_slot]
    if (node && input && isSjsxMultiChildInput(node, input, link.target_slot)) {
      disconnectSjsxMultiChildLink(this, node, linkId)
      return
    }
    origRemoveLink.call(this, linkId)
  }

  const origDisconnectInput = LGraphNodeClass.prototype.disconnectInput
  LGraphNodeClass.prototype.disconnectInput = function disconnectInputWithSjsxMulti(
    slot,
    keepReroutes
  ) {
    const slotIndex =
      typeof slot === 'string' ? this.findInputSlot(slot) : slot
    const input = this.inputs?.[slotIndex]
    if (input && isSjsxMultiChildInput(this, input, slotIndex) && this.graph?._links) {
      if (keepReroutes) {
        return origDisconnectInput.call(this, slot, keepReroutes)
      }

      const toRemove: number[] = []
      for (const link of this.graph._links.values()) {
        if (link.target_id === this.id && link.target_slot === slotIndex) {
          toRemove.push(link.id)
        }
      }
      for (const linkId of toRemove) {
        disconnectSjsxMultiChildLink(this.graph, this, linkId)
      }
      return true
    }
    return origDisconnectInput.call(this, slot, keepReroutes)
  }

  window._sjsxInspectMultiConnect = (nodeId) => {
    const graph = app.graph ?? app.rootGraph
    const node = graph?.getNodeById(nodeId)
    if (!node) return { error: 'node not found', nodeId }

    const childIndex = firstSjsxChildInputIndex(node)
    const input = childIndex >= 0 ? node.inputs?.[childIndex] : undefined
    const links = [...(graph?._links.values() ?? [])].filter(
      (link) => link.target_id === node.id && link.target_slot === childIndex
    )

    return {
      nodeType: getNodeTypeName(node),
      childInputIndex: childIndex,
      inputName: input ? getInputSlotName(input) : null,
      inputType: input?.type ?? null,
      isMulti: input ? isSjsxMultiChildInput(node, input, childIndex) : false,
      marked: Boolean(
        input && (input as SjsxInputSlot)[SJSX_ALLOW_MULTI_CONNECT]
      ),
      primaryLinkId: input?.link ?? null,
      childLinkCount: links.length,
      childLinks: links.map((link) => ({
        id: link.id,
        origin_id: link.origin_id,
        origin_slot: link.origin_slot
      }))
    }
  }

  patchSjsxMultiChildLinkDrawing()
}

/** Requires Pinia — call from App.vue onMounted, not at module load. */
export function registerSjsxMultiChildMarkers(): void {
  if (window._sjsxMultiChildMarkersRegistered) return
  window._sjsxMultiChildMarkersRegistered = true

  app.registerExtension({
    name: 'Sementic.Sjsx.MultiConnectMarkers',
    nodeCreated(node) {
      repairSjsxWidgetValues(node)
      initSjsxNodeParams(node)
      markSjsxMultiChildInputs(node)
    },
    loadedGraphNode(node) {
      repairSjsxWidgetValues(node)
      initSjsxNodeParams(node, { restoreFromValues: true })
      markSjsxMultiChildInputs(node)
    },
    afterConfigureGraph() {
      const graph = app.graph ?? app.rootGraph
      for (const node of graph?._nodes ?? []) {
        repairSjsxWidgetValues(node)
        initSjsxNodeParams(node, { restoreFromValues: true })
        markSjsxMultiChildInputs(node)
      }
    }
  })

  const graph = app.graph ?? app.rootGraph
  for (const node of graph?._nodes ?? []) {
    markSjsxMultiChildInputs(node)
  }
}

installSjsxMultiChildConnect()
