// Client-side photo preparation (FR-1): downsize to <= 1024 px on the long
// edge and re-encode as JPEG. Re-encoding through a canvas drops all metadata,
// including EXIF/GPS. The server re-validates and re-encodes again (R8).
// Everything stays in memory; nothing is stored.

export const MAX_IMAGE_EDGE = 1024;
// Phone photos are often 3-12 MB before resizing; the resized upload is far
// below the server's 5 MB cap.
export const MAX_ORIGINAL_BYTES = 25 * 1024 * 1024;
const JPEG_QUALITY = 0.85;

export class ImagePrepError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ImagePrepError';
  }
}

export function scaledSize(width: number, height: number, maxEdge = MAX_IMAGE_EDGE): { width: number; height: number } {
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

export async function prepareImage(file: File): Promise<Blob> {
  if (!file.type.startsWith('image/')) {
    throw new ImagePrepError('Please choose a photo (JPEG, PNG or WebP).');
  }
  if (file.size > MAX_ORIGINAL_BYTES) {
    throw new ImagePrepError('This photo is too large. Please choose a smaller one.');
  }
  let bitmap: ImageBitmap;
  try {
    // Applies the EXIF rotation before the metadata is dropped.
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    throw new ImagePrepError("This photo couldn't be opened. Please try a JPEG or PNG photo.");
  }
  try {
    const { width, height } = scaledSize(bitmap.width, bitmap.height);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new ImagePrepError("This photo couldn't be processed on this device.");
    ctx.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY));
    if (!blob) throw new ImagePrepError("This photo couldn't be processed on this device.");
    return blob;
  } finally {
    bitmap.close();
  }
}
