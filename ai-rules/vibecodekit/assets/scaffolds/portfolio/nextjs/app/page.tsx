import Hero from "@/components/Hero";
import Work from "@/components/Work";
import Contact from "@/components/Contact";

export default function Page() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-24 space-y-32">
      <Hero />
      <Work />
      <Contact />
    </main>
  );
}
