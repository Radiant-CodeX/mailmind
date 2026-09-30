"use client";

import React from "react";
import type { LucideIcon } from "lucide-react";
import type { Priority } from "../../lib/types";
import { PRIORITY_LABEL, initials } from "./format";

type Variant = "primary" | "quiet" | "ghost" | "danger";

const BTN_BASE =
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap font-medium transition-[background,color,transform,filter] duration-200 ease-out-expo active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none cursor-pointer select-none";

const BTN_VARIANT: Record<Variant, string> = {
  primary: "bg-cobalt text-cobalt-ink hover:brightness-110",
  quiet: "bg-sunk text-ink hover:bg-rule",
  ghost: "text-ink-2 hover:bg-hover hover:text-ink",
  danger: "text-urgent hover:bg-urgent-soft",
};

const BTN_SIZE = {
  sm: "h-8 px-3 text-[13px] rounded-full",
  md: "h-9 px-4 text-sm rounded-full",
};

export function Button({
  variant = "quiet",
  size = "md",
  icon: Icon,
  loading,
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: keyof typeof BTN_SIZE;
  icon?: LucideIcon;
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      className={`${BTN_BASE} ${BTN_VARIANT[variant]} ${BTN_SIZE[size]} ${className}`}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <span className="size-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" aria-hidden />
      ) : (
        Icon && <Icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
      )}
      {children}
    </button>
  );
}

export function IconButton({
  icon: Icon,
  label,
  active,
  className = "",
  tone = "default",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  tone?: "default" | "danger";
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex size-8 items-center justify-center rounded-full transition-colors duration-150 cursor-pointer disabled:opacity-40 disabled:pointer-events-none ${
        active
          ? "bg-cobalt-soft text-cobalt"
          : tone === "danger"
          ? "text-ink-3 hover:bg-urgent-soft hover:text-urgent"
          : "text-ink-3 hover:bg-hover hover:text-ink"
      } ${className}`}
      {...rest}
    >
      <Icon className="size-[17px]" strokeWidth={1.75} aria-hidden />
    </button>
  );
}

export function PriorityChip({ priority, className = "" }: { priority: Priority; className?: string }) {
  const tone =
    priority === "CRITICAL"
      ? "bg-urgent-soft text-urgent"
      : priority === "HIGH"
      ? "bg-soon-soft text-soon"
      : "bg-sunk text-ink-3";
  return (
    <span className={`inline-flex h-5 items-center rounded-full px-2 text-[11px] font-semibold leading-none ${tone} ${className}`}>
      {PRIORITY_LABEL[priority]}
    </span>
  );
}

export function Tag({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex h-5 items-center rounded-full bg-sunk px-2 text-[11px] font-medium leading-none text-ink-2 ${className}`}>
      {children}
    </span>
  );
}

/* Initials on a tint derived from the name: stable per sender, quiet in both themes. */
export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-ink"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `color-mix(in oklab, hsl(${h} 55% 60%) 22%, var(--mm-sunk))`,
      }}
    >
      {initials(name)}
    </span>
  );
}

export function SectionHead({ title, meta, action }: { title: string; meta?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h3 className="text-[13px] font-semibold text-ink">
        {title}
        {meta !== undefined && <span className="ml-1.5 font-normal text-ink-3">{meta}</span>}
      </h3>
      {action}
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-rule bg-surface px-1 font-mono text-[10px] text-ink-3">
      {children}
    </kbd>
  );
}
