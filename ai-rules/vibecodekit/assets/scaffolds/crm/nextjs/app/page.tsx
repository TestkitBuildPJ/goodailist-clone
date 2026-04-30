import Link from "next/link";
export default function Home() {
  return (
    <main className="p-12">
      <h1 className="text-3xl font-bold">VibecodeKit CRM</h1>
      <Link href="/contacts" className="mt-4 inline-block underline">
        View contacts
      </Link>
    </main>
  );
}
