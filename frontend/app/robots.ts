import type { MetadataRoute } from 'next';

const BASE = 'https://mailmind.radiantsofficial.com';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // Keep the authenticated app + private surfaces out of the index.
        disallow: ['/dashboard', '/admin', '/api/'],
      },
    ],
    sitemap: `${BASE}/sitemap.xml`,
    host: BASE,
  };
}
