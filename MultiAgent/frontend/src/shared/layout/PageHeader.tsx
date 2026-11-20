import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/shared/lib/utils";

export function PageHeader({ title, description, actions, back, className, icon }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; back?: string; className?: string; icon?: ReactNode }) {
  return (
    <div className={cn("mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {back && (
          <Link to={back} className="mb-1.5 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
            <ChevronLeft className="size-3.5" /> Back
          </Link>
        )}
        <div className="flex items-center gap-3">
          {icon}
          <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        </div>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Page({ children, className, wide }: { children: ReactNode; className?: string; wide?: boolean }) {
  return <div className={cn("mx-auto w-full px-4 py-5 sm:px-6 sm:py-7 lg:px-8", wide ? "max-w-[1600px]" : "max-w-6xl", className)}>{children}</div>;
}
