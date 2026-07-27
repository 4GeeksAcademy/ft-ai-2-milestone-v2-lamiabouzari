export function AnnouncementBar({
  children = "FREE SHIPPING IN FRANCE OVER 120 EUR | Complimentary tailoring on selected blazers",
}: {
  children?: React.ReactNode;
}) {
  return (
    <p className="border-b border-stone/80 bg-white/85 px-4 py-2 text-center text-[10px] leading-relaxed tracking-[0.12em] text-ink/70 sm:px-8 sm:text-xs sm:tracking-[0.18em]">
      {children}
    </p>
  );
}
