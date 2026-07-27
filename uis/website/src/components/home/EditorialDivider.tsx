export function EditorialDivider({ className = "" }: { className?: string }) {
  return (
    <div
      className={`editorial-divider ${className}`.trim()}
      aria-hidden
    />
  );
}
