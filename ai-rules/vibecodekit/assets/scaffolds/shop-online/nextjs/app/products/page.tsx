const PRODUCTS = [
  { id: "1", name: "Coffee beans", price: "120,000đ" },
  { id: "2", name: "Cold brew kit", price: "350,000đ" },
  { id: "3", name: "Espresso cup", price: "85,000đ" },
];

export default function ProductsPage() {
  return (
    <main className="px-6 py-12 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold">Products</h1>
      <ul className="mt-8 grid gap-6 sm:grid-cols-3">
        {PRODUCTS.map((p) => (
          <li key={p.id} className="rounded-lg border p-6">
            <h2 className="font-semibold">{p.name}</h2>
            <p className="mt-1 text-slate-600">{p.price}</p>
            <button className="mt-3 rounded bg-slate-900 px-4 py-2 text-white text-sm">
              Add to cart
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
