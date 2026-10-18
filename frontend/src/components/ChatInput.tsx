import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { MAX_MESSAGE_LENGTH } from '../api/client';
import { SendIcon, Spinner } from './icons';

interface Props {
  disabled: boolean;
  onSubmit: (message: string) => void;
}

export function ChatInput({ disabled, onSubmit }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const trimmed = value.trim();
  const nearLimit = value.length > MAX_MESSAGE_LENGTH * 0.9;

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

  function send() {
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue('');
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
        placeholder="e.g. Where does a plastic drink bottle go?"
        aria-describedby="question-hint question-count"
        className="w-full resize-y rounded-xl border border-stone-300 bg-stone-50 p-3 text-base text-stone-900 transition-colors placeholder:text-stone-500 hover:border-stone-400 focus:border-hku-600 focus:bg-white focus:outline-none focus-visible:ring-4 focus-visible:ring-hku-600/20"
      />
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
          disabled={disabled || !trimmed}
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
