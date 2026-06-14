import type { LGraph } from '@/lib/litegraph/src/LGraph'
import type { LGraphNode } from '@/lib/litegraph/src/LGraphNode'
import type { INodeInputSlot } from '@/lib/litegraph/src/interfaces'
import { LGraph as LGraphClass, LGraphNode as LGraphNodeClass } from '@/lib/litegraph/src/litegraph'
import {
  getSjsxTagName,
  isSjsxNodeType
} from '@/utils/sjsxNodeUtil'

declare global {
  interface Window {
    _sjsxMultiChildConnectInstalled?: boolean
  }
}

function getSjsxTagFromNode(node: LGraphNode): string {
  const ctor = node.constructor as {
    comfyClass?: string
    nodeData?: { name?: string; display_name?: string }
  }
  const type = node.type || ctor.comfyClass || ''
  return getSjsxTagName(type, ctor.nodeData)
}

export function isSjsxMultiChildInput(
  node: LGraphNode,
  input: INodeInputSlot | null | undefined
): boolean {
  if (!input || input.type !== 'SJSX') return false
  const type = node.type || (node.constructor as { comfyClass?: string }).comfyClass || ''
  if (!isSjsxNodeType(type)) return false
  const tag = getSjsxTagFromNode(node)
  if (input.name === tag) return true
  return typeof input.name === 'string' && input.name.startsWith(`${tag}.View`)
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
    const inputIndex = inputNode.inputs?.indexOf(input) ?? -1
    const multi =
      inputIndex >= 0 &&
      isSjsxMultiChildInput(inputNode, inputNode.inputs[inputIndex])
    if (multi && inputNode.inputs[inputIndex]?.link != null) {
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

  const origRemoveLink = LGraphClass.prototype.removeLink
  LGraphClass.prototype.removeLink = function removeLinkWithSjsxMulti(linkId) {
    const link = this._links.get(linkId)
    if (!link) return
    const node = this.getNodeById(link.target_id)
    const input = node?.inputs?.[link.target_slot]
    if (node && input && isSjsxMultiChildInput(node, input)) {
      const origin = this.getNodeById(link.origin_id)
      const output = origin?.outputs?.[link.origin_slot]
      if (output?.links) {
        const index = output.links.indexOf(linkId)
        if (index >= 0) output.links.splice(index, 1)
      }
      if (input.link === linkId) {
        input.link = findSiblingLinkId(
          this,
          node.id,
          link.target_slot,
          linkId
        )
      }
      link.disconnect(this)
      this.incrementVersion()
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
    if (input && isSjsxMultiChildInput(this, input) && this.graph?._links) {
      const toRemove: number[] = []
      for (const link of this.graph._links.values()) {
        if (link.target_id === this.id && link.target_slot === slotIndex) {
          toRemove.push(link.id)
        }
      }
      for (const linkId of toRemove) {
        this.graph.removeLink(linkId)
      }
      return true
    }
    return origDisconnectInput.call(this, slot, keepReroutes)
  }
}

installSjsxMultiChildConnect()
