import type { RowStatus } from "./rows";

export const STATUS_LABELS: Record<RowStatus, string> = {
  not_reviewed: "Not reviewed",
  approved: "Approved",
  changed: "Changed",
  flagged: "Flagged",
};

// CSS class names defined in app/review/page.tsx's <style> block.
export const STATUS_BADGE_CLASS: Record<RowStatus, string> = {
  not_reviewed: "status-badge status-badge--not-reviewed",
  approved: "status-badge status-badge--approved",
  changed: "status-badge status-badge--changed",
  flagged: "status-badge status-badge--flagged",
};
