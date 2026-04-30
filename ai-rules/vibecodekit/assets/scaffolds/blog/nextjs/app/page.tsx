import Link from "next/link";
export default function Home() {
  return (
    <main className="p-12 max-w-2xl mx-auto">
      <h1 className="text-4xl font-bold">VibecodeKit Blog</h1>
      <p className="mt-4 text-slate-600">Latest writing.</p>
      <Link href="/posts" className="mt-6 underline inline-block">All posts →</Link>
    </main>
  );
}
