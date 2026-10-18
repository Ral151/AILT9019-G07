import { useEffect, useRef, useState } from 'react';
import { getSamples } from './api/client';
import { ChatInput } from './components/ChatInput';
import { ExchangeItem } from './components/ExchangeItem';
import { HowItWorks } from './components/HowItWorks';
import { ShieldCheckIcon, TrashIcon } from './components/icons';
import { SampleChips } from './components/SampleChips';
import { ServiceNotice } from './components/ServiceNotice';
import { SiteHeader } from './components/SiteHeader';
import { useAsk } from './hooks/useAsk';
import { useHealth } from './hooks/useHealth';

export default function App() {
  const { exchanges, loading, submit, retry, clear } = useAsk();
  const { health, status } = useHealth();
  const [samples, setSamples] = useState<string[]>([]);
  const resultsRef = useRef<HTMLElement>(null);
  const count = exchanges.length;

  useEffect(() => {
    getSamples()
      .then(setSamples)
      .catch(() => setSamples([]));
  }, []);

  // Newest answers appear first, right under the question box.
  useEffect(() => {
    if (count > 0) resultsRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [count]);

  return (
    <div className="flex min-h-dvh flex-col bg-canvas text-base text-stone-900">
      <SiteHeader status={status} />

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 pb-10">
        <section
          aria-label="Ask a question"
          className="relative -mt-10 rounded-2xl bg-white p-4 shadow-xl ring-1 shadow-hku-900/10 ring-stone-200 sm:-mt-12 sm:p-6"
        >
          <ChatInput disabled={loading} onSubmit={(m) => void submit(m)} />
          <SampleChips samples={samples} disabled={loading} onPick={(s) => void submit(s)} />
        </section>

        <ServiceNotice status={status} demoAnswers={health?.demo_cache_entries ?? 0} />

        {count === 0 ? (
          <HowItWorks />
        ) : (
          <section ref={resultsRef} aria-labelledby="results-heading" className="scroll-mt-4">
            <div className="flex items-center justify-between gap-2">
              <h2 id="results-heading" className="text-sm font-semibold tracking-wide text-stone-600 uppercase">
                Your questions ({count})
              </h2>
              <button
                type="button"
                onClick={clear}
                disabled={loading}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 text-stone-600 transition-colors hover:bg-stone-200 hover:text-stone-900 focus-visible:outline-2 focus-visible:outline-hku-700 disabled:opacity-50"
              >
                <TrashIcon className="h-4 w-4" />
                Clear
              </button>
            </div>
            <ol aria-live="polite" aria-busy={loading} className="mt-3 flex flex-col gap-6">
              {[...exchanges].reverse().map((exchange) => (
                <ExchangeItem key={exchange.id} exchange={exchange} busy={loading} onRetry={(id) => void retry(id)} />
              ))}
            </ol>
          </section>
        )}
      </main>

      <footer className="bg-hku-900 text-hku-50">
        <div className="mx-auto max-w-3xl space-y-2 px-4 py-6 text-sm">
          <p className="flex items-center gap-2 text-base font-semibold text-white">
            <ShieldCheckIcon className="h-5 w-5 shrink-0 text-gold-300" />
            On-site signs and staff always take priority.
          </p>
          <p>
            This helper covers HKU campus recycling only. Don&apos;t include personal information in
            your question.
          </p>
          {health && (
            <p className="text-hku-100/80">
              Answers come from {health.corpus_chunks} excerpts of HKU&apos;s official recycling
              documents (corpus {health.corpus_version}).
            </p>
          )}
        </div>
      </footer>
    </div>
  );
}
