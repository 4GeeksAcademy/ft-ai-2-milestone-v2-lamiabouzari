"use client";

type CheckoutStepsProps = {
  orderTotalLabel?: string;
};

export function CheckoutSteps({
  orderTotalLabel = "Order Total: EUR 438 (Tax Included)",
}: CheckoutStepsProps) {
  return (
    <form
      className="rounded-2xl border border-stone/90 bg-white/90 p-5 shadow-sm md:p-8"
      aria-label="Three step checkout form"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="border-b border-stone/70 pb-8" id="step-personal">
        <div className="mb-5 flex items-center gap-3">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-sleeve/70 bg-stone/40 text-sm font-semibold">
            1
          </span>
          <div>
            <h2 className="font-serif text-3xl leading-none">Personal details</h2>
            <p className="mt-1 text-sm text-ink/70">
              Please enter your contact information. We&apos;ll use this to send
              order updates and receipts.
            </p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm text-ink/80">
            First name
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="firstName"
              autoComplete="given-name"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            Last name
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="lastName"
              autoComplete="family-name"
              required
            />
          </label>
          <label className="text-sm text-ink/80 sm:col-span-2">
            Email Address
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="email"
              name="email"
              autoComplete="email"
              required
            />
          </label>
          <label className="text-sm text-ink/80 sm:col-span-2">
            Phone Number (Optional)
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="tel"
              name="phone"
              autoComplete="tel"
            />
          </label>
        </div>
        <div className="mt-5 flex justify-end">
          <a
            href="#step-shipping"
            className="rounded-full border border-ink/20 bg-ink px-5 py-2.5 text-sm font-medium text-oat transition hover:bg-ink/90"
          >
            Continue to Shipping
          </a>
        </div>
      </div>

      <div className="border-b border-stone/70 py-8" id="step-shipping">
        <div className="mb-5 flex items-center gap-3">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-clay/70 bg-clay/30 text-sm font-semibold">
            2
          </span>
          <div>
            <h2 className="font-serif text-3xl leading-none">Shipping address</h2>
            <p className="mt-1 text-sm text-ink/70">
              Enter the address where you&apos;d like your order delivered.
            </p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm text-ink/80 sm:col-span-2">
            Street address
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="street"
              autoComplete="address-line1"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            Apartment, Suite, Unit, etc. (Optional)
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="unit"
              autoComplete="address-line2"
            />
          </label>
          <label className="text-sm text-ink/80">
            Postal code
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="postalCode"
              autoComplete="postal-code"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            City
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="city"
              autoComplete="address-level2"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            Country
            <select
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              name="country"
              autoComplete="country"
              required
              defaultValue="France"
            >
              <option>France</option>
              <option>Belgium</option>
              <option>Switzerland</option>
              <option>Luxembourg</option>
            </select>
          </label>
        </div>
        <div className="mt-5 flex justify-end">
          <a
            href="#step-card"
            className="rounded-full border border-ink/20 bg-ink px-5 py-2.5 text-sm font-medium text-oat transition hover:bg-ink/90"
          >
            Continue to Payment
          </a>
        </div>
      </div>

      <div className="pt-8" id="step-card">
        <div className="mb-5 flex items-center gap-3">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-stone bg-oat text-sm font-semibold">
            3
          </span>
          <div>
            <h2 className="font-serif text-3xl leading-none">Payment Information</h2>
            <p className="mt-1 text-sm text-ink/70">
              Your payment information is encrypted and securely processed.
            </p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm text-ink/80 sm:col-span-2">
            Name on card
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="cardName"
              autoComplete="cc-name"
              required
            />
          </label>
          <label className="text-sm text-ink/80 sm:col-span-2">
            Card number
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="cardNumber"
              autoComplete="cc-number"
              inputMode="numeric"
              placeholder="4242 4242 4242 4242"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            Expiration Date
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="expiry"
              autoComplete="cc-exp"
              placeholder="MM/YY"
              required
            />
          </label>
          <label className="text-sm text-ink/80">
            CVC
            <input
              className="mt-2 w-full rounded-xl border border-stone bg-oat/70 px-4 py-3 text-sm"
              type="text"
              name="cvc"
              autoComplete="cc-csc"
              inputMode="numeric"
              required
            />
          </label>
        </div>
        <div className="mt-7 flex flex-wrap items-center justify-between gap-4">
          <p className="text-xs uppercase tracking-[0.18em] text-ink/60">
            {orderTotalLabel}
          </p>
          <button
            type="submit"
            className="rounded-full border border-ink/20 bg-ink px-6 py-3 text-sm font-semibold text-oat transition hover:bg-ink/90"
          >
            Complete Purchase
          </button>
        </div>
      </div>
    </form>
  );
}
