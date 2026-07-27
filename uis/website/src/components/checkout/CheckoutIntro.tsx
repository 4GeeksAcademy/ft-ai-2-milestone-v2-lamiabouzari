export function CheckoutIntro({
  title = "Complete Your Order in Three Simple Steps",
  body = "Complete your order by entering your contact information, shipping details, and payment method. Your information is securely processed and used only to fulfill your order.",
}: {
  title?: string;
  body?: string;
}) {
  return (
    <section className="rounded-2xl border border-stone/90 bg-white/85 p-5 shadow-sm backdrop-blur sm:p-6 md:p-9">
      <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-ink/55">
            Secure Checkout
          </p>
          <h1 className="mt-2 max-w-xl font-serif text-3xl leading-tight text-ink sm:text-4xl md:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-ink/75 sm:text-base">
            {body}
          </p>
        </div>
        <nav
          aria-label="Checkout steps"
          className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-3"
        >
          <a
            href="#step-personal"
            className="rounded-2xl border border-sleeve/60 bg-stone/35 px-3 py-3 text-center text-[11px] uppercase tracking-[0.14em] text-ink/65 transition hover:bg-stone/50 sm:py-4 sm:text-xs sm:tracking-[0.18em]"
          >
            <span className="sm:hidden">01 Personal</span>
            <span className="hidden sm:inline">01 Personal Information</span>
          </a>
          <a
            href="#step-shipping"
            className="rounded-2xl border border-clay/70 bg-clay/25 px-3 py-3 text-center text-[11px] uppercase tracking-[0.14em] text-ink/65 transition hover:bg-clay/40 sm:py-4 sm:text-xs sm:tracking-[0.18em]"
          >
            <span className="sm:hidden">02 Shipping</span>
            <span className="hidden sm:inline">02 Shipping Details</span>
          </a>
          <a
            href="#step-card"
            className="rounded-2xl border border-stone bg-white/80 px-3 py-3 text-center text-[11px] uppercase tracking-[0.14em] text-ink/65 transition hover:bg-white sm:py-4 sm:text-xs sm:tracking-[0.18em]"
          >
            <span className="sm:hidden">03 Payment</span>
            <span className="hidden sm:inline">03 Payment</span>
          </a>
        </nav>
      </div>
    </section>
  );
}
