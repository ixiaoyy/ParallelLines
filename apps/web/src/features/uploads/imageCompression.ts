const POST_ATTACHMENT_MAX_IMAGE_EDGE = 2400;
const POST_ATTACHMENT_WEBP_QUALITY = 0.9;
const POST_ATTACHMENT_MIN_COMPRESS_BYTES = 512 * 1024;
const COMPRESSIBLE_POST_IMAGE_TYPES = new Set(["image/jpeg", "image/png"]);

/**
 * Downscales large post attachment images before upload to reduce comic/page transfer size.
 * Key parameter: `file` is the browser-selected attachment. Return value: the original file or a smaller WebP file.
 * Side effect: reads the image into an off-DOM canvas; no network or DOM insertion is performed.
 */
export async function preparePostAttachmentFile(file: File): Promise<File> {
  if (!COMPRESSIBLE_POST_IMAGE_TYPES.has(file.type)) {
    return file;
  }

  try {
    const image = await loadImageElement(file);
    const { width, height } = fitImageWithinMaxEdge(image.naturalWidth, image.naturalHeight);
    const shouldResize = width !== image.naturalWidth || height !== image.naturalHeight;
    if (!shouldResize && file.size < POST_ATTACHMENT_MIN_COMPRESS_BYTES) {
      return file;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return file;
    }

    context.drawImage(image, 0, 0, width, height);
    const compressed = await canvasToBlob(
      canvas,
      "image/webp",
      POST_ATTACHMENT_WEBP_QUALITY,
    );
    if (!compressed || compressed.type !== "image/webp" || compressed.size >= file.size) {
      return file;
    }

    return new File([compressed], replaceFileExtension(file.name, "webp"), {
      type: "image/webp",
      lastModified: file.lastModified,
    });
  } catch {
    return file;
  }
}

/**
 * Loads a browser `File` as an image so dimensions can be measured before upload.
 * Key parameter: `file` is a local image file. Return value: a decoded `HTMLImageElement`.
 * Side effect: creates and revokes one object URL.
 */
function loadImageElement(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(objectUrl);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("image_load_failed"));
    };
    image.src = objectUrl;
  });
}

/**
 * Calculates display-safe image dimensions while preserving the original aspect ratio.
 * Key parameters: `width` and `height` are source pixels. Return value: fitted integer dimensions.
 * Side effect: none.
 */
function fitImageWithinMaxEdge(width: number, height: number) {
  const maxEdge = Math.max(width, height);
  if (maxEdge <= POST_ATTACHMENT_MAX_IMAGE_EDGE) {
    return { width, height };
  }

  const ratio = POST_ATTACHMENT_MAX_IMAGE_EDGE / maxEdge;
  return {
    width: Math.max(1, Math.round(width * ratio)),
    height: Math.max(1, Math.round(height * ratio)),
  };
}

/**
 * Converts a canvas to a compressed blob using the browser encoder.
 * Key parameters: `canvas`, target `type`, and encoder `quality`. Return value: encoded blob or null.
 * Side effect: performs CPU work in the browser encoder but does not mutate application state.
 */
function canvasToBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number,
): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality);
  });
}

/**
 * Replaces a filename extension after client-side transcoding.
 * Key parameters: `filename` is the original display name and `extension` omits the dot. Return value: safe new name.
 * Side effect: none.
 */
function replaceFileExtension(filename: string, extension: string) {
  const cleanExtension = extension.replace(/^\.+/, "") || "webp";
  const base = filename.replace(/\.[^.]*$/, "").trim() || "upload";
  return `${base}.${cleanExtension}`;
}
