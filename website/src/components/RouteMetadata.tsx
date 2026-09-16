import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { trackPageView } from '../utils/analytics';

type PageMeta = { title: string; description: string; canonical: string; ogType: string; noindex?: boolean; jsonLd?: object | object[] };

export function RouteMetadata() {
  const { pathname } = useLocation();
  const route = pathname.replace(/\/+$/, '') || '/';
  const { data } = useQuery<Record<string, PageMeta>>({
    queryKey: ['page-metadata'],
    queryFn: async () => {
      const response = await fetch('/page-meta.json');
      if (!response.ok) throw new Error('Could not load page metadata');
      return response.json();
    },
    staleTime: Infinity,
    enabled: typeof window !== 'undefined',
  });
  useEffect(() => {
    const canonical = `https://goodmeasuregiving.org${route === '/' ? '/' : `${route}/`}`;
    // Keep server-rendered metadata while its matching manifest is loading.
    if (!data && document.querySelector('link[rel="canonical"]')?.getAttribute('href') === canonical) return;
    const isInvite = /^\/plan\/join\/[^/]+\/[^/]+$/.test(route);
    const meta: PageMeta = data?.[route] ?? {
      title: isInvite ? 'Join a Giving Plan | Good Measure Giving' : data ? 'Page Not Found | Good Measure Giving' : 'Good Measure Giving | Muslim Charity Evaluator',
      description: isInvite ? 'Accept an invitation to a shared giving plan.' : data ? 'The requested page could not be found. Browse our charity evaluations instead.' : 'Independent research to help you choose a charity and give well.',
      canonical, ogType: 'website', noindex: true,
    };
    document.title = meta.title;
    const setMeta = (attr: 'name' | 'property', key: string, content: string) => {
      // Preserve filtered-browse robots directive (noindex,follow) set by GmgBrowse.
      if (attr === 'name' && key === 'robots') {
        const facetTag = document.head.querySelector<HTMLMetaElement>(
          'meta[name="robots"][data-gmg-facets]'
        );
        const facetNoindex = facetTag?.getAttribute('content')?.includes('noindex');
        if (!content.includes('noindex') && facetNoindex) {
          // Do not override an active filtered-browse directive.
          return;
        }
        let node = document.head.querySelector<HTMLMetaElement>(
          'meta[name="robots"]:not([data-gmg-facets])'
        );
        if (!node) {
          node = document.createElement('meta');
          node.setAttribute('name', 'robots');
          document.head.appendChild(node);
        }
        node.content = content;
        return;
      }
      let node = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
      if (!node) { node = document.createElement('meta'); node.setAttribute(attr, key); document.head.appendChild(node); }
      node.content = content;
    };
    setMeta('name', 'description', meta.description);
    setMeta('name', 'robots', meta.noindex ? 'noindex,nofollow' : 'index,follow');
    const url = meta.canonical.replace(/\/+$/, '') + '/';
    let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) { link = document.createElement('link'); link.rel = 'canonical'; document.head.appendChild(link); }
    link.href = url;
    for (const [key, value] of Object.entries({ title: meta.title, description: meta.description, url, type: meta.ogType, image: 'https://goodmeasuregiving.org/og-share.jpg' })) setMeta('property', `og:${key}`, value);
    document.head.querySelectorAll('script[type="application/ld+json"]').forEach(node => node.remove());
    for (const block of meta.jsonLd ? (Array.isArray(meta.jsonLd) ? meta.jsonLd : [meta.jsonLd]) : []) {
      const script = document.createElement('script'); script.type = 'application/ld+json'; script.textContent = JSON.stringify(block); document.head.appendChild(script);
    }
    if (data) trackPageView(route, meta.title);
  }, [route, data]);
  return null;
}
