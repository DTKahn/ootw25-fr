import type { RowStatus } from "./rows";

export const STATUS_LABELS: Record<RowStatus, string> = {
  not_reviewed: "Not reviewed",
  no_changes: "No changes",
  suggestions: "Suggestions",
  flagged: "Flagged",
};

// CSS class names defined in app/review/page.tsx's <style> block.
export const STATUS_BADGE_CLASS: Record<RowStatus, string> = {
  not_reviewed: "status-badge status-badge--not-reviewed",
  no_changes: "status-badge status-badge--no-changes",
  suggestions: "status-badge status-badge--suggestions",
  flagged: "status-badge status-badge--flagged",
};
