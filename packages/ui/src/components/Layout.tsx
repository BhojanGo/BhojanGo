import * as React from "react";

import { cn } from "../lib/utils";

/**
 * Page content: at most 1200 px wide, centred, gutters 16 / 32 / 48 px (phone /
 * from 768 px / from 1024 px). The same as the `.container-page` class from the
 * Tailwind preset, which server components and plain markup use directly.
 */
export function Container({ as: Tag = "div", className, ...rest }: React.HTMLAttributes<HTMLElement> & { as?: React.ElementType }) {
  return <Tag className={cn("container-page", className)} {...rest} />;
}

/**
 * A page section inside the container, with the fluid vertical rhythm (32 px on a
 * phone to 64 px on a wide screen; `tight` halves it). `.section-page` /
 * `.section-page-tight` are the class versions.
 */
export function Section({ tight, className, ...rest }: React.HTMLAttributes<HTMLElement> & { tight?: boolean }) {
  return <section className={cn("container-page", tight ? "section-page-tight" : "section-page", className)} {...rest} />;
}
