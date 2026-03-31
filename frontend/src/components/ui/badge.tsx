import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "critical" | "action" | "info" | "success" | "new" | "nk" | "mlit" | "egov";
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  const variants = {
    default: "bg-zinc-500/15 text-zinc-300 border border-zinc-500/20 dark:bg-zinc-500/15 dark:text-zinc-300",
    critical: "bg-rose-500/15 text-rose-300 border border-rose-500/20 dark:bg-rose-500/15 dark:text-rose-300",
    action: "bg-amber-500/15 text-amber-300 border border-amber-500/20 dark:bg-amber-500/15 dark:text-amber-300",
    info: "bg-zinc-500/10 text-zinc-400 border border-zinc-500/15 dark:bg-zinc-500/10 dark:text-zinc-400",
    success: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 dark:bg-emerald-500/15 dark:text-emerald-300",
    new: "bg-rose-500 text-white border border-rose-400/30",
    nk: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 dark:bg-emerald-500/15 dark:text-emerald-300",
    mlit: "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20 dark:bg-indigo-500/15 dark:text-indigo-300",
    egov: "bg-purple-500/15 text-purple-300 border border-purple-500/20 dark:bg-purple-500/15 dark:text-purple-300",
  };

  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}
