type StylingSuggestionsProps = {
  text: string;
};

export function StylingSuggestions({ text }: StylingSuggestionsProps) {
  return (
    <section className="mt-10 rounded-xl border border-slate-200 bg-slate-50 p-6">
      <h2 className="text-lg font-semibold text-slate-700">Styling Suggestions</h2>
      <p className="mt-6 text-base italic text-slate-600">&ldquo;{text}&rdquo;</p>
    </section>
  );
}
