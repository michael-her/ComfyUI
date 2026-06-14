import { useSettingStore } from '@/platform/settings/settingStore'

const BOOTSTRAP_FLAG = 'sementic.sjsx.vueNodesBootstrapped'

/** SJAX NodeHeader requires Modern Node Design (Vue nodes / Nodes 2.0). */
export async function bootstrapSementicVueNodes(): Promise<void> {
  if (typeof localStorage === 'undefined') return

  const settingStore = useSettingStore()

  if (Object.keys(settingStore.settingsById).length === 0) {
    await settingStore.load()
  }

  if (settingStore.get('Comfy.VueNodes.Enabled')) {
    localStorage.setItem(BOOTSTRAP_FLAG, '1')
    return
  }

  await settingStore.set('Comfy.VueNodes.Enabled', true)
  localStorage.setItem(BOOTSTRAP_FLAG, '1')
}
