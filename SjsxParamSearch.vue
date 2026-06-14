<template>
  <div
    class="sjsx-param-search pointer-events-auto relative col-span-full px-3 pt-1 pb-1"
    data-testid="sjsx-param-search"
  >
    <input
      ref="inputRef"
      v-model="query"
      type="text"
      class="w-full rounded-md border border-component-node-border bg-component-node-background px-2 py-1 text-sm text-foreground outline-none focus:border-primary"
      :placeholder="placeholder"
      autocomplete="off"
      spellcheck="false"
      @keydown="handleKeydown"
      @focus="openSuggestions = true"
      @blur="handleBlur"
    />
    <ul
      v-if="openSuggestions && filteredSuggestions.length > 0"
      class="absolute inset-x-3 top-full z-20 mt-1 max-h-40 overflow-y-auto rounded-md border border-component-node-border bg-component-node-header-surface shadow-lg"
      data-testid="sjsx-param-suggestions"
    >
      <li
        v-for="(item, index) in filteredSuggestions"
        :key="item.name"
        :class="
          cn(
            'cursor-pointer px-2 py-1 text-sm',
            index === highlightedIndex
              ? 'bg-primary text-primary-foreground'
              : 'text-foreground hover:bg-muted'
          )
        "
        @mousedown.prevent="selectSuggestion(item.name)"
      >
        <span class="font-medium">{{ item.name }}</span>
        <span
          v-if="item.kind !== 'attr'"
          class="ml-2 text-xs opacity-70"
        >{{ item.kind }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { useSjsxParamCatalog } from '@/composables/sjsx/useSjsxParamCatalog'
import { cn } from '@comfyorg/tailwind-utils'

const props = defineProps<{
  nodeType: string
  activeParams: string[]
  placeholder?: string
}>()

const emit = defineEmits<{
  add: [name: string]
}>()

const placeholder = computed(
  () => props.placeholder ?? '파라미터 검색…'
)

const inputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const openSuggestions = ref(false)
const highlightedIndex = ref(0)
const hasNavigatedSuggestions = ref(false)

const { catalog, ensureLoaded } = useSjsxParamCatalog(() => props.nodeType)

onMounted(() => {
  void ensureLoaded()
})

const activeSet = computed(() => new Set(props.activeParams))

const filteredSuggestions = computed(() => {
  const q = query.value.trim().toLowerCase()
  const items = catalog.value.filter((item) => !activeSet.value.has(item.name))
  if (!q) return items.slice(0, 12)
  return items
    .filter((item) => item.name.toLowerCase().includes(q))
    .slice(0, 12)
})

watch(query, () => {
  highlightedIndex.value = 0
  hasNavigatedSuggestions.value = false
})

function selectSuggestion(name: string) {
  emit('add', name)
  query.value = ''
  openSuggestions.value = false
  highlightedIndex.value = 0
}

function commitQuery() {
  const typed = query.value.trim()
  if (!typed) return

  const suggestions = filteredSuggestions.value
  if (
    openSuggestions.value &&
    suggestions.length > 0 &&
    hasNavigatedSuggestions.value
  ) {
    selectSuggestion(suggestions[highlightedIndex.value]?.name ?? typed)
    return
  }

  emit('add', typed)
  query.value = ''
  openSuggestions.value = false
  highlightedIndex.value = 0
  hasNavigatedSuggestions.value = false
}

function handleKeydown(event: KeyboardEvent) {
  const suggestions = filteredSuggestions.value

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    openSuggestions.value = true
    hasNavigatedSuggestions.value = true
    if (suggestions.length === 0) return
    highlightedIndex.value = (highlightedIndex.value + 1) % suggestions.length
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    openSuggestions.value = true
    hasNavigatedSuggestions.value = true
    if (suggestions.length === 0) return
    highlightedIndex.value =
      (highlightedIndex.value - 1 + suggestions.length) % suggestions.length
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    openSuggestions.value = false
    return
  }

  if (event.key === 'Enter') {
    event.preventDefault()
    event.stopPropagation()
    commitQuery()
  }
}

function handleBlur() {
  window.setTimeout(() => {
    openSuggestions.value = false
  }, 120)
}
</script>
