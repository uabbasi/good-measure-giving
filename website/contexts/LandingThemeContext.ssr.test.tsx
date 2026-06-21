// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { LandingThemeProvider } from './LandingThemeContext';
import React from 'react';

test('LandingThemeProvider renders server-side without touching localStorage', () => {
  expect(() =>
    renderToStaticMarkup(
      React.createElement(LandingThemeProvider, null, React.createElement('div'))
    )
  ).not.toThrow();
});
