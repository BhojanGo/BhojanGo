import * as React from "react";
import { cn } from "../lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  /** pill = search bars; field = forms */
  shape?: "field" | "pill";
  leading?: React.ReactNode;
}

/** Text field with its label 8 px above it; errors in Chili, never only colour. */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, shape = "field", leading, className, id, ...rest }, ref,
) {
  const auto = React.useId();
  const inputId = id ?? auto;
  return (
    <div className="flex flex-col gap-2">
      {label && <label htmlFor={inputId} className="text-sm font-bold text-kohl">{label}</label>}
      <div className={cn(
        "flex items-center gap-2.5 bg-white px-4",
        shape === "pill" ? "h-[54px] rounded-pill shadow-float" : "h-14 rounded-card border-[1.5px]",
        shape === "field" && (error ? "border-chili" : "border-line-strong focus-within:border-peacock"),
      )}>
        {leading}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? `${inputId}-note` : undefined}
          className={cn("h-full flex-1 bg-transparent text-base text-kohl outline-none placeholder:text-muted", className)}
          {...rest}
        />
      </div>
      {(error || hint) && (
        <p id={`${inputId}-note`} className={cn("text-[13px]", error ? "font-semibold text-chili" : "text-muted")}>{error ?? hint}</p>
      )}
    </div>
  );
});
