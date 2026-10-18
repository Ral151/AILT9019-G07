import { FileTextIcon, SearchIcon, ShieldCheckIcon } from './icons';

const STEPS = [
  {
    Icon: SearchIcon,
    title: 'Ask about one item',
    text: 'Type what you want to throw away, like a drink bottle or a takeaway box.',
  },
  {
    Icon: FileTextIcon,
    title: "We check HKU's documents",
    text: "Only HKU's official recycling pages and posters are used. Nothing is guessed.",
  },
  {
    Icon: ShieldCheckIcon,
    title: 'Get a cited answer',
    text: "Every bin answer quotes the official text. If the documents don't cover it, it says so.",
  },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-heading" className="animate-rise">
      <h2 id="how-heading" className="text-sm font-semibold tracking-wide text-stone-600 uppercase">
        How it works
      </h2>
      <ol className="mt-3 grid gap-3 sm:grid-cols-3">
        {STEPS.map(({ Icon, title, text }, i) => (
          <li key={title} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-hku-50 text-hku-700 ring-1 ring-hku-100">
                <Icon className="h-5 w-5" />
              </span>
              <span className="text-sm font-semibold text-gold-600">Step {i + 1}</span>
            </div>
            <p className="mt-3 font-semibold text-stone-900">{title}</p>
            <p className="mt-1 text-stone-600">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
