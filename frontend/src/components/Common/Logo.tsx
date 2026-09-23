import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <span
          className={cn(
            "flex items-center gap-2.5 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          <BrandMark />
          <span className="text-base font-semibold tracking-tight">
            OpenGuard
          </span>
        </span>
        <span className="hidden group-data-[collapsible=icon]:block">
          <BrandMark compact />
        </span>
      </>
    ) : (
      <span className={cn("flex items-center gap-3", className)}>
        <BrandMark compact={variant === "icon"} />
        {variant === "full" && (
          <span className="text-xl font-semibold tracking-tight">
            OpenGuard
          </span>
        )}
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-full bg-foreground font-semibold text-background shadow-[0_0_28px_color-mix(in_oklab,currentColor_18%,transparent)]",
        compact ? "size-7 text-[10px]" : "size-9 text-xs",
      )}
    >
      O
    </span>
  )
}
