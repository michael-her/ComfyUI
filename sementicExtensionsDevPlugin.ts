import fs from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

/**
 * Serve ComfyUI custom_nodes JS extensions from the workspace in Vite dev.
 * Avoids 403 when Vite blocks proxied /extensions/*.js?import as outside root.
 */
export function sementicExtensionsDevPlugin(workspaceRoot: string): Plugin {
  const customNodesRoot = path.join(workspaceRoot, 'custom_nodes')

  return {
    name: 'sementic-extensions-dev',
    enforce: 'pre',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const urlPath = (req.url ?? '').split('?')[0]
        if (!urlPath.startsWith('/extensions/') || !urlPath.endsWith('.js')) {
          return next()
        }

        const rel = urlPath.slice('/extensions/'.length)
        const parts = rel.split('/')
        if (parts.length !== 2) {
          return next()
        }

        const [nodeName, fileName] = parts
        const filePath = path.join(customNodesRoot, nodeName, 'js', fileName)

        if (!fs.existsSync(filePath)) {
          return next()
        }

        res.setHeader('Content-Type', 'application/javascript; charset=utf-8')
        res.statusCode = 200
        res.end(fs.readFileSync(filePath, 'utf-8'))
      })
    }
  }
}
