const CONTACTS = [
  { id: "1", name: "Nguyễn Văn A", email: "a@example.com" },
  { id: "2", name: "Trần Thị B", email: "b@example.com" },
];
export default function ContactsPage() {
  return (
    <main className="p-12 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Contacts</h1>
      <table className="w-full border-collapse">
        <thead><tr><th className="text-left">Name</th><th className="text-left">Email</th></tr></thead>
        <tbody>
          {CONTACTS.map((c) => (
            <tr key={c.id} className="border-t"><td>{c.name}</td><td>{c.email}</td></tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
