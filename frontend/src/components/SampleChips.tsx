import { ArrowRightIcon } from './icons';

interface Props {
  samples: string[];
  disabled: boolean;
  onPick: (sample: string) => void;
}

export function SampleChips({ samples, disabled, onPick }: Props) {
  if (samples.length === 0) return null;
  return (
    <section aria-labelledby="samples-heading" className="mt-4 border-t border-stone-200 pt-4">
      <h2 id="samples-heading" className="text-sm font-semibold tracking-wide text-stone-600 uppercase">
        Try a sample question
      </h2>
      <ul className="mt-2 flex flex-wrap gap-2">
        {samples.map((sample) => (
          <li key={sample}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(sample)}
              className="group inline-flex min-h-11 items-center gap-2 rounded-full border border-hku-200 bg-hku-50 px-4 py-2 text-left text-base text-hku-900 transition-all hover:-translate-y-0.5 hover:border-hku-600 hover:bg-hku-100 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hku-700 disabled:translate-y-0 disabled:opacity-50"
            >
              {sample}
              <ArrowRightIcon className="h-4 w-4 shrink-0 opacity-60 transition-transform group-hover:translate-x-0.5" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
