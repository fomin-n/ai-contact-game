import "./SidebarCollapseButton.css";

type SidebarCollapseButtonProps = {
  isCollapsed: boolean;
  collapseLabel: string;
  expandLabel: string;
  onToggle: () => void;
};

export function SidebarCollapseButton({
  isCollapsed,
  collapseLabel,
  expandLabel,
  onToggle
}: SidebarCollapseButtonProps) {
  return (
    <button
      className="sidebar-collapse-button"
      type="button"
      aria-label={isCollapsed ? expandLabel : collapseLabel}
      aria-expanded={!isCollapsed}
      onClick={onToggle}
    >
      <span aria-hidden="true">{isCollapsed ? ">" : "<"}</span>
    </button>
  );
}
