"use client";

export default function Contact() {
  return (
    <section className="space-y-6" id="contact">
      <h2 className="text-3xl font-semibold">Liên hệ</h2>
      <p className="text-slate-600">
        Email:{" "}
        <a
          href="mailto:hello@example.com"
          className="font-medium text-red-500 hover:underline"
        >
          hello@example.com
        </a>
      </p>
      <p className="text-slate-600">
        GitHub:{" "}
        <a
          href="https://github.com/your-handle"
          className="font-medium text-red-500 hover:underline"
        >
          @your-handle
        </a>
      </p>
    </section>
  );
}
