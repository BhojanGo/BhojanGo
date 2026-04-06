import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "../lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 rounded-lg font-semibold",
    "transition-all duration-200 focus-visible:outline-none focus-visible:ring-2",
    "focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
    "active:scale-[0.98]",
  ],
  {
    variants: {
      variant: {
        primary: [
          "bg-orange-500 text-white shadow-sm",
          "hover:bg-orange-600 focus-visible:ring-orange-500",
          "dark:bg-orange-500 dark:hover:bg-orange-600",
        ],
        secondary: [
          "bg-gray-100 text-gray-900 shadow-sm",
          "hover:bg-gray-200 focus-visible:ring-gray-400",
          "dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700",
        ],
        outline: [
          "border border-gray-300 bg-transparent text-gray-900",
          "hover:bg-gray-50 focus-visible:ring-gray-400",
          "dark:border-gray-600 dark:text-gray-100 dark:hover:bg-gray-800",
        ],
        ghost: [
          "bg-transparent text-gray-700",
          "hover:bg-gray-100 focus-visible:ring-gray-400",
          "dark:text-gray-300 dark:hover:bg-gray-800",
        ],
        destructive: [
          "bg-red-500 text-white shadow-sm",
          "hover:bg-red-600 focus-visible:ring-red-500",
        ],
        link: ["text-orange-500 underline-offset-4 hover:underline p-0 h-auto font-medium"],
      },
      size: {
        xs: "h-7 px-2.5 text-xs",
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-11 px-6 text-base",
        xl: "h-12 px-8 text-base",
        icon: "h-10 w-10",
        "icon-sm": "h-8 w-8",
      },
      fullWidth: {
        true: "w-full",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, fullWidth, loading, leftIcon, rightIcon, children, ...props },
    ref
  ) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size, fullWidth, className }))}
        disabled={loading ?? props.disabled}
        aria-busy={loading}
        {...props}
      >
        {loading ? (
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        ) : leftIcon ? (
          <span className="shrink-0">{leftIcon}</span>
        ) : null}
        {children}
        {!loading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = "Button";

export { Button, buttonVariants };
