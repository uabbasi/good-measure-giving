import React, { Component, ReactNode } from 'react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorFallbackProps {
  error: Error | null;
}

/**
 * Theme-aware error fallback component.
 * Uses the landing theme context to render appropriately in dark/light mode.
 */
const ErrorFallback: React.FC<ErrorFallbackProps> = ({ error }) => {
  const { isDark } = useLandingTheme();

  return (
    <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? 'bg-slate-950' : 'bg-gray-50'}`}>
      <div className={`max-w-md w-full shadow-lg rounded-lg p-6 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white'}`}>
        <div className="flex items-center mb-4">
          <svg
            className={`h-6 w-6 mr-2 ${isDark ? 'text-red-400' : 'text-red-600'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Something went wrong
          </h2>
        </div>
        <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
          An unexpected error occurred. Please try refreshing the page.
        </p>
        {error && (
          <details className="mb-4">
            <summary className={`text-sm cursor-pointer ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-gray-500 hover:text-gray-700'}`}>
              Error details
            </summary>
            <pre className={`mt-2 text-xs p-2 rounded overflow-auto max-h-40 ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-gray-100 text-gray-900'}`}>
              {error.toString()}
            </pre>
          </details>
        )}
        <button
          onClick={() => window.location.reload()}
          className="w-full py-2 px-4 rounded transition-colors bg-emerald-700 text-white hover:bg-emerald-600"
        >
          Reload Page
        </button>
      </div>
    </div>
  );
};

/**
 * Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing
 * the entire application.
 *
 * Usage:
 * <ErrorBoundary fallback={<div>Something went wrong</div>}>
 *   <YourComponent />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error to console
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // Render custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Use theme-aware default fallback
      return <ErrorFallback error={this.state.error} />;
    }

    return this.props.children;
  }
}
