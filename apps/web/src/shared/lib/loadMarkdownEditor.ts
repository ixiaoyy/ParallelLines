import { runWhenBrowserIdle } from "@/shared/lib/loadWhenIdle";

type MarkdownEditorComponent = (typeof import("md-editor-v3"))["MdEditor"];

let markdownEditorPromise: Promise<MarkdownEditorComponent> | null = null;

/**
 * Loads md-editor-v3 and its vendor stylesheet as one cached async dependency.
 * Key parameters: none. Return value is the MdEditor component constructor. Side effect: downloads the editor JS/CSS chunk once.
 */
export function loadMarkdownEditor(): Promise<MarkdownEditorComponent> {
  if (!markdownEditorPromise) {
    markdownEditorPromise = Promise.all([
      import("md-editor-v3"),
      import("md-editor-v3/lib/style.css"),
    ]).then(([module]) => module.MdEditor);
  }

  return markdownEditorPromise;
}

/**
 * Waits for browser idle time before loading the shared markdown editor chunk.
 * Key parameter `timeoutMs` bounds the idle wait. Return value is the MdEditor component constructor. Side effect: schedules idle work and may download the editor chunk.
 */
export function loadMarkdownEditorWhenIdle(timeoutMs = 1200): Promise<MarkdownEditorComponent> {
  return runWhenBrowserIdle(timeoutMs).then(loadMarkdownEditor);
}
