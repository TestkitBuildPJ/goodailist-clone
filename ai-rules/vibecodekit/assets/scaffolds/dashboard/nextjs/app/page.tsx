const KPIS = [
  { label: "Revenue", value: "120M đ", delta: "+12%" },
  { label: "Active users", value: "3,402", delta: "+8%" },
  { label: "Orders", value: "881", delta: "-3%" },
];

export default function Dashboard() {
  return (
    <main className="p-12 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <ul className="mt-8 grid gap-6 sm:grid-cols-3">
        {KPIS.map((k) => (
          <li key={k.label} className="rounded-lg border p-6">
            <p className="text-sm text-slate-500">{k.label}</p>
            <p className="mt-1 text-3xl font-bold">{k.value}</p>
            <p className="mt-1 text-sm text-emerald-600">{k.delta}</p>
          </li>
        ))}
      </ul>
      <div className="mt-12 rounded-lg border p-6">
        <h2 className="font-semibold mb-4">Trend</h2>
        <p className="text-sm text-slate-500">
          Wire <code>recharts</code>&apos; AreaChart here once data is available.
        </p>
      </div>
    </main>
  );
}
