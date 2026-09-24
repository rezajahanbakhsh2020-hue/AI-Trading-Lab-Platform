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
      data-mobile-geometry-contract="true"
      className={combinedClassName}
      style={{
        width: "100%",
        maxWidth: "100%",
        minWidth: 0,
        inlineSize: "100%",
        maxInlineSize: "100%",
        minInlineSize: 0,
        boxSizing: "border-box",
        overflowX: "auto",
        WebkitOverflowScrolling: "touch",
      }}
    >
      {children}
    </div>
  );
}

/**
 * BoundedTableWrapper (Permanent Mobile Geometry Contract Primitive)
 *
 * Automatically wraps tabular data in a responsive, scrollable container
 * that guarantees zero horizontal document overflow on mobile viewports.
 */
export function BoundedTableWrapper({
  children,
  className = "",
  "data-testid": dataTestId,
}: {
  children: React.ReactNode;
  className?: string;
  "data-testid"?: string;
}) {
  return (
    <div
      data-testid={dataTestId || "bounded-table-wrapper"}
      className={`table-responsive ${className}`.trim()}
      style={{
        width: "100%",
        maxWidth: "100%",
        minWidth: 0,
        boxSizing: "border-box",
        overflowX: "auto",
        WebkitOverflowScrolling: "touch",
      }}
    >
      {children}
    </div>
  );
}

/**
 * BoundedModal (Permanent Mobile Geometry Contract Primitive)
 *
 * Sizing boundary wrapper for modals, command palettes, and dialog overlays.
 * Prevents fixed dialog width from pushing beyond the mobile viewport (360px+).
 */
export function BoundedModal({
  children,
  className = "",
  maxWidthPx = 480,
  onClick,
  "data-testid": dataTestId,
}: {
  children: React.ReactNode;
  className?: string;
  maxWidthPx?: number;
  onClick?: (e: React.MouseEvent) => void;
  "data-testid"?: string;
}) {
  return (
    <div
      data-testid={dataTestId || "bounded-modal"}
      className={`command-palette-modal modal-card ${className}`.trim()}
      onClick={onClick}
      style={{
        width: "100%",
        maxWidth: `min(100%, ${maxWidthPx}px)`,
        minWidth: 0,
        boxSizing: "border-box",
      }}
    >
      {children}
    </div>
  );
}
