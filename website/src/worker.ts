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

    // Always try the real asset first. The assets layer resolves /foo/ to
    // /foo/index.html, which is how the ~196 prerendered pages get served —
    // rewriting to / before this point would hand every one of them the
    // homepage instead, silently discarding the SSG output.
    const assetResponse = await env.ASSETS.fetch(request);

    // A path with a file extension is a real file request. If it is missing it
    // should 404 as itself rather than fall back to an HTML shell.
    const hasExtension = /\.\w{1,10}$/.test(url.pathname);

    if (assetResponse.status !== 404 || hasExtension) {
      return assetResponse;
    }

    // Extensionless miss — a client-only route. Serve the SPA shell so the
    // router can render it (including the 404 route).
    const spaRequest = new Request(new URL('/', url), request);
    return env.ASSETS.fetch(spaRequest);
  },
};
