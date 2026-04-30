import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * Minimal NextAuth options — replace `CredentialsProvider` with a real
 * provider (Email, Google, GitHub, …) once you have the credentials in
 * `.env`.  See https://next-auth.js.org/configuration/providers for the
 * full list.
 */
export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
      },
      // TODO: wire to your DB; this stub returns a fixed user so the
      // template runs out-of-the-box without a database.
      async authorize(credentials) {
        if (!credentials?.email) return null;
        return { id: "stub-user", email: credentials.email };
      },
    }),
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/auth/login" },
};
