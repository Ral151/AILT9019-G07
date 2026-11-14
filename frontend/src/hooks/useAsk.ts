import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiRequestError, ask } from '../api/client';
import type { ApiResponse } from '../types/api';

export interface Exchange {
  id: number;
  question: string;
  // The prepared photo, kept in memory only so "Try again" can resend it.
  photo: Blob | null;
  photoUrl: string | null; // object URL for the thumbnail
  response: ApiResponse | null;
  error: string | null;
}

export function useAsk() {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [loading, setLoading] = useState(false);
  const nextId = useRef(1);
  const urls = useRef<string[]>([]);

  const revokeAll = useCallback(() => {
    urls.current.forEach((url) => URL.revokeObjectURL(url));
    urls.current = [];
  }, []);

  useEffect(() => revokeAll, [revokeAll]);

  const update = useCallback((id: number, patch: Partial<Exchange>) => {
    setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }, []);

  const run = useCallback(
    async (id: number, question: string, photo: Blob | null) => {
      setLoading(true);
      try {
        update(id, { response: await ask(question, photo) });
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
    async (question: string, photo: Blob | null = null) => {
      const id = nextId.current++;
      const photoUrl = photo ? URL.createObjectURL(photo) : null;
      if (photoUrl) urls.current.push(photoUrl);
      setExchanges((prev) => [...prev, { id, question, photo, photoUrl, response: null, error: null }]);
      await run(id, question, photo);
    },
    [run],
  );

  const retry = useCallback(
    async (id: number) => {
      const exchange = exchanges.find((e) => e.id === id);
      if (!exchange) return;
      update(id, { response: null, error: null });
      await run(id, exchange.question, exchange.photo);
    },
    [exchanges, run, update],
  );

  const clear = useCallback(() => {
    revokeAll();
    setExchanges([]);
  }, [revokeAll]);

  return { exchanges, loading, submit, retry, clear };
}
