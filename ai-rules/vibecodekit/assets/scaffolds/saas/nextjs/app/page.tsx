import Link from "next/link";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-24 space-y-6">
      <h1 className="text-5xl font-bold tracking-tight">
        Ship your SaaS faster
      </h1>
      <p className="text-lg text-slate-600">
        Next.js + NextAuth + Prisma starter — scaffolded by VibecodeKit
        (preset: saas).
      </p>
      <div className="flex gap-4">
        <Link
          href="/auth/login"
          className="rounded-lg bg-slate-900 px-5 py-3 text-white hover:bg-slate-700"
        >
          Đăng nhập
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-slate-300 px-5 py-3 hover:border-slate-500"
        >
          Vào dashboard
        </Link>
      </div>
    </main>
  );
}
