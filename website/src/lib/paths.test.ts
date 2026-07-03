import { describe, it, expect } from 'vitest';
import {
  charityPath,
  causePath,
  guidePath,
  promptPath,
  zakatCalculatorPath,
  paths,
  isPath,
} from './paths';

describe('internal path builders', () => {
  it('build trailing-slash detail paths', () => {
    expect(charityPath('41-2046295')).toBe('/charity/41-2046295/');
    expect(causePath('humanitarian')).toBe('/causes/humanitarian/');
    expect(guidePath('what-makes-a-charity-zakat-eligible')).toBe(
      '/guides/what-makes-a-charity-zakat-eligible/',
    );
    expect(promptPath('score_judge')).toBe('/prompts/score_judge/');
    expect(zakatCalculatorPath('stocks')).toBe('/zakat-calculator/stocks/');
  });

  it('static content routes all end in a trailing slash', () => {
    for (const p of Object.values(paths)) {
      expect(p.endsWith('/')).toBe(true);
    }
  });

  it('isPath matches regardless of trailing slash', () => {
    expect(isPath('/browse/', '/browse')).toBe(true);
    expect(isPath('/browse', '/browse')).toBe(true);
    expect(isPath('/browse/', paths.browse)).toBe(true);
    expect(isPath('/', '/')).toBe(true);
    expect(isPath('/browse/', '/profile')).toBe(false);
    expect(isPath('/profile/', '/profile/')).toBe(true);
  });
});
