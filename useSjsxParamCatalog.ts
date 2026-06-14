import { computed, ref } from 'vue'

import type { SjsxParamSuggestion } from '@/utils/sjsxParamUtil'
import { getSjsxTagName } from '@/utils/sjsxNodeUtil'

interface VocabularyComponent {
  tag: string
  attrs?: Record<string, { description?: string }>
  events?: Record<string, { description?: string }>
  content_slot?: boolean
}

interface VocabularyResponse {
  components: VocabularyComponent[]
}

let vocabularyPromise: Promise<VocabularyResponse> | null = null

async function fetchVocabulary(): Promise<VocabularyResponse> {
  if (!vocabularyPromise) {
    vocabularyPromise = fetch('/api/sjsx/vocabulary')
      .then((res) => {
        if (!res.ok) throw new Error(`vocabulary ${res.status}`)
        return res.json()
      })
      .catch((err) => {
        vocabularyPromise = null
        throw err
      })
  }
  return vocabularyPromise
}

export function useSjsxParamCatalog(nodeType: () => string | undefined) {
  const loaded = ref(false)
  const loadError = ref<string | null>(null)
  const byTag = ref(new Map<string, SjsxParamSuggestion[]>())

  async function ensureLoaded() {
    if (loaded.value) return
    try {
      const data = await fetchVocabulary()
      const map = new Map<string, SjsxParamSuggestion[]>()
      for (const component of data.components ?? []) {
        const suggestions: SjsxParamSuggestion[] = []
        for (const [name, spec] of Object.entries(component.attrs ?? {})) {
          suggestions.push({
            name,
            kind: 'attr',
            description: spec.description
          })
        }
        for (const [name, spec] of Object.entries(component.events ?? {})) {
          suggestions.push({
            name,
            kind: 'event',
            description: spec.description
          })
        }
        if (component.content_slot) {
          suggestions.push({ name: 'content', kind: 'content' })
        }
        map.set(component.tag, suggestions)
      }
      byTag.value = map
      loaded.value = true
      loadError.value = null
    } catch (error) {
      loadError.value = error instanceof Error ? error.message : String(error)
    }
  }

  const tag = computed(() => getSjsxTagName(nodeType()))

  const catalog = computed(() => byTag.value.get(tag.value) ?? [])

  return {
    loaded,
    loadError,
    catalog,
    ensureLoaded
  }
}
