"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError, apiRequest } from "@/lib/api-client";
import { clearToken } from "@/lib/auth";

type Country = "USA" | "Spain";
type Status = "active" | "suspended";

interface Supplier {
  id: number;
  name: string;
  country: Country;
  categories: string[];
  rate_per_shipment: number;
  currency: "USD" | "EUR";
  updated_at: string;
  status: Status;
  service_zone: string | null;
  contact_email: string | null;
  notes: string | null;
}

interface Draft {
  rate: string;
  status: Status;
  editingRate: boolean;
  editingStatus: boolean;
}

const CATEGORIES: { value: string; label: string }[] = [
  { value: "carrier_last_mile", label: "Carrier last mile" },
  { value: "carrier_international", label: "Carrier international" },
  { value: "warehouse_supplies", label: "Warehouse supplies" },
  { value: "packaging_materials", label: "Packaging materials" },
  { value: "reverse_logistics", label: "Reverse logistics" },
  { value: "fleet_maintenance", label: "Fleet maintenance" },
  { value: "it_and_wms_software", label: "IT and WMS software" },
  { value: "cleaning_and_facilities", label: "Cleaning and facilities" },
];

const EMPTY_FORM = {
  name: "",
  country: "USA" as Country,
  categories: [] as string[],
  rate_per_shipment: "",
  status: "active" as Status,
  service_zone: "",
  contact_email: "",
  notes: "",
};

function categoryLabel(value: string): string {
  return CATEGORIES.find((item) => item.value === value)?.label ?? value;
}

function currencyFor(country: Country): "USD" | "EUR" {
  return country === "USA" ? "USD" : "EUR";
}

function listPath(country: string, category: string): string {
  const params = new URLSearchParams();
  if (country) params.set("country", country);
  if (category) params.set("category", category);
  const query = params.toString();
  return query ? `/suppliers?${query}` : "/suppliers";
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The supplier API could not be reached.";
}

function draftFor(supplier: Supplier, current?: Draft): Draft {
  return {
    rate: current?.rate ?? String(supplier.rate_per_shipment),
    status: current?.status ?? supplier.status,
    editingRate: current?.editingRate ?? false,
    editingStatus: current?.editingStatus ?? false,
  };
}

export default function SuppliersPage() {
  return (
    <RequireAuth>
      <SupplierDirectory />
    </RequireAuth>
  );
}

