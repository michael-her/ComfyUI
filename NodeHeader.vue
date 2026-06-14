<template>
  <div v-if="renderError" class="node-error p-4 text-red-500">
    {{ st('nodeErrors.header', 'Node Header Error') }}
  </div>
  <div
    v-else
    :class="
      cn(
        'lg-node-header w-full min-w-0 py-2 pr-3 pl-2 text-sm',
        'text-node-component-header',
        headerShapeClass
      )
    "
    :data-testid="`node-header-${nodeData?.id || ''}`"
    @dblclick="!isSjsxNode && handleDoubleClick()"
  >
    <div class="flex min-w-0 items-center justify-between gap-2.5">
      <div class="relative mr-auto flex min-w-0 items-center gap-2.5">
        <div class="flex shrink-0 items-center px-0.5">
          <Button
            size="icon-sm"
            variant="textonly"
            class="hover:bg-transparent"
            data-testid="node-collapse-button"
            @click.stop="handleCollapse"
            @dblclick.stop
          >
            <i
              :class="
                cn(
                  'icon-[lucide--chevron-down] size-5 transition-transform',
                  collapsed && '-rotate-90'
                )
              "
              class="text-node-component-header-icon"
            />
          </Button>
        </div>

        <div
          v-tooltip.top="tooltipConfig"
          class="flex min-w-0 flex-1 items-center gap-2"
          data-testid="node-title"
        >
          <div
            v-if="isSjsxNode"
            class="flex min-w-0 flex-nowrap items-center gap-1.5"
            data-sjsx-node="true"
            @click.stop="handleSjsxTitleClick"
          >
            <template v-if="isEditing">
              <EditableText
                class="min-w-0 max-w-[10rem] flex-1"
                :model-value="instanceName"
                :is-editing="true"
                :input-attrs="{
                  'data-testid': 'node-title-input',
                  placeholder: st(
                    'sideToolbar.nodeLibraryTab.sjsxInstanceNamePlaceholder',
                    'Instance name'
                  )
                }"
                @edit="handleSjsxInstanceNameEdit"
                @cancel="handleTitleCancel"
              />
            </template>
            <span
              v-else-if="instanceName"
              class="min-w-0 max-w-[10rem] shrink truncate font-medium"
              data-testid="sjsx-instance-name"
            >
              {{ instanceName }}
            </span>
            <span
              class="inline-flex shrink-0 items-center rounded-sm border border-white/30 bg-black/55 px-1.5 py-0.5 text-[11px] leading-none font-medium text-white"
              data-testid="sjsx-tag-badge"
            >
              {{ tagName }}
            </span>
          </div>

          <div v-else class="min-w-0 flex-1 truncate">
            <EditableText
              :model-value="displayTitle"
              :is-editing="isEditing"
              :input-attrs="{ 'data-testid': 'node-title-input' }"
              @edit="handleTitleEdit"
              @cancel="handleTitleCancel"
            />
          </div>
        </div>
      </div>

      <CreditBadge
        v-for="badge in priceBadges ?? []"
        :key="badge.required"
        :text="badge.required"
        :rest="badge.rest"
      />
      <NodeBadge v-if="statusBadge" v-bind="statusBadge" />
      <i
        v-if="isPinned"
        class="icon-[comfy--pin] size-5"
        data-testid="node-pin-indicator"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onErrorCaptured, ref, watch } from 'vue'

import EditableText from '@/components/common/EditableText.vue'
import CreditBadge from '@/components/node/CreditBadge.vue'
import Button from '@/components/ui/button/Button.vue'
import type { VueNodeData } from '@/composables/graph/useGraphNodeManager'
import { useVueNodeLifecycle } from '@/composables/graph/useVueNodeLifecycle'
import { useErrorHandling } from '@/composables/useErrorHandling'
import { st } from '@/i18n'
import { LGraphEventMode, RenderShape } from '@/lib/litegraph/src/litegraph'
import NodeBadge from '@/renderer/extensions/vueNodes/components/NodeBadge.vue'
import { useNodeTooltips } from '@/renderer/extensions/vueNodes/composables/useNodeTooltips'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import {
  getSjsxTagName,
  isSjsxCategory,
  isSjsxNodeDef,
  isSjsxNodeType
} from '@/utils/sjsxNodeUtil'
import { resolveNodeDisplayName } from '@/utils/nodeTitleUtil'
import { cn } from '@comfyorg/tailwind-utils'

import type { NodeBadgeProps } from './NodeBadge.vue'

interface NodeHeaderProps {
  nodeData?: VueNodeData
  collapsed?: boolean
  priceBadges?: { required: string; rest?: string }[]
}

const props = defineProps<NodeHeaderProps>()

const emit = defineEmits<{
  collapse: []
  'update:title': [newTitle: string]
}>()

const nodeDefStore = useNodeDefStore()
const { nodeManager } = useVueNodeLifecycle()

