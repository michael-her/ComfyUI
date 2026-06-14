/**
 * SEMENTIC: expose legacy script shims in Vite dev so custom_nodes extensions
 * (e.g. sjsx.js) can use window.comfyAPI without importing app.ts.
 */
import { app } from '@/scripts/app'
import { blankGraph } from '@/scripts/defaultGraph'

declare global {
  interface Window {
    comfyAPI?: Record<string, Record<string, unknown>>
  }
}

if (import.meta.env.DEV) {
  window.comfyAPI = window.comfyAPI ?? {}
  window.comfyAPI.app = { ...(window.comfyAPI.app ?? {}), app }
  window.comfyAPI.defaultGraph = {
    ...(window.comfyAPI.defaultGraph ?? {}),
    blankGraph
  }
}
