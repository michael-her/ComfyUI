import { computed, ref, toValue, type MaybeRefOrGetter } from 'vue'

import type { VueNodeData } from '@/composables/graph/useGraphNodeManager'

import {
  getSjsxActiveParams,
  getSjsxLGraphNode,
  initSjsxNodeParams,
  showSjsxParam,
  sjsxParamsRevision,
  SJSX_PARAMS_VERSION_KEY
} from '@/utils/sjsxParamUtil'
import { isSjsxNodeType } from '@/utils/sjsxNodeUtil'

export function useSjsxNodeParams(
  nodeData: MaybeRefOrGetter<VueNodeData | undefined>
) {
  const isSjsx = computed(() => isSjsxNodeType(toValue(nodeData)?.type))

  const paramsVersion = computed(() => {
    const node = getSjsxLGraphNode(toValue(nodeData)?.id)
    return Number(node?.properties?.[SJSX_PARAMS_VERSION_KEY] ?? 0)
  })

  const refreshNonce = ref(0)

  const activeParams = computed(() => {
    refreshNonce.value
    sjsxParamsRevision.value
    paramsVersion.value
    const node = getSjsxLGraphNode(toValue(nodeData)?.id)
    return node ? getSjsxActiveParams(node) : []
  })

  function ensureInitialized() {
    const node = getSjsxLGraphNode(toValue(nodeData)?.id)
    if (node) initSjsxNodeParams(node)
  }

  function addParam(name: string): boolean {
    const node = getSjsxLGraphNode(toValue(nodeData)?.id)
    if (!node) return false
    const added = showSjsxParam(node, name)
    if (added) refreshNonce.value++
    return added
  }

  return {
    isSjsx,
    activeParams,
    paramsVersion,
    refreshNonce,
    ensureInitialized,
    addParam
  }
}
