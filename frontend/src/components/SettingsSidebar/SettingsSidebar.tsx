import type { ReactNode } from "react";
import type { UiCopy } from "../../i18n/copy";
import { SidebarCollapseButton } from "../SidebarCollapseButton";
import "./SettingsSidebar.css";

type SettingsSidebarProps = {
  labels: UiCopy;
  isCollapsed: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function SettingsSidebar({ labels, isCollapsed, onToggle, children }: SettingsSidebarProps) {
  return (
    <aside className={`settings-sidebar ${isCollapsed ? "collapsed" : "expanded"}`}>
      <div className="settings-sidebar-header">
        {!isCollapsed && <h2>{labels.settings}</h2>}
        <SidebarCollapseButton
          isCollapsed={isCollapsed}
          collapseLabel={labels.collapseSettings}
          expandLabel={labels.expandSettings}
          onToggle={onToggle}
        />
      </div>

      {isCollapsed ? (
        <button className="settings-sidebar-rail" type="button" onClick={onToggle}>
          <span>{labels.settings}</span>
        </button>
      ) : (
        <div className="settings-sidebar-content">{children}</div>
      )}
    </aside>
  );
}