const renderError = ref<string | null>(null)
const { toastErrorHandler } = useErrorHandling()

onErrorCaptured((error) => {
  renderError.value = error.message
  toastErrorHandler(error)
  return false
})

const isEditing = ref(false)

const lgNode = computed(() => {
  const id = props.nodeData?.id
  if (!id || !nodeManager.value) return undefined
  return nodeManager.value.getNode(id)
})

const comfyClass = computed(
  () =>
    lgNode.value?.constructor?.comfyClass ||
    lgNode.value?.type ||
    props.nodeData?.type ||
    ''
)

const category = computed(
  () => lgNode.value?.constructor?.nodeData?.category as string | undefined
)

const nodeDef = computed(() => {
  const type = comfyClass.value || props.nodeData?.type || ''
  if (!type) return undefined
  return (
    nodeDefStore.nodeDefsByName[type] ??
    Object.values(nodeDefStore.nodeDefsByName).find(
      (def) =>
        def.name === type ||
        def.display_name === type ||
        getSjsxTagName(def.name) === type
    )
  )
})

const isSjsxNode = computed(() => {
  const type = comfyClass.value || props.nodeData?.type || ''
  if (isSjsxNodeType(type)) return true
  if (isSjsxCategory(category.value)) return true
  if (isSjsxNodeDef(nodeDef.value)) return true
  return Object.values(nodeDefStore.nodeDefsByName).some(
    (def) =>
      isSjsxNodeDef(def) &&
      (def.name === type ||
        def.display_name === type ||
        def.display_name === props.nodeData?.title)
  )
})

const tagName = computed(() =>
  getSjsxTagName(comfyClass.value || props.nodeData?.type, nodeDef.value)
)

const instanceName = computed(() => {
  const title = (props.nodeData?.title ?? '').trim()
  if (!title || title === tagName.value) return ''
  return title
})

const nodeTypeForTooltips = computed(
  () => comfyClass.value || props.nodeData?.type || ''
)

const { getNodeDescription, createTooltipConfig } =
  useNodeTooltips(nodeTypeForTooltips)

const tooltipConfig = computed(() => {
  if (isEditing.value) {
    return { value: '', disabled: true }
  }
  const description = getNodeDescription.value
  return createTooltipConfig(description)
})

const resolveTitle = (info: VueNodeData | undefined) => {
  const untitledLabel = st('g.untitled', 'Untitled')
  return resolveNodeDisplayName(info ?? null, {
    emptyLabel: untitledLabel,
    untitledLabel,
    st
  })
}

const displayTitle = ref(resolveTitle(props.nodeData))

const bypassed = computed(
  (): boolean => props.nodeData?.mode === LGraphEventMode.BYPASS
)
const muted = computed((): boolean => props.nodeData?.mode === LGraphEventMode.NEVER)

const statusBadge = computed((): NodeBadgeProps | undefined =>
  muted.value
    ? { text: 'Muted', cssIcon: 'icon-[lucide--ban]' }
    : bypassed.value
      ? { text: 'Bypassed', cssIcon: 'icon-[lucide--redo-dot]' }
      : undefined
)

const isPinned = computed(() => Boolean(props.nodeData?.flags?.pinned))

const headerShapeClass = computed(() => {
  if (props.collapsed) {
    switch (props.nodeData?.shape) {
      case RenderShape.BOX:
        return 'rounded-none'
      case RenderShape.CARD:
        return 'rounded-tl-2xl rounded-br-2xl rounded-tr-none rounded-bl-none'
      default:
        return 'rounded-2xl'
    }
  }
  switch (props.nodeData?.shape) {
    case RenderShape.BOX:
      return 'rounded-t-none'
    case RenderShape.CARD:
      return 'rounded-tl-2xl rounded-tr-none'
    default:
      return 'rounded-t-2xl'
  }
})

watch(
  () =>
    [props.nodeData?.title, props.nodeData?.type, comfyClass.value] as const,
  () => {
    if (isSjsxNode.value) return
    const next = resolveTitle(props.nodeData)
    if (next !== displayTitle.value) {
      displayTitle.value = next
    }
  }
)

const handleCollapse = () => {
  emit('collapse')
}

const handleDoubleClick = () => {
  isEditing.value = true
}

const handleSjsxTitleClick = () => {
  if (!isEditing.value) {
    isEditing.value = true
  }
}

const handleSjsxInstanceNameEdit = (newTitle: string) => {
  isEditing.value = false
  const trimmedTitle = newTitle.trim()
  if (trimmedTitle !== instanceName.value) {
    emit('update:title', trimmedTitle)
  }
}

const handleTitleEdit = (newTitle: string) => {
  isEditing.value = false
  const trimmedTitle = newTitle.trim()
  if (trimmedTitle && trimmedTitle !== displayTitle.value) {
    emit('update:title', trimmedTitle)
  }
}

const handleTitleCancel = () => {
  isEditing.value = false
}
</script>
