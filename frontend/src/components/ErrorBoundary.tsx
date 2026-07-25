import React, { ErrorInfo } from 'react';
import { AlertTriangle, Terminal, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

export class GlobalErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error('Operations Center Exception:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="h-screen w-screen flex flex-col bg-[#0a0a0a] text-foreground p-6 sm:p-12 overflow-auto">
          <div className="flex-1 w-full max-w-4xl mx-auto flex flex-col justify-center">
            
            <div className="mb-6 flex items-center gap-3">
              <div className="w-10 h-10 rounded border border-red-500/30 bg-red-500/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-foreground">Critical Subsystem Failure</h1>
                <p className="text-[11px] text-muted-foreground font-mono uppercase tracking-widest mt-1">Application State Corrupted</p>
              </div>
            </div>

            <div className="border border-border rounded-md shadow-card bg-card overflow-hidden">
              <div className="px-5 py-3 border-b border-border bg-card/50 flex items-center gap-2">
                <Terminal className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">Stack Trace</span>
              </div>
              
              <div className="p-5 bg-background">
                <p className="text-sm font-semibold text-red-500 font-mono mb-4 break-words">
                  {this.state.error?.name}: {this.state.error?.message || 'Unknown Exception'}
                </p>
                <div className="bg-[#0a0a0a] border border-border/50 rounded-md p-4 overflow-auto max-h-[400px]">
                  <pre className="text-[11px] text-zinc-400 font-mono leading-relaxed break-words whitespace-pre-wrap">
                    {this.state.error?.stack || 'No stack trace available.'}
                    {'\n\n'}
                    {this.state.errorInfo?.componentStack}
                  </pre>
                </div>
              </div>

              <div className="px-5 py-4 border-t border-border bg-card/50 flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground">Action required to recover state.</span>
                <Button 
                  onClick={() => window.location.reload()}
                  className="bg-red-600 hover:bg-red-700 text-white border-0 gap-2 font-semibold tracking-wide text-xs h-9 px-6"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reinitialize Client
                </Button>
              </div>
            </div>

          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
