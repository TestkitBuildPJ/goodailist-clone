export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12 space-y-8">
      <header>
        <h1 className="text-3xl font-semibold">Dashboard</h1>
        <p className="text-slate-600">Tổng quan hoạt động của bạn.</p>
      </header>
      <section className="grid gap-4 md:grid-cols-3">
        {["Người dùng", "Doanh thu (₫)", "Phiên 24h"].map((label) => (
          <div
            key={label}
            className="rounded-2xl border border-slate-200 bg-white p-6"
          >
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-semibold">—</p>
          </div>
        ))}
      </section>
    </main>
  );
}
