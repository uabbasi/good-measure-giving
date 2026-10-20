import React from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { Link } from 'react-router-dom';
import { GmgContentFrame, ContentHero, Em, CtaLink } from '../src/components/gmg/content';

export const NotFoundPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  return (
    <GmgContentFrame isDark={isDark}>
      {(ctx) => (
        <>
          <ContentHero
            ctx={ctx}
            title={<>Page <Em p={ctx.p}>not found.</Em></>}
            lead="The page you're looking for doesn't exist or may have moved."
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 24 }}>
            <CtaLink p={ctx.p} to="/browse/">Browse charities</CtaLink>
            <Link to="/" className="tap-link" style={{ color: ctx.p.accent, textDecoration: 'none', fontWeight: 500 }}>Go home</Link>
          </div>
        </>
      )}
    </GmgContentFrame>
  );
};
