/**
 * Convert and rescale images for memory upload: normalize to JPEG and max dimension.
 * On native iOS/Android, use pickActivityImages() to avoid "unavailable assets" (e.g. iCloud photos).
 */

const MAX_DIMENSION = 1920;
const PICK_LIMIT = 20;
const JPEG_QUALITY = 0.88;
const HEIC_EXTENSIONS = ['.heic', '.heif'];

function isHeic(file: File): boolean {
  const name = (file.name || '').toLowerCase();
  return HEIC_EXTENSIONS.some((ext) => name.endsWith(ext));
}

const UNAVAILABLE_ASSET_MESSAGE =
  'This photo could not be loaded. On iPhone, photos stored only in iCloud may show as unavailable—download them to your device first or choose another photo.';

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(UNAVAILABLE_ASSET_MESSAGE));
    img.src = src;
  });
}

function resizeToCanvas(
  img: HTMLImageElement,
  maxSize: number
): { canvas: HTMLCanvasElement; width: number; height: number } {
  let { width, height } = img;
  if (width <= maxSize && height <= maxSize) {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2d not available');
    ctx.drawImage(img, 0, 0);
    return { canvas, width, height };
  }
  const scale = maxSize / Math.max(width, height);
  width = Math.round(width * scale);
  height = Math.round(height * scale);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2d not available');
  ctx.drawImage(img, 0, 0, width, height);
  return { canvas, width, height };
}

function canvasToFile(canvas: HTMLCanvasElement, baseName: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('Failed to export image'));
          return;
        }
        const name = baseName.replace(/\.[^.]+$/i, '') + '.jpg';
        resolve(new File([blob], name, { type: 'image/jpeg' }));
      },
      'image/jpeg',
      JPEG_QUALITY
    );
  });
}

/**
 * Convert HEIC/HEIF to JPEG blob using heic2any if available.
 */
async function heicToBlob(file: File): Promise<Blob> {
  try {
    const heic2any = (await import('heic2any')).default;
    const result = await heic2any({
      blob: file,
      toType: 'image/jpeg',
      quality: JPEG_QUALITY,
    });
    const blob = Array.isArray(result) ? result[0] : result;
    if (!blob || !(blob instanceof Blob)) throw new Error('heic2any returned invalid result');
    return blob;
  } catch {
    throw new Error('HEIC conversion not supported in this browser. Try a JPEG or PNG image.');
  }
}

/**
 * Pick images from the device gallery using the native picker when on iOS/Android.
 * Avoids "unavailable assets" on iPhone (e.g. iCloud-only photos) by letting the native layer resolve the file.
 * Returns null on web or when the plugin is unavailable—caller should fall back to file input.
 */
export async function pickActivityImages(): Promise<File[] | null> {
  const { Capacitor } = await import('@capacitor/core');
  if (!Capacitor.isNativePlatform()) return null;
  try {
    const { Camera } = await import('@capacitor/camera');
    if (!Capacitor.isPluginAvailable('Camera')) return null;
    const { photos } = await Camera.pickImages({ limit: PICK_LIMIT });
    if (photos.length === 0) return [];
    // Read all photo data immediately in parallel; on iOS the picker's temp files can be
    // removed once the picker closes, so we must fetch before that happens.
    const blobs = await Promise.all(
      photos.map(async (photo, i) => {
        try {
          const webPath = Capacitor.convertFileSrc(photo.path);
          const res = await fetch(webPath);
          if (!res.ok) return null;
          const blob = await res.blob();
          return { blob, name: `photo-${i}.${photo.format || 'jpg'}`, type: blob.type || 'image/jpeg' };
        } catch {
          return null;
        }
      })
    );
    const valid = blobs.filter((b): b is NonNullable<typeof b> => b != null);
    const files: File[] = [];
    for (const { blob, name, type } of valid) {
      try {
        const file = new File([blob], name, { type });
        files.push(await processImageForUpload(file));
      } catch {
        // Skip if processing fails (e.g. corrupt image)
      }
    }
    return files;
  } catch {
    return null;
  }
}

/**
 * Process an image file for upload: convert to JPEG and rescale so longest side is at most MAX_DIMENSION.
 * HEIC/HEIF is converted via heic2any when available.
 * Rejects with a user-friendly message when the asset is unavailable (e.g. iCloud placeholder on iOS).
 */
export async function processImageForUpload(file: File): Promise<File> {
  if (file.size === 0) {
    throw new Error(UNAVAILABLE_ASSET_MESSAGE);
  }
  let blob: Blob = file;
  let objectUrl: string | null = null;

  if (isHeic(file)) {
    blob = await heicToBlob(file);
  }

  objectUrl = URL.createObjectURL(blob);
  try {
    const img = await loadImage(objectUrl);
    const { canvas } = resizeToCanvas(img, MAX_DIMENSION);
    const baseName = (file.name || 'image').replace(/\.[^.]+$/i, '') || 'image';
    return canvasToFile(canvas, baseName);
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}
