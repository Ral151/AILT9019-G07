import { useEffect, useState } from 'react';
import { getHealth } from '../api/client';
import type { HealthResponse } from '../types/api';

// What the UI tells the user about the answer service (FR-9 provider-down state).
//   live     - LLM configured and reachable
//   degraded - LLM configured but the last reachability check failed
//   safe     - no LLM: templates and official excerpts only
//   offline  - the API itself did not respond
export type ServiceStatus = 'checking' | 'live' | 'degraded' | 'safe' | 'offline';

function statusOf(health: HealthResponse): ServiceStatus {
  if (health.text_provider === 'none' || health.text_provider === 'mock') return 'safe';
  if (health.text_provider_reachable === false) return 'degraded';
  return 'live';
}

export function useHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<ServiceStatus>('checking');

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((h) => {
        if (cancelled) return;
        setHealth(h);
        setStatus(statusOf(h));
      })
      .catch(() => {
        if (!cancelled) setStatus('offline');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { health, status };
}
