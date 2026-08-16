// The assessment-label and evidence-stage tags ("Limited Basis", "High
// Conviction", "Verified", etc.) reached the page as bare internal-rubric
// jargon with zero explanation anywhere on the site — found in manual QA
// ("what does 'Limited Basis' mean?"). Now wired to native title tooltips.
// This pins that every real corpus value has a matching explainer — a typo
// or a new pipeline-added label would otherwise render title="undefined"
// silently, one lookup miss at a time.

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { MemoryRouter } from 'react-router-dom';
import { GmgCharityDetail, ASSESSMENT_LABEL_EXPLAINERS, EVIDENCE_STAGE_EXPLAINERS } from './GmgCharityDetail';
import { adaptCharity } from './charityAdapter';

vi.mock('../../auth/useAuth', () => ({ useCommunityMember: () => false }));
vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const dir = path.resolve(__dirname, '../../../data/charities');
const load = (ein: string) => JSON.parse(fs.readFileSync(path.join(dir, `charity-${ein}.json`), 'utf8'));

describe('GmgCharityDetail — assessment/evidence tag tooltips', () => {
  it('gives the "Limited Basis" tag a real explanation, not an empty title', () => {
    const raw = load('85-3964369'); // Al-Barr Foundation — evaluationTrack NEW_ORG forces Limited Basis
    const { getByText } = render(
      <MemoryRouter>
        <GmgCharityDetail charity={raw} isDark={false} />
      </MemoryRouter>,
    );
    const tag = getByText('Limited Basis');
    const title = tag.closest('span')?.getAttribute('title');
    expect(title).toBeTruthy();
    expect(title).toMatch(/not enough evidence/i);
  });

  it('every assessment_label and evidence_stage value in the corpus has a matching explainer', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    expect(files.length).toBeGreaterThan(100);

    const missing: string[] = [];
    for (const file of files) {
      const c = adaptCharity(load(file.replace(/^charity-/, '').replace(/\.json$/, '')));
      if (c.assessmentLabel && !(c.assessmentLabel in ASSESSMENT_LABEL_EXPLAINERS)) {
        missing.push(`${file}: assessment_label "${c.assessmentLabel}"`);
      }
      if (c.evidenceStage && !(c.evidenceStage in EVIDENCE_STAGE_EXPLAINERS)) {
        missing.push(`${file}: evidence_stage "${c.evidenceStage}"`);
      }
    }
    expect(missing).toEqual([]);
  });
});
