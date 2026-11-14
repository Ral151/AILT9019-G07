import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from 'react';
import { MAX_MESSAGE_LENGTH } from '../api/client';
import { ImagePrepError, prepareImage } from '../api/image';
import { CameraIcon, ImageIcon, SendIcon, Spinner, XIcon } from './icons';

// §8.3 wording; also in the README.
export const PHOTO_PRIVACY_NOTE =
  "Photos are processed in memory and are not saved or logged by this app. To identify the item, the photo is sent to a third-party AI service under its own terms. Please don't upload photos that show people, faces, or documents.";

interface Props {
  disabled: boolean;
  // false when /api/health says photo recognition is off.
  photosEnabled: boolean;
  onSubmit: (message: string, photo: Blob | null) => void;
}

interface Photo {
  blob: Blob;
  url: string;
}

const PHOTO_BUTTON =
  'min-h-11 items-center gap-2 rounded-xl px-4 font-semibold text-hku-700 ring-1 ring-hku-200 transition-colors hover:bg-hku-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hku-700 disabled:cursor-not-allowed disabled:text-stone-400 disabled:ring-stone-200 disabled:hover:bg-transparent';

export function ChatInput({ disabled, photosEnabled, onSubmit }: Props) {
  const [value, setValue] = useState('');
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const trimmed = value.trim();
  const nearLimit = value.length > MAX_MESSAGE_LENGTH * 0.9;
  const canSend = !disabled && !preparing && (trimmed.length > 0 || photo !== null);

  // "/" focuses the question box from anywhere on the page.
  useEffect(() => {
    function onKey(event: globalThis.KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing = target?.closest('input, textarea, select, [contenteditable="true"]');
      if (event.key === '/' && !typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        textareaRef.current?.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // Release the preview URL when the photo is replaced, removed or sent.
  useEffect(() => {
    if (!photo) return;
    return () => URL.revokeObjectURL(photo.url);
  }, [photo]);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ''; // so choosing the same file again still fires
    if (!file) return;
    setPhotoError(null);
    setPreparing(true);
    try {
      const blob = await prepareImage(file);
      setPhoto({ blob, url: URL.createObjectURL(blob) });
    } catch (err) {
      setPhoto(null);
      setPhotoError(err instanceof ImagePrepError ? err.message : "This photo couldn't be opened. Please try another one.");
    } finally {
      setPreparing(false);
    }
  }

  function send() {
    if (!canSend) return;
    onSubmit(trimmed, photo?.blob ?? null);
    setValue('');
    setPhoto(null);
    setPhotoError(null);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  const photoButtonsDisabled = disabled || preparing || !photosEnabled;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <label htmlFor="question" className="font-semibold text-stone-900">
        What do you want to throw away?
      </label>
      <textarea
        ref={textareaRef}
        id="question"
        value={value}
        maxLength={MAX_MESSAGE_LENGTH}
        rows={2}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={photo ? 'Optional: add a question about the photo' : 'e.g. Where does a plastic drink bottle go?'}
        aria-describedby="question-hint question-count"
        className="w-full resize-y rounded-xl border border-stone-300 bg-stone-50 p-3 text-base text-stone-900 transition-colors placeholder:text-stone-500 hover:border-stone-400 focus:border-hku-600 focus:bg-white focus:outline-none focus-visible:ring-4 focus-visible:ring-hku-600/20"
      />

      {/* Two ways to add a photo: the camera (phones) or an existing file. */}
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="camera-input"
        onChange={(e) => void handleFile(e)}
      />
      <input
        ref={uploadRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/*"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="upload-input"
        onChange={(e) => void handleFile(e)}
      />
      <div className="flex flex-wrap items-center gap-2">
        {/* Only touch devices get "Take photo"; on a laptop it would just open the file picker. */}
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          disabled={photoButtonsDisabled}
          className={`hidden pointer-coarse:inline-flex ${PHOTO_BUTTON}`}
        >
          <CameraIcon className="h-5 w-5" />
          Take photo
        </button>
        <button
          type="button"
          onClick={() => uploadRef.current?.click()}
          disabled={photoButtonsDisabled}
          className={`inline-flex ${PHOTO_BUTTON}`}
        >
          <ImageIcon className="h-5 w-5" />
          Upload photo
        </button>
        {preparing && (
          <span role="status" className="inline-flex items-center gap-2 text-sm text-stone-600">
            <Spinner className="h-4 w-4" />
            Preparing photo…
          </span>
        )}
      </div>

      {photo && (
        <div className="flex items-center gap-3 rounded-xl bg-stone-50 p-2 ring-1 ring-stone-200">
          <img src={photo.url} alt="Photo to send" className="h-16 w-16 rounded-lg object-cover" />
          <span className="flex-1 text-sm text-stone-700">Photo added. Ask about one item at a time.</span>
          <button
            type="button"
            onClick={() => setPhoto(null)}
            disabled={disabled}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 text-stone-600 transition-colors hover:bg-stone-200 hover:text-stone-900 focus-visible:outline-2 focus-visible:outline-hku-700 disabled:opacity-50"
          >
            <XIcon className="h-4 w-4" />
            Remove photo
          </button>
        </div>
      )}

      {photoError && (
        <p role="alert" className="text-sm font-medium text-red-700">
          {photoError}
        </p>
      )}

      <p className="text-sm text-stone-600">
        {photosEnabled
          ? PHOTO_PRIVACY_NOTE
          : 'Photo recognition is not available right now. Please describe the item in words instead.'}
      </p>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-stone-600">
          <span id="question-hint" className="hidden sm:inline">
            Enter to send · Shift+Enter for a new line · press <kbd className="rounded border border-stone-300 bg-white px-1.5 font-sans">/</kbd> to type ·{' '}
          </span>
          <span id="question-count" className={nearLimit ? 'font-semibold text-amber-700' : undefined}>
            {value.length}/{MAX_MESSAGE_LENGTH}
          </span>
        </p>
        <button
          type="submit"
          disabled={!canSend}
          className="inline-flex min-h-11 min-w-28 items-center justify-center gap-2 rounded-xl bg-hku-600 px-5 font-semibold text-white shadow-sm transition-all hover:bg-hku-700 hover:shadow-md active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hku-700 disabled:cursor-not-allowed disabled:bg-stone-400 disabled:shadow-none"
        >
          {disabled ? (
            <>
              <Spinner className="h-5 w-5" />
              Asking…
            </>
          ) : (
            <>
              Ask
              <SendIcon className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}
