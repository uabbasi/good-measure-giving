/**
 * ActionsBar - Horizontal row of charity action buttons
 * Actions: Log Donation, Save, Donate
 * (Share and Report Issue are in the bottom metadata bar of each view)
 */

import React from 'react';
import { Plus, ExternalLink, Shield, LogIn } from 'lucide-react';
import { BookmarkButton } from './BookmarkButton';
import { CompareButton } from './CompareButton';
import { useAuth, SignInButton } from '../auth';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface ActionsBarProps {
  charityEin: string;
  charityName: string;
  onLogDonation?: () => void;
  /** Styling variant: 'default' has border/background, 'terminal' is Bloomberg-style */
  variant?: 'default' | 'terminal';
  /** Optional donate URL for terminal variant */
  donateUrl?: string;
  /** Optional callback when donate is clicked */
  onDonateClick?: () => void;
  /** Wallet tag: 'ZAKAT-ELIGIBLE' or 'SADAQAH-ELIGIBLE' */
  walletTag?: string | null;
  /** Cause area (e.g. 'RELIGIOUS_CULTURAL') */
  causeArea?: string | null;
}

function formatCauseArea(raw: string): string {
  return raw.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()).replace(/\bAnd\b/g, '&');
}

export function ActionsBar({ charityEin, charityName, onLogDonation, variant = 'default', donateUrl, onDonateClick, walletTag, causeArea }: ActionsBarProps) {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();

  // Terminal variant: Bloomberg-style compact bar
  if (variant === 'terminal') {
    const terminalBtn = `inline-flex items-center gap-1.5 px-2 py-1 text-xs font-mono uppercase tracking-wide transition-colors ${
      isDark
        ? 'text-slate-500 hover:text-amber-400'
        : 'text-slate-400 hover:text-amber-600'
    }`;

    return (
      <div className={`border-b ${isDark ? 'border-slate-800/50 bg-slate-950' : 'border-slate-200 bg-slate-100'}`}>
        {/* Mobile quick actions */}
        <div className={`sm:hidden sticky top-16 z-30 border-b ${isDark ? 'border-slate-800 bg-slate-950/95' : 'border-slate-200 bg-white/95'} backdrop-blur`}>
          <div className="px-3 py-2.5">
            <div className="flex items-center gap-2">
              {isSignedIn ? (
                <>
                  {onLogDonation && (
                    <button
                      onClick={onLogDonation}
                      className={`flex-1 inline-flex items-center justify-center gap-2 px-3 py-2.5 min-h-[44px] rounded-lg text-sm font-semibold transition-colors ${
                        isDark
                          ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                      }`}
                    >
                      <Plus className="w-4 h-4" />
                      Log Donation
                    </button>
                  )}
                  <BookmarkButton
                    charityEin={charityEin}
                    charityName={charityName}
                    showLabel
                    fullWidth
                    size="md"
                    className="flex-1"
                  />
                </>
              ) : (
                <SignInButton variant="custom" isDark={isDark}>
                  <span className={`w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 min-h-[44px] rounded-lg text-sm font-semibold cursor-pointer ${
                    isDark
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}>
                    <LogIn className="w-4 h-4" />
                    Sign in to save & log
                  </span>
                </SignInButton>
              )}
              {donateUrl && (
                <a
                  href={donateUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={onDonateClick}
                  className={`inline-flex items-center justify-center gap-2 px-3 py-2.5 min-h-[44px] rounded-lg text-sm font-semibold whitespace-nowrap ${
                    isDark
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  }`}
                >
                  Donate
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        </div>

        <div className="hidden sm:block px-6">
          <div className="flex items-center justify-between py-2">
            {/* Cause Area + Wallet Tag (left side) */}
            <div className="flex items-center gap-2">
              {causeArea && (
                <span className={`text-xs font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {formatCauseArea(causeArea)}
                </span>
              )}
              {causeArea && walletTag && (
                <span className={isDark ? 'text-slate-700' : 'text-slate-300'}>·</span>
              )}
              {walletTag && (
                <>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-semibold uppercase tracking-wide ${
                    walletTag.includes('ZAKAT')
                      ? isDark ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-700/50' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : isDark ? 'bg-slate-800 text-slate-400 border border-slate-700' : 'bg-slate-100 text-slate-500 border border-slate-200'
                  }`}>
                    <Shield className="w-3 h-3" />
                    {walletTag.includes('ZAKAT') ? 'Zakat Eligible' : 'Sadaqah'}
                  </span>
                  {walletTag.includes('ZAKAT') && (
                    <span className="relative group/tooltip">
                      <span className={`text-xs cursor-help border-b border-dotted ${isDark ? 'text-slate-600 border-slate-600' : 'text-slate-400 border-slate-400'}`}>
                        stated policy
                      </span>
                      <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg shadow-lg w-56 text-center opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none">
                        Per organization's published zakat policy
                        <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900"></span>
                      </span>
                    </span>
                  )}
                </>
              )}
            </div>
            {/* Action buttons */}
            <div className="flex items-center gap-3">
              {isSignedIn ? (
                <>
                  {onLogDonation && (
                    <button onClick={onLogDonation} className={terminalBtn}>
                      <Plus className="w-3 h-3" aria-hidden="true" />
                      <span className={isDark ? 'text-emerald-500' : 'text-emerald-600'}>Log Donation</span>
                    </button>
                  )}
                  <span className={`${isDark ? 'text-slate-700' : 'text-slate-300'}`}>│</span>
                  <CompareButton
                    charityEin={charityEin}
                    charityName={charityName}
                    size="sm"
                    className="!text-xs !font-mono !uppercase !tracking-wide"
                  />
                  <span className={`${isDark ? 'text-slate-700' : 'text-slate-300'}`}>│</span>
                  <BookmarkButton
                    charityEin={charityEin}
                    charityName={charityName}
                    showLabel
                    size="sm"
                    className="!text-xs !font-mono !uppercase !tracking-wide"
                  />
                </>
              ) : (
                <SignInButton
                  variant="custom"
                  isDark={isDark}
                >
                  <span className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-mono uppercase tracking-wide cursor-pointer transition-colors ${
                    isDark ? 'text-emerald-500 hover:text-emerald-400' : 'text-emerald-600 hover:text-emerald-500'
                  }`}>
                    <LogIn className="w-3 h-3" aria-hidden="true" />
                    Sign in to log donations, compare & save
                  </span>
                </SignInButton>
              )}

              {donateUrl && (
                <>
                  <span className={`${isDark ? 'text-slate-700' : 'text-slate-300'}`}>│</span>
                  <a
                    href={donateUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={onDonateClick}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-mono uppercase tracking-wide rounded transition-colors ${
                      isDark
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                        : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    }`}
                  >
                    Donate
                    <ExternalLink className="w-3 h-3" aria-hidden="true" />
                  </a>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`border-b ${isDark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-200 bg-slate-50/50'}`}>
      {/* Mobile quick actions */}
      <div className={`sm:hidden sticky top-16 z-30 border-b ${isDark ? 'border-slate-800 bg-slate-900/95' : 'border-slate-200 bg-white/95'} backdrop-blur`}>
        <div className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            {isSignedIn ? (
              <>
                {onLogDonation && (
                  <button
                    onClick={onLogDonation}
                    className={`flex-1 inline-flex items-center justify-center gap-2 px-3 py-2.5 min-h-[44px] rounded-lg text-sm font-semibold transition-colors ${
                      isDark
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                    }`}
                  >
                    <Plus className="w-4 h-4" />
                    Log Donation
                  </button>
                )}
                <BookmarkButton
                  charityEin={charityEin}
                  charityName={charityName}
                  showLabel
                  fullWidth
                  size="md"
                  className="flex-1"
                />
              </>
            ) : (
              <SignInButton variant="custom" isDark={isDark}>
                <span className={`w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 min-h-[44px] rounded-lg text-sm font-semibold cursor-pointer ${
                  isDark
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}>
                  <LogIn className="w-4 h-4" />
                  Sign in to save & log
                </span>
              </SignInButton>
            )}
          </div>
        </div>
      </div>

      <div className="hidden sm:block max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-2.5">
          {/* Cause Area + Wallet Tag (left side) */}
          <div className="flex items-center gap-2">
            {causeArea && (
              <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {formatCauseArea(causeArea)}
              </span>
            )}
            {causeArea && walletTag && (
              <span className={isDark ? 'text-slate-700' : 'text-slate-300'}>·</span>
            )}
            {walletTag && (
              <>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-medium ${
                  walletTag.includes('ZAKAT')
                    ? isDark ? 'bg-emerald-900/40 text-emerald-400' : 'bg-emerald-50 text-emerald-700'
                    : isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'
                }`}>
                  <Shield className="w-3 h-3" />
                  {walletTag.includes('ZAKAT') ? 'Zakat Eligible' : 'Sadaqah'}
                </span>
                {walletTag.includes('ZAKAT') && (
                  <span className="relative group/tooltip">
                    <span className={`text-xs cursor-help border-b border-dotted ${isDark ? 'text-slate-600 border-slate-600' : 'text-slate-400 border-slate-400'}`}>
                      stated policy
                    </span>
                    <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg shadow-lg w-56 text-center opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none">
                      Per organization's published zakat policy
                      <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900"></span>
                    </span>
                  </span>
                )}
              </>
            )}
          </div>
          {/* Action buttons */}
          <div className="flex items-center gap-1">
            {isSignedIn ? (
              <>
                {onLogDonation && (
                  <button
                    onClick={onLogDonation}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      isDark
                        ? 'text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10'
                        : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50'
                    }`}
                  >
                    <Plus className="w-4 h-4" aria-hidden="true" />
                    Log Donation
                  </button>
                )}
                <CompareButton
                  charityEin={charityEin}
                  charityName={charityName}
                  size="sm"
                />
                <BookmarkButton
                  charityEin={charityEin}
                  charityName={charityName}
                  showLabel
                  size="sm"
                />
              </>
            ) : (
              <SignInButton
                variant="custom"
                isDark={isDark}
              >
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  isDark ? 'text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10' : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50'
                }`}>
                  <LogIn className="w-4 h-4" aria-hidden="true" />
                  Sign in to log donations, compare & save
                </span>
              </SignInButton>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
