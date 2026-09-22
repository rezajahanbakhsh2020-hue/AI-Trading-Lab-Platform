import React from "react";

interface BoundedPageContainerProps {
  children: React.ReactNode;
  className?: string;
  id?: string;
  "data-testid"?: string;
}

/**
 * BoundedPageContainer (Permanent Mobile Geometry Contract)
 *
 * Enforces application-wide mobile viewport geometry bounds on every page view.
 * Descendant components, tables, flex rows, grids, or charts CANNOT expand
 * the containing block beyond 100% width of the workspace viewport.
 */
export function BoundedPageContainer({
  children,
  className = "",
  id,
  "data-testid": dataTestId,
}: BoundedPageContainerProps) {
  const combinedClassName = `bounded-page-container ${className}`.trim();

  return (
    <div
      id={id}
      data-testid={dataTestId || "bounded-page-container"}
      className={combinedClassName}
      style={{
        width: "100%",
        maxWidth: "100%",
        minWidth: 0,
        inlineSize: "100%",
        maxInlineSize: "100%",
        minInlineSize: 0,
        boxSizing: "border-box",
      }}
    >
      {children}
    </div>
  );
}
