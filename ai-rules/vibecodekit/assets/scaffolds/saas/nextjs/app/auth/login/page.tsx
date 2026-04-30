"use client";

import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    // TODO: wire to NextAuth signIn("email", { email }) once provider is set.
    setSubmitted(true);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 space-y-6">
      <h1 className="text-3xl font-semibold">Đăng nhập</h1>
      {submitted ? (
        <p className="rounded-lg bg-emerald-50 px-4 py-3 text-emerald-700">
          Đã gửi link đăng nhập tới <strong>{email}</strong>.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-500"
              placeholder="ban@example.com"
            />
          </label>
          <button
            type="submit"
            className="w-full rounded-lg bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
          >
            Gửi link đăng nhập
          </button>
        </form>
      )}
    </main>
  );
}
