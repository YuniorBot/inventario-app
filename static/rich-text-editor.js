;(() => {
  const toggleCommands = new Set([
    "bold",
    "italic",
    "underline",
    "insertUnorderedList",
    "insertOrderedList",
  ])

  const clipboardTagMap = new Map([
    ["b", "strong"],
    ["strong", "strong"],
    ["i", "em"],
    ["em", "em"],
    ["u", "u"],
    ["p", "p"],
    ["br", "br"],
    ["ul", "ul"],
    ["ol", "ol"],
    ["li", "li"],
  ])
  const clipboardBlockTags = new Set([
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "main",
    "section",
  ])
  const discardedClipboardTags = new Set([
    "audio",
    "button",
    "canvas",
    "embed",
    "form",
    "iframe",
    "img",
    "input",
    "link",
    "math",
    "meta",
    "noscript",
    "object",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
    "video",
  ])

  function hasBoldStyle(element) {
    const weight = element.style.fontWeight.toLowerCase()
    const numericWeight = Number.parseInt(weight, 10)
    return weight === "bold" || weight === "bolder" || numericWeight >= 600
  }

  function hasItalicStyle(element) {
    const style = element.style.fontStyle.toLowerCase()
    return style === "italic" || style === "oblique"
  }

  function hasUnderlineStyle(element) {
    return `${element.style.textDecoration} ${element.style.textDecorationLine}`
      .toLowerCase()
      .includes("underline")
  }

  function sanitizeClipboardChildren(source) {
    const fragment = document.createDocumentFragment()
    source.childNodes.forEach(child => {
      const sanitized = sanitizeClipboardNode(child)
      if (sanitized) fragment.appendChild(sanitized)
    })
    return fragment
  }

  function sanitizeClipboardNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return document.createTextNode(node.nodeValue || "")
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return null

    const source = node
    const sourceTag = source.tagName.toLowerCase()
    if (discardedClipboardTags.has(sourceTag)) return null

    let content = sanitizeClipboardChildren(source)
    const outputTag = clipboardTagMap.get(sourceTag)

    const wrappers = []
    if (outputTag !== "strong" && hasBoldStyle(source)) wrappers.push("strong")
    if (outputTag !== "em" && hasItalicStyle(source)) wrappers.push("em")
    if (outputTag !== "u" && hasUnderlineStyle(source)) wrappers.push("u")

    wrappers.reverse().forEach(tag => {
      const wrapper = document.createElement(tag)
      wrapper.appendChild(content)
      content = wrapper
    })

    if (!outputTag && !clipboardBlockTags.has(sourceTag)) return content

    const output = document.createElement(outputTag || "p")
    if (output.tagName !== "BR") output.appendChild(content)
    return output
  }

  function plainTextFragment(value) {
    const fragment = document.createDocumentFragment()
    value.replace(/\r\n?/g, "\n").split("\n").forEach((line, index) => {
      if (index) fragment.appendChild(document.createElement("br"))
      fragment.appendChild(document.createTextNode(line))
    })
    return fragment
  }

  function clipboardFragment(clipboardData) {
    const html = clipboardData.getData("text/html")
    if (html) {
      const parsed = new DOMParser().parseFromString(html, "text/html")
      const fragment = sanitizeClipboardChildren(parsed.body)
      if (fragment.childNodes.length) return fragment
    }
    return plainTextFragment(clipboardData.getData("text/plain"))
  }

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
    const initialValue = textarea.value
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

    function insertFragment(fragment) {
      const selection = window.getSelection()
      if (!selection || !selection.rangeCount || !selectionIsInsideEditor()) {
        editor.focus()
        editor.appendChild(fragment)
        return
      }

      const range = selection.getRangeAt(0)
      const lastNode = fragment.lastChild
      range.deleteContents()
      range.insertNode(fragment)
      if (lastNode) {
        range.setStartAfter(lastNode)
        range.collapse(true)
        selection.removeAllRanges()
        selection.addRange(range)
      }
    }

    function resetEditor() {
      textarea.value = initialValue
      editor.innerHTML = initialValue
      savedRange = null
      tools.forEach(tool => {
        tool.classList.remove("is-active")
        if (toggleCommands.has(tool.dataset.command)) {
          tool.setAttribute("aria-pressed", "false")
        }
      })
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
      if (!event.clipboardData) return
      event.preventDefault()
      insertFragment(clipboardFragment(event.clipboardData))
      syncInput()
      rememberSelection()
      refreshToolbar()
    })
    field.addEventListener("rich-text:reset", resetEditor)
    field.closest("form")?.addEventListener("submit", syncInput)
    document.addEventListener("selectionchange", refreshToolbar)
  })

  const panels = Array.from(document.querySelectorAll("[data-editor-panel]"))

  function getToggle(panel) {
    return document.querySelector(`[data-editor-toggle="${panel.id}"]`)
  }

  function resetPanel(panel) {
    panel.querySelectorAll("[data-rich-text]").forEach(field => {
      field.dispatchEvent(new CustomEvent("rich-text:reset"))
    })
  }

  function closePanel(panel, restoreContent = true) {
    panel.hidden = true
    const toggle = getToggle(panel)
    if (toggle) toggle.setAttribute("aria-expanded", "false")
    if (restoreContent) resetPanel(panel)
  }

  function openPanel(panel) {
    panels.forEach(otherPanel => {
      if (otherPanel !== panel) closePanel(otherPanel)
    })
    panel.hidden = false
    const toggle = getToggle(panel)
    if (toggle) toggle.setAttribute("aria-expanded", "true")
    window.requestAnimationFrame(() => {
      const editor = panel.querySelector(".rich-text-editor")
      const textarea = panel.querySelector("textarea:not([hidden])")
      ;(editor || textarea)?.focus()
    })
  }

  document.querySelectorAll("[data-editor-toggle]").forEach(toggle => {
    const panel = document.getElementById(toggle.dataset.editorToggle)
    if (!panel) return
    toggle.hidden = false
    toggle.addEventListener("click", () => {
      if (panel.hidden) openPanel(panel)
      else closePanel(panel)
    })
  })

  document.querySelectorAll("[data-editor-cancel]").forEach(cancel => {
    const panel = document.getElementById(cancel.dataset.editorCancel)
    if (!panel) return
    cancel.hidden = false
    cancel.addEventListener("click", () => {
      closePanel(panel)
      getToggle(panel)?.focus()
    })
  })

  panels.forEach(panel => closePanel(panel, false))
})()
