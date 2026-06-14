<template>
  <div v-if="renderError" class="node-error p-2 text-sm text-red-500">
    {{ st('nodeErrors.widgets', 'Node Widgets Error') }}
  </div>
  <div
    v-else
    data-testid="node-widgets"
    :class="
      cn(
        'lg-node-widgets grid grid-cols-[min-content_minmax(80px,min-content)_minmax(125px,1fr)] gap-y-1 pr-3',
        shouldHandleNodePointerEvents
          ? 'pointer-events-auto'
          : 'pointer-events-none'
      )
    "
    :style="{
      'grid-template-rows': gridTemplateRows,
      flex: gridTemplateRows.includes('auto') ? 1 : undefined
    }"
    @pointerdown.capture="handleBringToFront"
    @pointerdown="handleWidgetPointerEvent"
    @pointermove="handleWidgetPointerEvent"
    @pointerup="handleWidgetPointerEvent"
  >
    <template v-for="widget in visibleProcessedWidgets" :key="widget.renderKey">
      <div
        data-testid="node-widget"
        class="lg-node-widget group col-span-full grid grid-cols-subgrid items-stretch"
      >
        <!-- Widget Input Slot Dot -->
        <div
          :class="
            cn(
              'z-10 flex w-3 items-stretch opacity-0 transition-opacity duration-150 group-hover:opacity-100',
              widget.slotMetadata?.linked && 'opacity-100'
            )
          "
        >
          <InputSlot
            v-if="widget.slotMetadata"
            :key="`widget-slot-${widget.name}-${widget.slotMetadata.index}`"
            :slot-data="{
              name: widget.name,
              type: widget.slotMetadata.type,
              boundingRect: [0, 0, 0, 0]
            }"
            :node-id="nodeData?.id != null ? String(nodeData.id) : ''"
            :has-error="widget.hasError"
            :index="widget.slotMetadata.index"
            :socketless="widget.simplified.spec?.socketless"
            dot-only
          />
        </div>
        <!-- Widget Component -->
        <AppInput
          :id="widget.id"
          :name="widget.name"
          :enable="canSelectInputs && !widget.simplified.options?.disabled"
        >
          <component
            :is="widget.vueComponent"
            v-model="widget.value"
            v-tooltip.left="widget.tooltipConfig"
            :widget="widget.simplified"
            :node-id="nodeData?.id != null ? String(nodeData.id) : ''"
            :node-type="nodeType"
            :class="
              cn(
                'col-span-2',
                widget.hasError && 'font-bold text-node-stroke-error'
              )
            "
            @update:model-value="(value) => handleSjsxWidgetUpdate(value, widget)"
            @contextmenu="widget.handleContextMenu"
          />
        </AppInput>
      </div>
    </template>

    <SjsxParamSearch
      v-if="isSjsx"
      :node-type="nodeType"
      :active-params="activeParams"
      @add="handleAddParam"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onErrorCaptured, onMounted, ref } from 'vue'

import type { VueNodeData } from '@/composables/graph/useGraphNodeManager'
import { useSjsxNodeParams } from '@/composables/sjsx/useSjsxNodeParams'
import { useErrorHandling } from '@/composables/useErrorHandling'
import { st } from '@/i18n'
import { sjsxParamsRevision, getSjsxLGraphNode, syncSjsxWidgetValuesToProperties } from '@/utils/sjsxParamUtil'
import { useCanvasInteractions } from '@/renderer/core/canvas/useCanvasInteractions'
import AppInput from '@/renderer/extensions/linearMode/AppInput.vue'
import { useNodeZIndex } from '@/renderer/extensions/vueNodes/composables/useNodeZIndex'
import { useProcessedWidgets } from '@/renderer/extensions/vueNodes/composables/useProcessedWidgets'
import { useVueElementTracking } from '@/renderer/extensions/vueNodes/composables/useVueNodeResizeTracking'
import { cn } from '@comfyorg/tailwind-utils'

import InputSlot from './InputSlot.vue'
import SjsxParamSearch from './SjsxParamSearch.vue'

interface NodeWidgetsProps {
  nodeData?: VueNodeData
}

const { nodeData } = defineProps<NodeWidgetsProps>()

const { shouldHandleNodePointerEvents, forwardEventToCanvas } =
  useCanvasInteractions()
const { bringNodeToFront } = useNodeZIndex()

function handleWidgetPointerEvent(event: PointerEvent) {
  if (shouldHandleNodePointerEvents.value) return
  event.stopPropagation()
  forwardEventToCanvas(event)
}

function handleBringToFront() {
  if (nodeData?.id != null) {
    bringNodeToFront(String(nodeData.id))
  }
}

const renderError = ref<string | null>(null)
const { toastErrorHandler } = useErrorHandling()

onErrorCaptured((error) => {
  renderError.value = error.message
  toastErrorHandler(error)
  return false
})

const { isSjsx, activeParams, refreshNonce, ensureInitialized, addParam } =
  useSjsxNodeParams(() => nodeData)

const {
  canSelectInputs,
  gridTemplateRows: widgetGridRows,
  nodeType,
  processedWidgets: baseProcessedWidgets,
  showAdvanced
} = useProcessedWidgets(() => nodeData)

const processedWidgets = computed(() => {
  refreshNonce.value
  sjsxParamsRevision.value
  return baseProcessedWidgets.value
})

const visibleProcessedWidgets = computed(() => {
  sjsxParamsRevision.value
  refreshNonce.value
  if (!isSjsx.value) {
    return processedWidgets.value.filter(
      (widget) =>
        !widget.hidden && (!widget.advanced || showAdvanced.value)
    )
  }
  const active = new Set(activeParams.value)
  return processedWidgets.value.filter((widget) => active.has(widget.name))
})

const gridTemplateRows = computed(() => {
  const rows = isSjsx.value
    ? visibleProcessedWidgets.value
        .map((w) => (w.hasLayoutSize ? 'auto' : 'min-content'))
        .join(' ')
    : widgetGridRows.value
  if (!isSjsx.value) return rows
  return rows ? `${rows} min-content` : 'min-content'
})

onMounted(() => {
  if (isSjsx.value) ensureInitialized()
})

function handleAddParam(name: string) {
  addParam(name)
}

function handleSjsxWidgetUpdate(
  value: unknown,
  widget: { name: string; updateHandler: (value: unknown) => void }
) {
  widget.updateHandler(value)
  if (!isSjsx.value) return
  const node = getSjsxLGraphNode(nodeData?.id)
  if (!node) return
  syncSjsxWidgetValuesToProperties(node)
  node.setDirtyCanvas(true, true)
  window.dispatchEvent(
    new CustomEvent('sjsx:widget-values-changed', {
      detail: { nodeId: node.id }
    })
  )
}

if (nodeData?.id != null) {
  useVueElementTracking(String(nodeData.id), 'widgets-grid')
}
</script>
