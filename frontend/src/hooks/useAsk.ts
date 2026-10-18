import { useCallback, useRef, useState } from 'react';
import { ApiRequestError, ask } from '../api/client';
import type { ApiResponse } from '../types/api';

export interface Exchange {
  id: number;
  question: string;
  response: ApiResponse | null;
  error: string | null;
}

export function useAsk() {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [loading, setLoading] = useState(false);
  const nextId = useRef(1);

  const update = useCallback((id: number, patch: Partial<Exchange>) => {
    setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }, []);

  const run = useCallback(
    async (id: number, question: string) => {
      setLoading(true);
      try {
        update(id, { response: await ask(question) });
      } catch (err) {
        const message =
          err instanceof ApiRequestError
            ? err.message
            : 'Could not reach the server. Check your connection and try again.';
        update(id, { error: message });
      } finally {
        setLoading(false);
      }
    },
    [update],
  );

  const submit = useCallback(
    async (question: string) => {
      const id = nextId.current++;
      setExchanges((prev) => [...prev, { id, question, response: null, error: null }]);
      await run(id, question);
    },
    [run],
  );

  const retry = useCallback(
    async (id: number) => {
      const exchange = exchanges.find((e) => e.id === id);
      if (!exchange) return;
      update(id, { response: null, error: null });
      await run(id, exchange.question);
    },
    [exchanges, run, update],
  );

  const clear = useCallback(() => setExchanges([]), []);

  return { exchanges, loading, submit, retry, clear };
}
