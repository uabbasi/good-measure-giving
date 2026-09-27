/**
 * Worker entry point:
 * 1. Proxies /__/auth/* to Firebase (same-origin auth for Safari)
 * 2. Serves static assets (prerendered pages included), falling back to the
 *    SPA shell only for routes that have no prerendered page
 *
 * wrangler not_found_handling must be "none" so the assets layer doesn't
 * intercept /__/auth/* navigation requests before the Worker runs.
 */

interface Env {
  ASSETS: { fetch: (request: Request) => Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Proxy Firebase auth handler requests
    if (url.pathname.startsWith('/__/auth/')) {
      const firebaseUrl = `https://good-measure-giving.firebaseapp.com${url.pathname}${url.search}`;
      const headers = new Headers(request.headers);
      headers.delete('host');

      const response = await fetch(firebaseUrl, {
        method: request.method,
        headers,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
        redirect: 'manual',
      });

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    }

    // Retired display previews share the normal page URL. Keep functional
    // parameters (filters, comparison EINs, attribution) and auth/files intact.
    const hasExtension = /\.\w{1,10}$/.test(url.pathname);
    if (!hasExtension && (request.method === 'GET' || request.method === 'HEAD')
      && (url.searchParams.has('view') || url.searchParams.has('type'))) {
      url.searchParams.delete('view');
      url.searchParams.delete('type');
      return Response.redirect(url.href, 301);
    }

    // Always try the real asset first. The assets layer resolves /foo/ to
    // /foo/index.html, which is how the ~196 prerendered pages get served —
    // rewriting to / before this point would hand every one of them the
    // homepage instead, silently discarding the SSG output.
    const assetResponse = await env.ASSETS.fetch(request);

    // A path with a file extension is a real file request. If it is missing it
    // should 404 as itself rather than fall back to an HTML shell.
    if (assetResponse.status !== 404 || hasExtension) {
      return assetResponse;
    }

    // Only known client-only routes get a successful SPA fallback.
    let clientRoute = /^\/(?:profile|compare|bookmarks)\/?$/.test(url.pathname)
      || /^\/plan\/join\/[^/]+\/[^/]+\/?$/.test(url.pathname);
    // Unlisted charities and planned prompts intentionally have no static page.
    // Preserve their links only when the underlying record actually exists.
    const charity = url.pathname.match(/^\/charity\/(\d{2}-\d{7})\/?$/);
    const prompt = url.pathname.match(/^\/prompts\/([\w-]+)\/?$/);
    const dataPath = charity ? `/data/charities/charity-${charity[1]}.json`
      : prompt ? `/data/prompts/${prompt[1]}.json` : null;
    if (dataPath) clientRoute = (await env.ASSETS.fetch(new Request(new URL(dataPath, url)))).ok;
    const fallback = await env.ASSETS.fetch(new Request(new URL(clientRoute ? '/' : '/404.html', url), request));
    return clientRoute ? fallback : new Response(fallback.body, {
      status: 404,
      headers: fallback.headers,
    });
  },
};
