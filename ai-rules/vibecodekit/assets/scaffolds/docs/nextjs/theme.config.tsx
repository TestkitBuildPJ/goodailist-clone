import type { DocsThemeConfig } from "nextra-theme-docs";

const config: DocsThemeConfig = {
  logo: <span style={{ fontWeight: 600 }}>VibeCode Docs</span>,
  project: { link: "https://github.com/your-org/your-docs" },
  docsRepositoryBase: "https://github.com/your-org/your-docs/tree/main",
  footer: {
    content: <span>© {new Date().getFullYear()} VibeCode Docs.</span>
  },
  search: { placeholder: "Tìm tài liệu…" },
  i18n: [
    { locale: "vi", name: "Tiếng Việt" },
    { locale: "en", name: "English" }
  ]
};

export default config;
