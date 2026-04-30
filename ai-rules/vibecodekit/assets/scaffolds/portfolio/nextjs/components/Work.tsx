"use client";

import { motion } from "framer-motion";

const projects = [
  {
    title: "Dự án A",
    description: "Mô tả ngắn gọn về dự án — vai trò, công nghệ, kết quả.",
    href: "https://example.com/a",
  },
  {
    title: "Dự án B",
    description: "Mô tả ngắn gọn về dự án — vai trò, công nghệ, kết quả.",
    href: "https://example.com/b",
  },
  {
    title: "Dự án C",
    description: "Mô tả ngắn gọn về dự án — vai trò, công nghệ, kết quả.",
    href: "https://example.com/c",
  },
];

export default function Work() {
  return (
    <section className="space-y-8" id="work">
      <h2 className="text-3xl font-semibold">Công việc gần đây</h2>
      <ul className="grid gap-6 md:grid-cols-3">
        {projects.map((p, i) => (
          <motion.li
            key={p.title}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
            className="rounded-2xl border border-slate-200 p-6 hover:border-red-400"
          >
            <a href={p.href} className="block space-y-2">
              <h3 className="text-xl font-semibold">{p.title}</h3>
              <p className="text-sm text-slate-600">{p.description}</p>
            </a>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}
