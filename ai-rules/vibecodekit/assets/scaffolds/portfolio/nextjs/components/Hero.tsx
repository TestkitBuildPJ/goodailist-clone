"use client";

import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section className="space-y-6">
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-5xl font-bold tracking-tight md:text-7xl"
      >
        Xin chào — tôi là <span className="text-red-500">Tên Bạn</span>.
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="max-w-xl text-lg text-slate-600"
      >
        Tôi xây sản phẩm web bằng React, Next.js và Tailwind. Trang này được
        scaffold bằng VibecodeKit.
      </motion.p>
    </section>
  );
}
