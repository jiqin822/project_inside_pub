/**
 * Request microphone access with a guard for environments where
 * navigator.mediaDevices is undefined (e.g. HTTP on iOS remote server).
 * On iOS, getUserMedia requires a secure context (HTTPS or localhost).
 */
const MEDIA_UNAVAILABLE_MESSAGE =
  'Microphone is not available. On iPhone, use HTTPS or run the native app.';

export function isMediaDevicesSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
}

export async function getMicrophoneStream(
  constraints: MediaStreamConstraints = { audio: true }
): Promise<MediaStream> {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    throw new Error(MEDIA_UNAVAILABLE_MESSAGE);
  }
  return navigator.mediaDevices.getUserMedia(constraints);
}
