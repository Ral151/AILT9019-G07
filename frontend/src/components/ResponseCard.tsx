import type { ComponentType, SVGProps } from 'react';
import type { Action, ApiResponse, Citation } from '../types/api';
import {
  AlertIcon,
  BanIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ExternalLinkIcon,
  RecycleIcon,
  ShieldCheckIcon,
  UsersIcon,
} from './icons';

interface ActionStyle {
  label: string;
  badge: string;
  bar: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}

const ACTION_STYLE: Record<Action, ActionStyle> = {
  answer: {
    label: 'Answer',
    badge: 'bg-emerald-50 text-emerald-900 ring-emerald-700/30',
    bar: 'bg-emerald-500',
    Icon: CheckCircleIcon,
  },
  answer_with_caveat: {
    label: 'Answer with note',
    badge: 'bg-amber-50 text-amber-900 ring-amber-700/30',
    bar: 'bg-amber-400',
    Icon: AlertIcon,
  },
  defer: {
    label: 'Check with staff',
    badge: 'bg-sky-50 text-sky-900 ring-sky-700/30',
    bar: 'bg-sky-500',
    Icon: UsersIcon,
  },
  refuse: {
    label: "Can't help with this",
    badge: 'bg-stone-100 text-stone-800 ring-stone-600/30',
    bar: 'bg-stone-400',
    Icon: BanIcon,
  },
};

// Display colours only (they never decide anything). Matched on the stream
// name returned by the server; unknown streams fall back to a neutral swatch.
// The bin name is always shown as text next to the swatch (FR-9).
const STREAM_SWATCH: Record<string, string> = {
  paper: 'bg-sky-500 text-white',
  metal: 'bg-yellow-300 text-yellow-950',
  metals: 'bg-yellow-300 text-yellow-950',
  plastic: 'bg-amber-800 text-white',
  plastics: 'bg-amber-800 text-white',
  'plastic bottle': 'bg-amber-800 text-white',
  'other plastic': 'bg-amber-600 text-white',
  'tetra pak': 'bg-red-500 text-white',
  'glass bottle': 'bg-lime-500 text-lime-950',
  'glass bottles': 'bg-lime-500 text-lime-950',
  'rechargeable battery': 'bg-orange-500 text-white',
  'rechargeable batteries': 'bg-orange-500 text-white',
};

function BinCategory({ name }: { name: string }) {
  const swatch = STREAM_SWATCH[name.toLowerCase()] ?? 'bg-stone-400 text-white';
  return (
    <div className="mt-4 flex items-center gap-4 rounded-xl bg-linear-to-r from-hku-50 to-white p-4 ring-1 ring-hku-100">
      <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl shadow-sm ${swatch}`}>
        <RecycleIcon className="h-7 w-7" />
      </span>
      <span>
        <span className="block text-sm text-stone-600">Bin category</span>
        <span className="text-xl font-bold text-stone-900">{name}</span>
      </span>
    </div>
  );
}

// "14-17" -> "lines 14-17"; "62-62" -> "line 62".
function formatLines(lines: string): string {
  const [start, end] = lines.split('-');
  return start && start === end ? `line ${start}` : `lines ${lines}`;
}

function CitationItem({ citation }: { citation: Citation }) {
  return (
    <li className="rounded-r-lg border-l-4 border-gold-400 bg-stone-50 p-3">
      <p className="text-sm font-semibold text-hku-700">{citation.title}</p>
      <p className="text-sm text-stone-600">
        {citation.section} · {formatLines(citation.lines)}
      </p>
      <blockquote className="mt-2 whitespace-pre-line text-stone-800">
        <span aria-hidden="true">“</span>
        <span>{citation.excerpt}</span>
        <span aria-hidden="true">”</span>
      </blockquote>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4">
        <span className="text-sm text-stone-500">Retrieved {citation.retrieved_at}</span>
        {citation.url && (
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center gap-1 font-medium text-hku-700 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-hku-700"
          >
            Open official source
            <ExternalLinkIcon className="h-4 w-4 shrink-0" />
          </a>
        )}
      </div>
    </li>
  );
}

export function ResponseCard({ response }: { response: ApiResponse }) {
  const style = ACTION_STYLE[response.action];
  const { Icon } = style;
  return (
    <article className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-stone-200">
      <div aria-hidden="true" className={`h-1.5 ${style.bar}`} />
      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ${style.badge}`}
          >
            <Icon className="h-4 w-4" />
            <span>{style.label}</span>
          </span>
          {response.served_from_cache && (
            <span className="rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700 ring-1 ring-stone-400">
              Demo answer
            </span>
          )}
        </div>

        {response.bin_category && <BinCategory name={response.bin_category} />}

        <p className="mt-4 text-lg leading-relaxed whitespace-pre-line text-stone-900">
          {response.answer_text}
        </p>

        {response.caveats.length > 0 && (
          <div className="mt-4 rounded-xl bg-amber-50 p-3 ring-1 ring-amber-200">
            <p className="flex items-center gap-2 font-semibold text-amber-950">
              <AlertIcon className="h-5 w-5 text-amber-600" />
              Please note
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-9 text-amber-950">
              {response.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </div>
        )}

        {response.citations.length > 0 && (
          <details className="group mt-4" open={response.action === 'defer'}>
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 rounded-lg px-1 font-semibold text-hku-700 hover:bg-hku-50 focus-visible:outline-2 focus-visible:outline-hku-700 [&::-webkit-details-marker]:hidden">
              <span>Official sources ({response.citations.length})</span>
              <ChevronDownIcon className="h-5 w-5 transition-transform duration-200 group-open:rotate-180" />
            </summary>
            <ul className="mt-2 space-y-2 group-open:animate-rise">
              {response.citations.map((c) => (
                <CitationItem key={`${c.source_id}:${c.lines}`} citation={c} />
              ))}
            </ul>
          </details>
        )}

        {response.redirect && (
          <a
            href={response.redirect.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg bg-hku-600 px-4 font-semibold text-white shadow-sm transition-colors hover:bg-hku-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hku-700"
          >
            {response.redirect.label}
            <ExternalLinkIcon className="h-4 w-4 shrink-0" />
          </a>
        )}
      </div>

      <p className="flex items-start gap-2 border-t border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-700 sm:px-5">
        <ShieldCheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-hku-600" />
        <span>On-site signs and staff always take priority. Hall rules may vary.</span>
      </p>
    </article>
  );
}
