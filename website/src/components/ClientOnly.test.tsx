// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { ClientOnly } from './ClientOnly';

test('renders nothing during server render', () => {
  const html = renderToStaticMarkup(<ClientOnly><span>hi</span></ClientOnly>);
  expect(html).toBe('');
});
