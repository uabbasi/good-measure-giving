/**
 * Proxy /__/auth/* to Firebase's auth handler on our own domain.
 * This makes signInWithPopup/signInWithRedirect same-origin,
 * fixing Safari's third-party storage blocking.
 */

// Cloudflare Pages Function types
type PagesFunction = (context: { request: Request }) => Promise<Response>;

export const onRequest: PagesFunction = async ({ request }) => {
  const url = new URL(request.url);
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
};
