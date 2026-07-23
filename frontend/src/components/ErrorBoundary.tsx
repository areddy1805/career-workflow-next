import React, { ErrorInfo } from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from './ui/button';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class GlobalErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="h-full w-full flex items-center justify-center p-8">
          <div className="max-w-md w-full border border-destructive/20 bg-destructive/5 p-6 rounded-lg space-y-4">
            <div className="flex items-center space-x-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <h2 className="text-lg font-semibold tracking-tight">Application Error</h2>
            </div>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap font-mono">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Reload Application
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
