import Link from "next/link";

export default function Home() {
  return (
    <main className="px-6 py-24 max-w-3xl mx-auto text-center">
      <h1 className="text-4xl font-bold">Welcome to the shop</h1>
      <p className="mt-4 text-slate-600">Browse products to begin.</p>
      <Link href="/products" className="mt-8 inline-block rounded bg-slate-900 px-6 py-3 text-white">
        Browse products
      </Link>
    </main>
  );
}