function SupplierDirectory() {
  const requestSeq = useRef(0);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [country, setCountry] = useState("");
  const [category, setCategory] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createNotice, setCreateNotice] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [savingById, setSavingById] = useState<Record<number, boolean>>({});
  const [errorById, setErrorById] = useState<Record<number, string | null>>({});
  const [noticeById, setNoticeById] = useState<Record<number, string | null>>({});

  useEffect(() => {
    const request = ++requestSeq.current;
    const path = listPath(country, category);
    apiRequest<Supplier[]>(path, { auth: true, cache: "no-store" })
      .then((rows) => {
        if (request !== requestSeq.current) return;
        setSuppliers(rows);
        setListError(null);
      })
      .catch((error: unknown) => {
        if (request !== requestSeq.current) return;
        if (error instanceof ApiError && error.status === 401) clearToken();
        setListError(messageFrom(error));
      })
      .finally(() => {
        if (request === requestSeq.current) setLoadingList(false);
      });
  }, [country, category]);

  function applyFilters(nextCountry: string, nextCategory: string) {
    setLoadingList(true);
    setListError(null);
    setCountry(nextCountry);
    setCategory(nextCategory);
  }

  async function refreshList() {
    const request = ++requestSeq.current;
    try {
      const rows = await apiRequest<Supplier[]>(listPath(country, category), { auth: true, cache: "no-store" });
      if (request !== requestSeq.current) return;
      setSuppliers(rows);
      setListError(null);
    } catch (error) {
      if (request !== requestSeq.current) return;
      if (error instanceof ApiError && error.status === 401) clearToken();
      setListError(messageFrom(error));
    } finally {
      if (request === requestSeq.current) setLoadingList(false);
    }
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    setCreateNotice(null);
    const rate = Number(form.rate_per_shipment);
    if (!Number.isFinite(rate)) {
      setCreateError("Enter a finite rate per shipment greater than zero.");
      setCreating(false);
      return;
    }
    try {
      await apiRequest<Supplier>("/suppliers", {
        method: "POST",
        auth: true,
        body: {
          name: form.name,
          country: form.country,
          categories: form.categories,
          rate_per_shipment: rate,
          currency: currencyFor(form.country),
          status: form.status,
          service_zone: form.service_zone || null,
          contact_email: form.contact_email || null,
          notes: form.notes || null,
        },
      });
      setForm(EMPTY_FORM);
      setCreateNotice("Supplier registered.");
      await refreshList();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) clearToken();
      setCreateError(messageFrom(error));
    } finally {
      setCreating(false);
    }
  }

  function updateDraft(id: number, supplier: Supplier, patch: Partial<Draft>) {
    setDrafts((current) => ({ ...current, [id]: { ...draftFor(supplier, current[id]), ...patch } }));
  }

  async function saveRate(supplier: Supplier) {
    const draft = draftFor(supplier, drafts[supplier.id]);
    const rate = Number(draft.rate);
    if (!Number.isFinite(rate)) {
      setErrorById((current) => ({ ...current, [supplier.id]: "Enter a finite rate per shipment greater than zero." }));
      return;
    }
    setSavingById((current) => ({ ...current, [supplier.id]: true }));
    setErrorById((current) => ({ ...current, [supplier.id]: null }));
    setNoticeById((current) => ({ ...current, [supplier.id]: null }));
    try {
      const updated = await apiRequest<Supplier>(`/suppliers/${supplier.id}/rate`, {
        method: "PATCH",
        auth: true,
        body: { rate_per_shipment: rate },
      });
      setSuppliers((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setDrafts((current) => ({
        ...current,
        [supplier.id]: { ...draftFor(updated, current[supplier.id]), editingRate: false, rate: String(updated.rate_per_shipment) },
      }));
      setNoticeById((current) => ({ ...current, [supplier.id]: "Rate saved." }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) clearToken();
      setErrorById((current) => ({ ...current, [supplier.id]: messageFrom(error) }));
    } finally {
      setSavingById((current) => ({ ...current, [supplier.id]: false }));
    }
  }

  async function saveStatus(supplier: Supplier) {
    const draft = draftFor(supplier, drafts[supplier.id]);
    setSavingById((current) => ({ ...current, [supplier.id]: true }));
    setErrorById((current) => ({ ...current, [supplier.id]: null }));
    setNoticeById((current) => ({ ...current, [supplier.id]: null }));
    try {
      const updated = await apiRequest<Supplier>(`/suppliers/${supplier.id}/status`, {
        method: "PATCH",
        auth: true,
        body: { status: draft.status },
      });
      setSuppliers((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setDrafts((current) => ({
        ...current,
        [supplier.id]: { ...draftFor(updated, current[supplier.id]), editingStatus: false, status: updated.status },
      }));
      setNoticeById((current) => ({ ...current, [supplier.id]: "Status saved." }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) clearToken();
      setErrorById((current) => ({ ...current, [supplier.id]: messageFrom(error) }));
    } finally {
      setSavingById((current) => ({ ...current, [supplier.id]: false }));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl text-foreground">Suppliers</h1>
        <p className="mt-1 text-sm text-slate-600">TrackFlow carrier and warehouse supplier directory for Los Angeles and Zaragoza.</p>
      </div>

      <section className="dashboard-card p-5">
        <h2 className="font-display text-xl text-foreground">Register a supplier</h2>
        <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={onCreate}>
          <label className="text-sm">
            Name
            <input className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </label>
          <label className="text-sm">
            Country
            <select
              className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2"
              value={form.country}
              onChange={(event) => setForm({ ...form, country: event.target.value as Country })}
            >
              <option value="USA">USA</option>
              <option value="Spain">Spain</option>
            </select>
          </label>
          <label className="text-sm">
            Rate per shipment ({currencyFor(form.country)})
            <input className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" inputMode="decimal" value={form.rate_per_shipment} onChange={(event) => setForm({ ...form, rate_per_shipment: event.target.value })} required />
          </label>
          <label className="text-sm">
            Status
            <select className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as Status })}>
              <option value="active">active</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          <fieldset className="text-sm sm:col-span-2">
            <legend>Categories</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {CATEGORIES.map((item) => (
                <label key={item.value} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.categories.includes(item.value)}
                    onChange={(event) => {
                      const categories = event.target.checked
                        ? [...form.categories, item.value]
                        : form.categories.filter((value) => value !== item.value);
                      setForm({ ...form, categories });
                    }}
                  />
                  {item.label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="text-sm">
            Service zone
            <input className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" value={form.service_zone} onChange={(event) => setForm({ ...form, service_zone: event.target.value })} />
          </label>
          <label className="text-sm">
            Contact email
            <input className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" type="email" value={form.contact_email} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} />
          </label>
          <label className="text-sm sm:col-span-2">
            Notes
            <textarea className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2" rows={2} value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </label>
          <div className="sm:col-span-2">
            <button className="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={creating} type="submit">
              {creating ? "Registering…" : "Register supplier"}
            </button>
          </div>
        </form>
        {createError ? <div className="mt-4"><StateMessage tone="error" title="Supplier was not registered" description={createError} /></div> : null}
        {createNotice ? <div className="mt-4"><StateMessage tone="success" title={createNotice} /></div> : null}
      </section>

      <section className="dashboard-card p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="font-display text-xl text-foreground">Directory</h2>
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="text-sm">
              Country
              <select className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 sm:w-40" value={country} onChange={(event) => applyFilters(event.target.value, category)}>
                <option value="">All countries</option>
                <option value="USA">USA</option>
                <option value="Spain">Spain</option>
              </select>
            </label>
            <label className="text-sm">
              Category
              <select className="mt-1 block w-full rounded-lg border border-line bg-white px-3 py-2 sm:w-56" value={category} onChange={(event) => applyFilters(country, event.target.value)}>
                <option value="">All categories</option>
                {CATEGORIES.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-4">
          {loadingList ? <StateMessage tone="loading" title="Loading suppliers" /> : null}
          {!loadingList && listError ? <StateMessage tone="error" title="The directory could not be loaded" description={listError} /> : null}
          {!loadingList && !listError && suppliers.length === 0 && !country && !category ? (
            <StateMessage tone="empty" title="No suppliers yet" description="Register the first supplier with the form above." />
          ) : null}
          {!loadingList && !listError && suppliers.length === 0 && (country || category) ? (
            <StateMessage tone="empty" title="No matching suppliers" description="Try another country or category." />
          ) : null}
        </div>

        {!loadingList && !listError && suppliers.length > 0 ? (
          <>
            <div className="mt-4 hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-slate-500">
                    <th className="py-2 pr-3 font-medium">Name</th>
                    <th className="py-2 pr-3 font-medium">Country</th>
                    <th className="py-2 pr-3 font-medium">Categories</th>
                    <th className="py-2 pr-3 font-medium">Rate</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 font-medium">Last rate update</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map((supplier) => (
                    <SupplierTableRow
                      key={supplier.id}
                      supplier={supplier}
                      draft={draftFor(supplier, drafts[supplier.id])}
                      saving={Boolean(savingById[supplier.id])}
                      error={errorById[supplier.id]}
                      notice={noticeById[supplier.id]}
                      onDraft={(patch) => updateDraft(supplier.id, supplier, patch)}
                      onSaveRate={() => void saveRate(supplier)}
                      onSaveStatus={() => void saveStatus(supplier)}
                      onCancelRate={() => updateDraft(supplier.id, supplier, { editingRate: false, rate: String(supplier.rate_per_shipment) })}
                      onCancelStatus={() => updateDraft(supplier.id, supplier, { editingStatus: false, status: supplier.status })}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 grid gap-3 md:hidden">
              {suppliers.map((supplier) => (
                <SupplierCard
                  key={supplier.id}
                  supplier={supplier}
                  draft={draftFor(supplier, drafts[supplier.id])}
                  saving={Boolean(savingById[supplier.id])}
                  error={errorById[supplier.id]}
                  notice={noticeById[supplier.id]}
                  onDraft={(patch) => updateDraft(supplier.id, supplier, patch)}
                  onSaveRate={() => void saveRate(supplier)}
                  onSaveStatus={() => void saveStatus(supplier)}
                  onCancelRate={() => updateDraft(supplier.id, supplier, { editingRate: false, rate: String(supplier.rate_per_shipment) })}
                  onCancelStatus={() => updateDraft(supplier.id, supplier, { editingStatus: false, status: supplier.status })}
                />
              ))}
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}

interface RowProps {
  supplier: Supplier;
  draft: Draft;
  saving: boolean;
  error?: string | null;
  notice?: string | null;
  onDraft: (patch: Partial<Draft>) => void;
  onSaveRate: () => void;
  onSaveStatus: () => void;
  onCancelRate: () => void;
  onCancelStatus: () => void;
}

function StatusBadge({ status }: { status: Status }) {
  const tone = status === "active" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{status}</span>;
}

function RateEditor({ supplier, draft, saving, onDraft, onSaveRate, onCancelRate }: RowProps) {
  if (!draft.editingRate) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span>{supplier.rate_per_shipment} {supplier.currency}</span>
        <button type="button" className="rounded-full border border-line px-3 py-1 text-xs" disabled={saving} onClick={() => onDraft({ editingRate: true, rate: String(supplier.rate_per_shipment) })}>
          Edit rate
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        aria-label={`Rate for ${supplier.name}`}
        className="w-28 rounded-lg border border-line bg-white px-2 py-1"
        value={draft.rate}
        disabled={saving}
        onChange={(event) => onDraft({ rate: event.target.value })}
      />
      <span className="text-xs text-slate-500">{supplier.currency}</span>
      <button type="button" className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-white disabled:opacity-60" disabled={saving} onClick={onSaveRate}>
        {saving ? "Saving…" : "Save"}
      </button>
      <button type="button" className="rounded-full border border-line px-3 py-1 text-xs disabled:opacity-60" disabled={saving} onClick={onCancelRate}>
        Cancel
      </button>
    </div>
  );
}

function StatusEditor({ supplier, draft, saving, onDraft, onSaveStatus, onCancelStatus }: RowProps) {
  if (!draft.editingStatus) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={supplier.status} />
        <button type="button" className="rounded-full border border-line px-3 py-1 text-xs" disabled={saving} onClick={() => onDraft({ editingStatus: true, status: supplier.status })}>
          Edit status
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select aria-label={`Status for ${supplier.name}`} className="rounded-lg border border-line bg-white px-2 py-1" value={draft.status} disabled={saving} onChange={(event) => onDraft({ status: event.target.value as Status })}>
        <option value="active">active</option>
        <option value="suspended">suspended</option>
      </select>
      <button type="button" className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-white disabled:opacity-60" disabled={saving} onClick={onSaveStatus}>
        {saving ? "Saving…" : "Save"}
      </button>
      <button type="button" className="rounded-full border border-line px-3 py-1 text-xs disabled:opacity-60" disabled={saving} onClick={onCancelStatus}>
        Cancel
      </button>
    </div>
  );
}

function RowFeedback({ error, notice }: { error?: string | null; notice?: string | null }) {
  if (error) return <p className="mt-2 text-xs text-red-700">{error}</p>;
  if (notice) return <p className="mt-2 text-xs text-emerald-700">{notice}</p>;
  return null;
}

function SupplierTableRow(props: RowProps) {
  const { supplier, saving } = props;
  return (
    <tr className="border-b border-line align-top" aria-busy={saving}>
      <td className="py-3 pr-3">
        <p className="font-semibold">{supplier.name}</p>
        {supplier.service_zone ? <p className="text-xs text-slate-500">{supplier.service_zone}</p> : null}
        <RowFeedback error={props.error} notice={props.notice} />
      </td>
      <td className="py-3 pr-3">{supplier.country}</td>
      <td className="py-3 pr-3">{supplier.categories.map(categoryLabel).join(", ")}</td>
      <td className="py-3 pr-3"><RateEditor {...props} /></td>
      <td className="py-3 pr-3"><StatusEditor {...props} /></td>
      <td className="py-3"><time dateTime={supplier.updated_at}>{supplier.updated_at}</time></td>
    </tr>
  );
}

function SupplierCard(props: RowProps) {
  const { supplier, saving } = props;
  return (
    <article className="rounded-xl border border-line p-4" aria-busy={saving}>
      <p className="font-semibold">{supplier.name}</p>
      <p className="text-sm text-slate-600">{supplier.country}{supplier.service_zone ? ` · ${supplier.service_zone}` : ""}</p>
      <p className="mt-2 text-sm">{supplier.categories.map(categoryLabel).join(", ")}</p>
      <div className="mt-3"><RateEditor {...props} /></div>
      <div className="mt-3"><StatusEditor {...props} /></div>
      <p className="mt-3 text-xs text-slate-500">Last rate update <time dateTime={supplier.updated_at}>{supplier.updated_at}</time></p>
      <RowFeedback error={props.error} notice={props.notice} />
    </article>
  );
}
