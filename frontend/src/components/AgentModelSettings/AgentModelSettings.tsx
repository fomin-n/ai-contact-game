import type { AgentModelSelection, ProviderModelCatalog, RoleModelSelection } from "../../types/game";
import type { ModelSelectionMode } from "../../hooks/useGameController";
import type { UiCopy } from "../../i18n/copy";
import "./AgentModelSettings.css";

type ModelRole = keyof AgentModelSelection;

const roleOrder: ModelRole[] = ["wordMaster", "playerA", "playerB"];

function roleLabel(labels: UiCopy, role: ModelRole): string {
  return role === "wordMaster" ? labels.wordMaster : role === "playerA" ? labels.playerA : labels.playerB;
}

function providerFor(catalog: ProviderModelCatalog[], providerId: string): ProviderModelCatalog | undefined {
  return catalog.find((p) => p.id === providerId);
}

function firstModel(provider: ProviderModelCatalog | undefined): string {
  return provider?.defaultModel || provider?.models[0]?.id || "";
}

function modelDisplayName(catalog: ProviderModelCatalog[], providerId: string, modelId: string): string {
  return providerFor(catalog, providerId)?.models.find((m) => m.id === modelId)?.displayName ?? modelId;
}

// ── Sub-components ────────────────────────────────────────────────────────────

type ToggleSwitchProps = {
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
  label: string;
};

function ToggleSwitch({ checked, disabled, onChange, label }: ToggleSwitchProps) {
  return (
    <label className={`toggle-row${disabled ? " toggle-row-disabled" : ""}`}>
      <span className="toggle-switch">
        <input
          type="checkbox"
          role="switch"
          checked={checked}
          disabled={disabled}
          aria-label={label}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="toggle-track" aria-hidden="true" />
      </span>
      <span>{label}</span>
    </label>
  );
}


type SelectPairProps = {
  providerId: string;
  modelId: string;
  catalog: ProviderModelCatalog[];
  disabled: boolean;
  providerLabel: string;
  modelLabel: string;
  providerAriaLabel?: string;
  modelAriaLabel?: string;
  onProviderChange: (id: string) => void;
  onModelChange: (id: string) => void;
};

function SelectPair({
  providerId,
  modelId,
  catalog,
  disabled,
  providerLabel,
  modelLabel,
  providerAriaLabel,
  modelAriaLabel,
  onProviderChange,
  onModelChange,
}: SelectPairProps) {
  const provider = providerFor(catalog, providerId) ?? catalog[0];
  return (
    <>
      <label className="select-field">
        <span>{providerLabel}</span>
        <select
          value={providerId}
          disabled={disabled}
          aria-label={providerAriaLabel}
          onChange={(e) => onProviderChange(e.target.value)}
        >
          {catalog.map((p) => (
            <option value={p.id} disabled={!p.hasApiKey} key={p.id}>
              {p.displayName}
            </option>
          ))}
        </select>
      </label>
      <label className="select-field">
        <span>{modelLabel}</span>
        <select
          value={modelId}
          disabled={disabled || !provider}
          aria-label={modelAriaLabel}
          onChange={(e) => onModelChange(e.target.value)}
        >
          {(provider?.models ?? []).map((m) => (
            <option value={m.id} key={m.id}>
              {m.displayName}
              {m.isCustom ? " (custom)" : ""}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

type AgentModelSettingsProps = {
  labels: UiCopy;
  catalog: ProviderModelCatalog[];
  selection: AgentModelSelection;
  mode: ModelSelectionMode;
  disabled: boolean;
  onModeChange: (mode: ModelSelectionMode) => void;
  onSelectionChange: (selection: AgentModelSelection) => void;
};

export function AgentModelSettings({
  labels,
  catalog,
  selection,
  mode,
  disabled,
  onModeChange,
  onSelectionChange,
}: AgentModelSettingsProps) {
  function updateRole(role: ModelRole, next: RoleModelSelection) {
    onSelectionChange({ ...selection, [role]: next });
  }

  function handleProviderChange(role: ModelRole, providerId: string) {
    const provider = providerFor(catalog, providerId);
    updateRole(role, { provider: providerId, model: firstModel(provider) });
  }

  function handleModelChange(role: ModelRole, modelId: string) {
    updateRole(role, { ...selection[role], model: modelId });
  }

  const sharedModelName = modelDisplayName(catalog, selection.wordMaster.provider, selection.wordMaster.model);

  return (
    <section className="panel ai-models-panel" aria-label={labels.aiModels}>
      <header className="ai-models-header">
        <h2>{labels.aiModels}</h2>
        {!!catalog.length && (
          <ToggleSwitch
            checked={mode === "same"}
            disabled={disabled}
            onChange={(checked) => onModeChange(checked ? "same" : "advanced")}
            label={labels.useSameModel}
          />
        )}
      </header>

      {!catalog.length && <p className="muted">...</p>}

      {!!catalog.length && mode === "same" && (
        <div className="shared-selector">
          <div className="shared-selects">
            <SelectPair
              providerId={selection.wordMaster.provider}
              modelId={selection.wordMaster.model}
              catalog={catalog}
              disabled={disabled}
              providerLabel={labels.provider}
              modelLabel={labels.model}
              onProviderChange={(id) => handleProviderChange("wordMaster", id)}
              onModelChange={(id) => handleModelChange("wordMaster", id)}
            />
          </div>
          <div className="shared-meta">
            <span className="shared-meta-text">
              {labels.currentSetup} {sharedModelName} {labels.forAllRoles}
            </span>
          </div>
          <p className="applied-to">
            {labels.appliedTo} {labels.wordMaster}, {labels.playerA}, {labels.playerB}
          </p>
        </div>
      )}

      {!!catalog.length && mode === "advanced" && (
        <>
          <div className="role-rows">
            {roleOrder.map((role) => {
              const rs = selection[role];
              const roleName = roleLabel(labels, role);
              return (
                <div className="role-row" key={role}>
                  <div className="role-row-header">
                    <span className="role-row-name">{roleName}</span>
                  </div>
                  <div className="role-row-selects">
                    <SelectPair
                      providerId={rs.provider}
                      modelId={rs.model}
                      catalog={catalog}
                      disabled={disabled}
                      providerLabel={labels.provider}
                      modelLabel={labels.model}
                      providerAriaLabel={`${roleName} — ${labels.provider}`}
                      modelAriaLabel={`${roleName} — ${labels.model}`}
                      onProviderChange={(id) => handleProviderChange(role, id)}
                      onModelChange={(id) => handleModelChange(role, id)}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
