/**
 * Node Event Handlers Composable
 *
 * Handles all Vue node interaction events including:
 * - Node selection with multi-select support
 * - Node collapse/expand state management
 * - Node title editing and updates
 * - Layout mutations for visual feedback
 * - Integration with LiteGraph canvas selection system
 */
import { createSharedComposable } from '@vueuse/core'

import { useVueNodeLifecycle } from '@/composables/graph/useVueNodeLifecycle'
import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import { useCanvasInteractions } from '@/renderer/core/canvas/useCanvasInteractions'
import { useNodeZIndex } from '@/renderer/extensions/vueNodes/composables/useNodeZIndex'
import { isMultiSelectKey } from '@/renderer/extensions/vueNodes/utils/selectionUtils'
import { isSjsxNodeDef, isSjsxNodeType } from '@/utils/sjsxNodeUtil'
import type { NodeId } from '@/renderer/core/layout/types'
import { useNodeDefStore } from '@/stores/nodeDefStore'

function useNodeEventHandlersIndividual() {
  const canvasStore = useCanvasStore()
  const { nodeManager } = useVueNodeLifecycle()
  const { bringNodeToFront } = useNodeZIndex()
  const { shouldHandleNodePointerEvents } = useCanvasInteractions()
  const nodeDefStore = useNodeDefStore()

  function isSjsxGraphNode(node: {
    type?: string
    constructor?: { comfyClass?: string }
  }) {
    const nodeType = node.type || node.constructor?.comfyClass || ''
    if (isSjsxNodeType(nodeType)) return true
    return isSjsxNodeDef(nodeDefStore.nodeDefsByName[nodeType])
  }

  function handleNodeSelect(event: PointerEvent, nodeId: NodeId) {
    if (!shouldHandleNodePointerEvents.value) return

    if (!canvasStore.canvas || !nodeManager.value) return

    const node = nodeManager.value.getNode(nodeId)
    if (!node) return

    const multiSelect = isMultiSelectKey(event)
    const selectedItemsCount = canvasStore.selectedItems.length
    const preserveExistingSelection =
      !multiSelect && node.selected && selectedItemsCount > 1

    if (multiSelect) {
      if (!node.selected) {
        canvasStore.canvas.select(node)
      }
    } else if (!preserveExistingSelection) {
      canvasStore.canvas.deselectAll()
      canvasStore.canvas.select(node)
    }

    if (!node.flags?.pinned) {
      bringNodeToFront(nodeId)
    }

    canvasStore.updateSelectedItems()
  }

  function handleNodeCollapse(nodeId: NodeId, collapsed: boolean) {
    if (!shouldHandleNodePointerEvents.value) return

    if (!nodeManager.value) return

    const node = nodeManager.value.getNode(nodeId)
    if (!node) return

    const currentCollapsed = node.flags?.collapsed ?? false
    if (currentCollapsed !== collapsed) {
      node.collapse()
    }
  }

  function handleNodeTitleUpdate(nodeId: NodeId, newTitle: string) {
    if (!shouldHandleNodePointerEvents.value) return

    if (!nodeManager.value) return

    const node = nodeManager.value.getNode(nodeId)
    if (!node) return

    const trimmedTitle = newTitle.trim()

    if (isSjsxGraphNode(node)) {
      node.title = trimmedTitle
      return
    }

    node.title = newTitle

    if (node.isSubgraphNode?.()) {
      node.subgraph.name = newTitle
    }
  }

  function handleNodeRightClick(event: PointerEvent, nodeId: NodeId) {
    if (!shouldHandleNodePointerEvents.value) return

    if (!canvasStore.canvas || !nodeManager.value) return

    const node = nodeManager.value.getNode(nodeId)
    if (!node) return

    event.preventDefault()

    if (!node.selected) {
      handleNodeSelect(event, nodeId)
    }
  }

  function toggleNodeSelectionAfterPointerUp(
    nodeId: NodeId,
    multiSelect: boolean
  ) {
    if (!shouldHandleNodePointerEvents.value) return

    if (!canvasStore.canvas || !nodeManager.value) return

    const node = nodeManager.value.getNode(nodeId)
    if (!node) return

    if (!multiSelect) {
      canvasStore.canvas.deselectAll()
      canvasStore.canvas.select(node)
      canvasStore.updateSelectedItems()
      if (!node.flags?.pinned) {
        bringNodeToFront(nodeId)
      }
      return
    }

    if (node.selected) {
      canvasStore.canvas.deselect(node)
    } else {
      canvasStore.canvas.select(node)
      if (!node.flags?.pinned) {
        bringNodeToFront(nodeId)
      }
    }

    canvasStore.updateSelectedItems()
  }

  return {
    handleNodeSelect,
    handleNodeCollapse,
    handleNodeTitleUpdate,
    handleNodeRightClick,
    toggleNodeSelectionAfterPointerUp
  }
}

export const useNodeEventHandlers = createSharedComposable(
  useNodeEventHandlersIndividual
)
