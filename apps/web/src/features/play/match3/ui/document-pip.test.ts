import { afterEach, describe, expect, it, vi } from "vitest";

import { createDocumentPipController } from "./document-pip";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("document picture-in-picture controller", () => {
  it("stays unsupported when the browser API is absent", async () => {
    vi.stubGlobal("window", {});
    const onSurfaceChange = vi.fn();
    const controller = createDocumentPipController(onSurfaceChange);

    expect(controller.supported).toBe(false);
    await expect(controller.open({} as HTMLElement, {} as HTMLElement)).resolves.toBe(false);
    expect(controller.opened).toBe(false);
    expect(onSurfaceChange).not.toHaveBeenCalled();
  });

  it("stays unsupported when requestWindow is not callable", async () => {
    vi.stubGlobal("window", {
      documentPictureInPicture: { requestWindow: true },
    });
    const controller = createDocumentPipController(vi.fn());

    expect(controller.supported).toBe(false);
    await expect(
      controller.open({} as HTMLElement, {} as HTMLElement),
    ).resolves.toBe(false);
  });

  it("settles a non-resolving browser request as a safe failure", async () => {
    vi.useFakeTimers();
    const requestWindow = vi.fn(() => new Promise<Window>(() => undefined));
    vi.stubGlobal("window", { documentPictureInPicture: { requestWindow } });
    vi.stubGlobal("document", { querySelectorAll: vi.fn(() => []) });
    const onSurfaceChange = vi.fn();
    const controller = createDocumentPipController(onSurfaceChange);

    const opened = controller.open({} as HTMLElement, {} as HTMLElement);
    await vi.advanceTimersByTimeAsync(1_500);

    await expect(opened).resolves.toBe(false);
    expect(controller.opened).toBe(false);
    expect(onSurfaceChange).not.toHaveBeenCalled();
  });

  it("leaves the mounted surface in place when the request is rejected", async () => {
    const requestWindow = vi.fn().mockRejectedValue(new Error("not allowed"));
    vi.stubGlobal("window", { documentPictureInPicture: { requestWindow } });
    vi.stubGlobal("document", { querySelectorAll: vi.fn(() => []) });
    const surface = {} as HTMLElement;
    const anchor = { append: vi.fn() } as unknown as HTMLElement;
    const onSurfaceChange = vi.fn();
    const controller = createDocumentPipController(onSurfaceChange);

    await expect(controller.open(surface, anchor)).resolves.toBe(false);
    expect(controller.opened).toBe(false);
    expect(anchor.append).not.toHaveBeenCalled();
    expect(onSurfaceChange).not.toHaveBeenCalled();
  });

  it("moves one surface into the small window and restores that exact node", async () => {
    const sourceStyle = { cloneNode: vi.fn(() => ({ kind: "style-clone" })) };
    const appendStyle = vi.fn();
    const appendToPip = vi.fn();
    const listeners: { pagehide: (() => void) | null } = { pagehide: null };
    const pipWindow = {
      document: {
        documentElement: { lang: "" },
        head: { append: appendStyle },
        body: { className: "", append: appendToPip },
      },
      addEventListener: vi.fn((type: string, listener: () => void) => {
        if (type === "pagehide") listeners.pagehide = listener;
      }),
      close: vi.fn(),
    };
    const requestWindow = vi.fn().mockResolvedValue(pipWindow);
    vi.stubGlobal("window", { documentPictureInPicture: { requestWindow } });
    vi.stubGlobal("document", {
      documentElement: { lang: "zh-CN" },
      querySelectorAll: vi.fn(() => [sourceStyle]),
    });
    const surface = { kind: "canonical-surface" } as unknown as HTMLElement;
    const anchor = { append: vi.fn() } as unknown as HTMLElement;
    const onSurfaceChange = vi.fn();
    const controller = createDocumentPipController(onSurfaceChange);

    await expect(controller.open(surface, anchor)).resolves.toBe(true);
    expect(controller.opened).toBe(true);
    expect(appendToPip).toHaveBeenCalledWith(surface);
    expect(pipWindow.document.documentElement.lang).toBe("zh-CN");
    expect(pipWindow.document.body.className).toBe("document-pip-body");
    expect(onSurfaceChange).toHaveBeenLastCalledWith(pipWindow);

    if (!listeners.pagehide) throw new Error("pagehide listener was not registered");
    listeners.pagehide();
    expect(anchor.append).toHaveBeenCalledWith(surface);
    expect(controller.opened).toBe(false);
    expect(onSurfaceChange).toHaveBeenLastCalledWith(null);
  });
});
