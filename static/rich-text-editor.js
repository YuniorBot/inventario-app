;(() => {
  const toggleCommands = new Set([
    "bold",
    "italic",
    "underline",
    "insertUnorderedList",
    "insertOrderedList",
  ])

  function normalizeHtml(editor) {
    const clone = editor.cloneNode(true)
    clone.querySelectorAll("div").forEach(block => {
      const paragraph = document.createElement("p")
      while (block.firstChild) paragraph.appendChild(block.firstChild)
      block.replaceWith(paragraph)
    })
    return clone.innerHTML
  }

  document.querySelectorAll("[data-rich-text]").forEach(field => {
    const textarea = field.querySelector(".rich-text-input")
    const editor = field.querySelector(".rich-text-editor")
    const toolbar = field.querySelector(".rich-text-toolbar")
    const tools = Array.from(field.querySelectorAll("[data-command]"))
    let savedRange = null

    if (!textarea || !editor || !toolbar) return

    editor.innerHTML = textarea.value
    textarea.hidden = true
    toolbar.hidden = false
    editor.hidden = false

    try {
      document.execCommand("defaultParagraphSeparator", false, "p")
    } catch (_error) {
      // The editor still works in browsers that do not expose this preference.
    }

    function selectionIsInsideEditor() {
      const selection = window.getSelection()
      return Boolean(
        selection &&
        selection.rangeCount &&
        editor.contains(selection.getRangeAt(0).commonAncestorContainer)
      )
    }

    function rememberSelection() {
      if (!selectionIsInsideEditor()) return
      savedRange = window.getSelection().getRangeAt(0).cloneRange()
    }

    function restoreSelection() {
      editor.focus()
      if (!savedRange) return
      const selection = window.getSelection()
      selection.removeAllRanges()
      selection.addRange(savedRange)
    }

    function syncInput() {
      textarea.value = normalizeHtml(editor)
    }

    function refreshToolbar() {
      if (!selectionIsInsideEditor()) return
      tools.forEach(tool => {
        const command = tool.dataset.command
        if (!toggleCommands.has(command)) return
        const active = document.queryCommandState(command)
        tool.classList.toggle("is-active", active)
        tool.setAttribute("aria-pressed", String(active))
      })
    }

    tools.forEach(tool => {
      tool.addEventListener("pointerdown", event => event.preventDefault())
      tool.addEventListener("click", () => {
        restoreSelection()
        document.execCommand(tool.dataset.command, false)
        rememberSelection()
        syncInput()
        refreshToolbar()
      })
    })

    editor.addEventListener("input", () => {
      syncInput()
      rememberSelection()
      refreshToolbar()
    })
    editor.addEventListener("keyup", rememberSelection)
    editor.addEventListener("mouseup", rememberSelection)
    editor.addEventListener("focus", rememberSelection)
    editor.addEventListener("paste", event => {
      event.preventDefault()
      document.execCommand("insertText", false, event.clipboardData.getData("text/plain"))
    })
    field.closest("form")?.addEventListener("submit", syncInput)
    document.addEventListener("selectionchange", refreshToolbar)
  })
})()
