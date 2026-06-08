// Copy text to the clipboard, working on both HTTPS/localhost (secure context,
// where navigator.clipboard exists) AND plain HTTP over an IP (e.g.
// http://16.16.252.44), where navigator.clipboard is undefined.
//
// The legacy execCommand('copy') path uses a hidden textarea and works in
// insecure contexts where the modern Clipboard API is blocked.
//
// Returns true on success, false on failure (caller can toast accordingly).
export async function copyText(text) {
  // Modern API — only available in secure contexts (HTTPS or localhost)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // fall through to legacy method
    }
  }

  // Legacy fallback for HTTP / non-secure contexts
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    // Keep it out of view and avoid scroll jumps
    ta.style.position = 'fixed'
    ta.style.top = '0'
    ta.style.left = '0'
    ta.style.width = '1px'
    ta.style.height = '1px'
    ta.style.padding = '0'
    ta.style.border = 'none'
    ta.style.outline = 'none'
    ta.style.boxShadow = 'none'
    ta.style.background = 'transparent'
    ta.setAttribute('readonly', '')
    document.body.appendChild(ta)
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
