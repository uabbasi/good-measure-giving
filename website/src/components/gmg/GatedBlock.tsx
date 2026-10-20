// Motif-native wrapper around CommunityGate. The shared JoinCommunityPrompt is
// Tailwind-styled and would read as a different site inside this page.
//
// A fallback is always supplied: CommunityGate with none renders nothing, which
// would leave a signed-out visitor staring at a hole with no clue that anything
// exists there.

import React from 'react';
import { CommunityGate } from '../../auth/CommunityGate';
import { SignInButton } from '../../auth/SignInButton';
import { GmgPalette, FONT_MONO } from './tokens';

export const GatedBlock: React.FC<{
  label: string;
  p: GmgPalette;
  children: React.ReactNode;
}> = ({ label, p, children }) => (
  <CommunityGate
    fallback={
      // One quiet line, not a boxed prompt with its own button: a charity page has
      // about ten of these, and the closing sign-in panel is the one real ask.
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: '4px 14px',
          padding: '10px 0',
          borderTop: `1px solid ${p.rule}`,
          borderBottom: `1px solid ${p.rule}`,
        }}
      >
        <span
          style={{
            fontFamily: FONT_MONO,
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: p.sub,
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 13, color: p.sub }}>Sign in to see this — it's free.</span>
        <span style={{ display: 'inline-block', fontSize: 13, color: p.accent }}>
          <SignInButton variant="custom" className="cursor-pointer font-medium underline underline-offset-4 decoration-1">
            Sign in
          </SignInButton>
        </span>
      </div>
    }
  >
    {children}
  </CommunityGate>
);

export default GatedBlock;
