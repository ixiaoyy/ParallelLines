interface DocumentPictureInPictureWindow extends Window {
  readonly document: Document;
}
interface DocumentPictureInPictureApi {
  requestWindow(options?: { width?: number; height?: number }): Promise<DocumentPictureInPictureWindow>;
}

type WindowWithDocumentPip = Window & {
  documentPictureInPicture?: DocumentPictureInPictureApi;
};

export interface DocumentPipController {
  readonly supported: boolean;
  readonly opened: boolean;
  open(surface: HTMLElement, anchor: HTMLElement): Promise<boolean>;
  close(): void;
}

export function createDocumentPipController(
  onSurfaceChange: (surfaceWindow: Window | null) => void,
): DocumentPipController {
  const candidateApi = (window as WindowWithDocumentPip).documentPictureInPicture;
  const api = typeof candidateApi?.requestWindow === "function"
    ? candidateApi
    : null;
  let pipWindow: DocumentPictureInPictureWindow | null = null;
  let surface: HTMLElement | null = null;
  let anchor: HTMLElement | null = null;
  let opening = false;
  let requestSequence = 0;

  function copyStyles(target: Document): void {
    for (const node of document.querySelectorAll("style, link[rel='stylesheet']")) {
      target.head.append(node.cloneNode(true));
    }
  }

  function restore(): void {
    if (surface && anchor) anchor.append(surface);
    pipWindow = null;
    surface = null;
    anchor = null;
    onSurfaceChange(null);
  }

  async function open(nextSurface: HTMLElement, nextAnchor: HTMLElement): Promise<boolean> {
    if (!api || pipWindow || opening) return false;
    const sequence = ++requestSequence;
    opening = true;
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
    try {
      const timeout = new Promise<{ kind: "timed-out" }>((resolve) => {
        timeoutHandle = setTimeout(() => resolve({ kind: "timed-out" }), 1_500);
      });
      const request = api.requestWindow({ width: 430, height: 560 });
      const outcome = await Promise.race([
        request.then(
          (nextWindow) => ({ kind: "opened" as const, nextWindow }),
          () => ({ kind: "failed" as const }),
        ),
        timeout,
      ]);
      if (timeoutHandle !== null) clearTimeout(timeoutHandle);
      if (outcome.kind !== "opened") {
        if (outcome.kind === "timed-out") {
          void request.then((lateWindow) => lateWindow.close(), () => undefined);
        }
        return false;
      }
      const nextWindow = outcome.nextWindow;
      if (sequence !== requestSequence) {
        nextWindow.close();
        return false;
      }
      copyStyles(nextWindow.document);
      nextWindow.document.documentElement.lang = document.documentElement.lang;
      nextWindow.document.body.className = "document-pip-body";
      nextWindow.document.body.append(nextSurface);
      pipWindow = nextWindow;
      surface = nextSurface;
      anchor = nextAnchor;
      nextWindow.addEventListener("pagehide", restore, { once: true });
      onSurfaceChange(nextWindow);
      return true;
    } catch {
      return false;
    } finally {
      if (timeoutHandle !== null) clearTimeout(timeoutHandle);
      opening = false;
    }
  }

  function close(): void {
    requestSequence += 1;
    pipWindow?.close();
  }

  return {
    supported: Boolean(api),
    get opened() {
      return pipWindow !== null;
    },
    open,
    close,
  };
}
