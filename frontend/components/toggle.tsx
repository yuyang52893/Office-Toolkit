import { Check } from "lucide-react";

type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
};

export function Toggle({ checked, onChange, label, description }: ToggleProps) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3.5 transition hover:border-slate-300">
      <span>
        <span className="block text-sm font-semibold text-slate-800">{label}</span>
        {description ? (
          <span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span>
        ) : null}
      </span>
      <input
        type="checkbox"
        className="sr-only"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span
        aria-hidden="true"
        className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border transition ${
          checked
            ? "border-blue-600 bg-blue-600 text-white"
            : "border-slate-300 bg-white text-transparent"
        }`}
      >
        <Check size={13} strokeWidth={3} />
      </span>
    </label>
  );
}

