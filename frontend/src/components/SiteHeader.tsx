import type { ServiceStatus } from '../hooks/useHealth';
import { RecycleIcon } from './icons';

const STATUS: Record<ServiceStatus, { label: string; dot: string }> = {
  checking: { label: 'Checking service…', dot: 'bg-stone-300' },
  live: { label: 'Live answers', dot: 'bg-emerald-400 animate-pulse' },
  degraded: { label: 'Answer service unstable', dot: 'bg-amber-400' },
  safe: { label: 'Safe mode', dot: 'bg-amber-400' },
  offline: { label: 'Server not reachable', dot: 'bg-red-400' },
};

export function SiteHeader({ status }: { status: ServiceStatus }) {
  const s = STATUS[status];
  return (
    <header className="hero text-white">
      <div className="mx-auto max-w-3xl px-4 pt-8 pb-16 text-center sm:pt-12 sm:pb-20">
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/25 backdrop-blur-sm">
          <RecycleIcon className="h-8 w-8 text-gold-300" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">HKU Campus Recycling Rules Helper</h1>
        <p className="mx-auto mt-2 max-w-xl text-base text-hku-50/90 sm:text-lg">
          Ask where something goes on campus. Every bin answer quotes HKU&apos;s official recycling
          documents.
        </p>
        <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-black/20 px-3 py-1 text-sm ring-1 ring-white/15">
          <span aria-hidden="true" className={`h-2 w-2 rounded-full ${s.dot}`} />
          <span>{s.label}</span>
        </p>
      </div>
    </header>
  );
}
