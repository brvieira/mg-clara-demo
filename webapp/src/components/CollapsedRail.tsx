import type { ReactNode } from "react";
import { PanelLeftOpen, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface CollapsedRailProps {
  side: "left" | "right";
  label: string;
  onExpand: () => void;
  accentDot?: boolean;
  children?: ReactNode;
  dark?: boolean;
}

export function CollapsedRail({
  side,
  label,
  onExpand,
  accentDot,
  children,
  dark,
}: CollapsedRailProps) {
  const Icon = side === "left" ? PanelLeftOpen : PanelRightOpen;
  return (
    <div
      className={`flex h-full w-[52px] shrink-0 flex-col items-center gap-4 py-3 ${
        dark ? "bg-[var(--vz-dbg-bg)] text-[var(--vz-dbg-text)]" : "bg-vz-branco"
      } ${side === "left" ? "border-r" : "border-l"} border-[var(--vz-border)]`}
    >
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onExpand}
              aria-label={`Expandir ${label}`}
            />
          }
        >
          <Icon className="size-4" />
        </TooltipTrigger>
        <TooltipContent side={side === "left" ? "right" : "left"}>Expandir</TooltipContent>
      </Tooltip>

      {children}

      <span
        className="mt-2 text-[10px] font-medium tracking-[0.14em] text-[var(--vz-faint)] uppercase"
        style={{ writingMode: "vertical-rl" }}
      >
        {label}
      </span>

      {accentDot && <span className="mt-auto size-2 rounded-full bg-[var(--vz-accent)]" />}
    </div>
  );
}
