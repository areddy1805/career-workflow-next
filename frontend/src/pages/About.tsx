import { Info, Code, ExternalLink } from "lucide-react";

export default function About() {
  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Info className="w-4 h-4 text-primary" /> About
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Platform information and resources.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-muted/5 p-6 flex items-center justify-center">
        <div className="max-w-md w-full bg-card border border-border/50 rounded-xl p-8 text-center space-y-6 shadow-sm">
          <div>
            <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-primary/20">
              <span className="text-2xl font-black tracking-tighter text-primary">
                CW
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight">
              Career Workflow
            </h2>
            <p className="text-muted-foreground mt-1">
              Autonomous Job Operations Console
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 text-left border-y border-border/40 py-4">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                Version
              </p>
              <p className="font-mono mt-0.5">2.0.0-rc1</p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                Architecture
              </p>
              <p className="font-mono mt-0.5">Operations Console</p>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <a
              href="https://github.com/areddy1805/career-workflow-next"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors p-2 bg-secondary/30 rounded-lg hover:bg-secondary/50"
            >
              <Code className="w-4 h-4" /> GitHub Repository{" "}
              <ExternalLink className="w-3 h-3 opacity-50" />
            </a>
          </div>

          <p className="text-[10px] text-muted-foreground/60 pt-4">
            © {new Date().getFullYear()} Career Workflow. Internal tools.
          </p>
        </div>
      </div>
    </div>
  );
}
