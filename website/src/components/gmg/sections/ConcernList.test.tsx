/**
 * ConcernList — shared across all six donor-question sections. Concern
 * detail text is running prose and, before the page-wide measure-cap fix,
 * ran the full section width (~180 characters per line on a wide screen).
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ConcernList } from './ConcernList';
import { gmgPalette } from '../tokens';
import type { Concern } from '../adapters/concerns';

const p = gmgPalette(false);

const concerns: Concern[] = [
  {
    type: 'data_quality',
    anchor: 'whatTheyDo',
    severity: 'medium',
    headline: 'Some caveat',
    detail: 'A long explanation of the caveat that would otherwise run the full width of a wide viewport.',
    dataPoints: {},
  },
];

describe('ConcernList', () => {
  it('renders nothing for an empty list', () => {
    const { container } = render(<ConcernList concerns={[]} p={p} />);
    expect(container.firstChild).toBeNull();
  });

  it('caps concern detail text to a readable measure', () => {
    const { getByText } = render(<ConcernList concerns={concerns} p={p} />);
    const detail = getByText(concerns[0].detail);
    expect(detail.style.maxWidth).toBe('75ch');
  });
});
