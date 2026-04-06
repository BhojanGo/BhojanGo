import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "../lib/utils";

const spinnerVariants = cva("animate-spin rounded-full border-2 border-current border-t-transparent", {
  variants: {
    size: {
      xs: "h-3 w-3",
      sm: "h-4 w-4",
      md: "h-6 w-6",
      lg: "h-8 w-8",
      xl: "h-12 w-12",
    },
    color: {
      primary: "text-orange-500",
      white: "text-white",
      gray: "text-gray-500",
      current: "text-current",
    },
  },
  defaultVariants: {
    size: "md",
    color: "primary",
  },
});

export interface SpinnerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "color">,
    VariantProps<typeof spinnerVariants> {
  label?: string;
}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ className, size, color, label = "Loading...", ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="status"
        aria-label={label}
        className={cn("inline-flex items-center justify-center", className)}
        {...props}
      >
        <div className={cn(spinnerVariants({ size, color }))} />
        <span className="sr-only">{label}</span>
      </div>
    );
  }
);
Spinner.displayName = "Spinner";

interface FullPageSpinnerProps {
  label?: string;
}

const FullPageSpinner: React.FC<FullPageSpinnerProps> = ({ label = "Loading..." }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm dark:bg-gray-900/80">
    <div className="flex flex-col items-center gap-3">
      <Spinner size="xl" color="primary" label={label} />
      <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{label}</p>
    </div>
  </div>
);

export { Spinner, FullPageSpinner };
