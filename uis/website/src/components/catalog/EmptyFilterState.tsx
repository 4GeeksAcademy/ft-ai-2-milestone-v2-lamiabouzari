export function EmptyFilterState({
  message = "No products match the selected filters.",
}: {
  message?: string;
}) {
  return (
    <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
      {message}
    </p>
  );
}
