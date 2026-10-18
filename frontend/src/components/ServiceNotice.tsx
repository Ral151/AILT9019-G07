import type { ServiceStatus } from '../hooks/useHealth';
import { AlertIcon } from './icons';

// FR-9 provider-down state. Explains what still works so a refusal is not a surprise.
const TEXT: Partial<Record<ServiceStatus, string>> = {
  safe: 'Live answers are switched off on this server. Safety guidance, refusals and official excerpts still work, but most bin answers will say the service is unavailable.',
  degraded:
    'The answer service is not responding reliably. You may see "service unavailable" for some questions. Please try again in a minute.',
  offline: "The helper's server is not responding. Check your connection, or try again later.",
};

export function ServiceNotice({ status, demoAnswers }: { status: ServiceStatus; demoAnswers: number }) {
  const text = TEXT[status];
  if (!text) return null;
  return (
    <div role="status" className="flex gap-3 rounded-xl bg-amber-50 p-4 text-amber-950 ring-1 ring-amber-200">
      <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
      <p>
        {text}
        {status !== 'offline' && demoAnswers > 0 && ' Sample questions may show reviewed demo answers.'}
      </p>
    </div>
  );
}
