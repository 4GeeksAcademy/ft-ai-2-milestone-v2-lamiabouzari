interface StateMessageProps {
  readonly tone?: "loading" | "empty" | "error" | "success";
  readonly title: string;
  readonly description?: string;
}

const TONE_STYLES: Record<NonNullable<StateMessageProps["tone"]>, string> = {
  loading: "border-line bg-panel-soft text-slate-600",
  empty: "border-line bg-panel-soft text-slate-600",
  error: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

export function StateMessage({ tone = "empty", title, description }: StateMessageProps) {
  return (
    <div className={`rounded-xl border p-4 text-sm ${TONE_STYLES[tone]}`}>
      <p className="font-semibold">{title}</p>
      {description ? <p className="mt-1">{description}</p> : null}
    </div>
  );
}
