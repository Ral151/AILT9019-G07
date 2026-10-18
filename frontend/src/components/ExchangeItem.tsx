import type { Exchange } from '../hooks/useAsk';
import { AlertIcon, QuestionIcon, RetryIcon, Spinner } from './icons';
import { ResponseCard } from './ResponseCard';

function LoadingCard() {
  return (
    <div role="status" className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-stone-200">
      <div aria-hidden="true" className="skeleton h-1.5" />
      <div className="p-4 sm:p-5">
        <p className="flex items-center gap-2 font-medium text-hku-700">
          <Spinner className="h-5 w-5" />
          Checking HKU&apos;s official documents…
        </p>
        <div aria-hidden="true" className="mt-4 space-y-2">
          <div className="skeleton h-12 w-full rounded-xl" />
          <div className="skeleton h-4 w-11/12 rounded" />
          <div className="skeleton h-4 w-3/4 rounded" />
        </div>
      </div>
    </div>
  );
}

function ErrorCard({ message, onRetry, disabled }: { message: string; onRetry: () => void; disabled: boolean }) {
  return (
    <div role="alert" className="rounded-2xl bg-red-50 p-4 text-red-950 ring-1 ring-red-200 sm:p-5">
      <p className="flex items-start gap-2">
        <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
        <span>{message}</span>
      </p>
      <button
        type="button"
        onClick={onRetry}
        disabled={disabled}
        className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg bg-white px-4 font-semibold text-red-900 ring-1 ring-red-300 transition-colors hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700 disabled:opacity-50"
      >
        <RetryIcon className="h-4 w-4" />
        Try again
      </button>
    </div>
  );
}

interface Props {
  exchange: Exchange;
  busy: boolean;
  onRetry: (id: number) => void;
}

export function ExchangeItem({ exchange, busy, onRetry }: Props) {
  return (
    <li className="animate-rise">
      <p className="mb-2 flex items-start gap-2 px-1 font-semibold text-stone-900">
        <QuestionIcon className="mt-0.5 h-5 w-5 shrink-0 text-hku-600" />
        <span>
          <span className="sr-only">You asked: </span>
          {exchange.question}
        </span>
      </p>
      {exchange.response && <ResponseCard response={exchange.response} />}
      {exchange.error && (
        <ErrorCard message={exchange.error} disabled={busy} onRetry={() => onRetry(exchange.id)} />
      )}
      {!exchange.response && !exchange.error && <LoadingCard />}
    </li>
  );
}
