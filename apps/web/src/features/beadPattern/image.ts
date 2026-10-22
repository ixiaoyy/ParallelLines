import { BEAD_MESSAGES, MAX_GRID_EDGE, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS } from "./model";
import type { CropRegion } from "./model";

export interface LoadedImage {
  image: HTMLImageElement;
  url: string;
  release: () => void;
}

/** 读取本地文件或本站示例；返回图像及释放方法，任何失败均不上传文件。 */
export async function loadBeadImage(source: File | string): Promise<LoadedImage> {
  if (source instanceof File) {
    if (!/^image\/(jpeg|png|webp)$/.test(source.type)) throw new Error(BEAD_MESSAGES.type);
    if (source.size > MAX_IMAGE_BYTES) throw new Error(BEAD_MESSAGES.size);
  }
  const localFile = source instanceof File;
  const url = localFile ? URL.createObjectURL(source) : source;
  const release = () => { if (localFile) URL.revokeObjectURL(url); };
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    if (!image.naturalWidth || !image.naturalHeight) throw new Error(BEAD_MESSAGES.read);
    if (image.naturalWidth * image.naturalHeight > MAX_IMAGE_PIXELS) throw new Error(BEAD_MESSAGES.pixels);
    return { image, url, release };
  } catch (error) {
    release();
    if (error instanceof Error && error.message === BEAD_MESSAGES.pixels) throw error;
    throw new Error(BEAD_MESSAGES.read);
  }
}

/** 由裁剪区域比例计算方格数量，长边限制在 8 至 128 格，不拉伸图像。 */
export function getGridSize(image: HTMLImageElement, crop: CropRegion, edge: number) {
  const longest = Math.min(MAX_GRID_EDGE, Math.max(8, Math.round(edge) || 48));
  const width = image.naturalWidth * crop.width;
  const height = image.naturalHeight * crop.height;
  const ratio = longest / Math.max(width, height);
  return { width: Math.max(1, Math.round(width * ratio)), height: Math.max(1, Math.round(height * ratio)) };
}

/** 将裁剪区域采样成目标网格；Canvas 保留透明通道，白色不作为背景删除。 */
export function sampleBeadImage(image: HTMLImageElement, crop: CropRegion, edge: number): ImageData {
  const { width, height } = getGridSize(image, crop, edge);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error(BEAD_MESSAGES.generate);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(image, crop.x * image.naturalWidth, crop.y * image.naturalHeight,
    crop.width * image.naturalWidth, crop.height * image.naturalHeight, 0, 0, width, height);
  return context.getImageData(0, 0, width, height);
}
