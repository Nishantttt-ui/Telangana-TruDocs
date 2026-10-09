import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 100)
}

export function createBlobUrl(blob) {
  return URL.createObjectURL(blob)
}

// `isCancelled` lets the caller abandon a stale render (effect cleanup / newer blob).
// Without it, two overlapping renders into one container both append their pages.
export async function renderPdfToCanvas(blob, container, isCancelled = () => false) {
  try {
    const arrayBuffer = await blob.arrayBuffer()
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
    if (isCancelled()) return
    container.innerHTML = ''

    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
      const page = await pdf.getPage(pageNum)
      if (isCancelled()) return
      const viewport = page.getViewport({ scale: window.devicePixelRatio || 1.5 })
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = '100%'
      canvas.style.display = 'block'
      canvas.style.borderRadius = '4px'
      container.appendChild(canvas)
      await page.render({ canvasContext: ctx, viewport }).promise
    }
  } catch (err) {
    container.innerHTML = '<p style="padding:16px;color:#f87171">Could not render PDF preview.</p>'
  }
}
