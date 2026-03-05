/**
 * Worker entry point:
 * 1. Proxies /__/auth/* to Firebase (same-origin auth for Safari)
 * 2. Serves static assets, with SPA fallback to /
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

    // Check if the path looks like a static asset (has a file extension)
    const hasExtension = /\.\w{1,10}$/.test(url.pathname);

    if (hasExtension) {
      // Real file request — serve directly from assets
      return env.ASSETS.fetch(request);
    }

    // SPA route — rewrite to / before hitting assets, so it always returns index.html
    const spaRequest = new Request(new URL('/', url), request);
    return env.ASSETS.fetch(spaRequest);
  },
};
