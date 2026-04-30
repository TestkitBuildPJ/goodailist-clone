const POSTS = [
  { slug: "hello", title: "Hello, world", date: "2026-04-26" },
  { slug: "vibecodekit-v011", title: "VibecodeKit v0.11.0 is out", date: "2026-05-01" },
];
export default function PostsPage() {
  return (
    <main className="p-12 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold">Posts</h1>
      <ul className="mt-8 space-y-4">
        {POSTS.map((p) => (
          <li key={p.slug}>
            <h2 className="font-semibold">{p.title}</h2>
            <p className="text-sm text-slate-500">{p.date}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
