import type { AgentModelSelection, ProviderModelCatalog, RoleModelSelection } from "../../types/game";
import type { ModelSelectionMode } from "../../hooks/useGameController";
import type { UiCopy } from "../../i18n/copy";
import "./AgentModelSettings.css";

type ModelRole = keyof AgentModelSelection;

type AgentModelSettingsProps = {
  labels: UiCopy;
  catalog: ProviderModelCatalog[];
  selection: AgentModelSelection;
  mode: ModelSelectionMode;
  disabled: boolean;
  onModeChange: (mode: ModelSelectionMode) => void;
  onSelectionChange: (selection: AgentModelSelection) => void;
};

const roleOrder: ModelRole[] = ["wordMaster", "playerA", "playerB"];

function roleLabel(labels: UiCopy, role: ModelRole): string {
  if (role === "wordMaster") return labels.wordMasterModel;
  if (role === "playerA") return labels.playerAModel;
  return labels.playerBModel;
}

function providerFor(catalog: ProviderModelCatalog[], providerId: string): ProviderModelCatalog | undefined {
  return catalog.find((provider) => provider.id === providerId);
}

function firstModel(provider: ProviderModelCatalog | undefined): string {
  return provider?.defaultModel || provider?.models[0]?.id || "";
}

export function AgentModelSettings({
  labels,
  catalog,
  selection,
  mode,
  disabled,
  onModeChange,
  onSelectionChange
}: AgentModelSettingsProps) {
  function updateRole(role: ModelRole, nextRoleSelection: RoleModelSelection) {
    onSelectionChange({
      ...selection,
      [role]: nextRoleSelection
    });
  }

  function updateProvider(role: ModelRole, providerId: string) {
    const provider = providerFor(catalog, providerId);
    updateRole(role, {
      provider: providerId,
      model: firstModel(provider)
    });
  }

  function updateModel(role: ModelRole, model: string) {
    updateRole(role, {
      ...selection[role],
      model
    });
  }

  const rows = mode === "same" ? (["wordMaster"] as ModelRole[]) : roleOrder;

  return (
    <section className="panel agent-model-settings" aria-label={labels.aiModels}>
      <header>
        <h2>{labels.aiModels}</h2>
      </header>

      {!catalog.length && <p className="muted">...</p>}

      {!!catalog.length && <label className="model-same-toggle">
        <input
          type="checkbox"
          checked={mode === "same"}
          disabled={disabled}
          onChange={(event) => onModeChange(event.target.checked ? "same" : "advanced")}
        />
        <span>{labels.useSameModel}</span>
      </label>}

      {!!catalog.length && <div className="agent-model-rows">
        {rows.map((role) => {
          const roleSelection = selection[role];
          const provider = providerFor(catalog, roleSelection.provider) ?? catalog[0];
          return (
            <div className="agent-model-row" key={role}>
              <div className="agent-model-row-header">
                <strong>{mode === "same" ? labels.allRolesModel : roleLabel(labels, role)}</strong>
                {provider && (
                  <span className={provider.hasApiKey ? "key-status configured" : "key-status missing"}>
                    {provider.hasApiKey ? labels.providerConfigured : labels.providerMissingKey}
                  </span>
                )}
              </div>

              <label>
                <span>{labels.provider}</span>
                <select
                  value={roleSelection.provider}
                  disabled={disabled}
                  onChange={(event) => updateProvider(role, event.target.value)}
                >
                  {catalog.map((providerOption) => (
                    <option value={providerOption.id} disabled={!providerOption.hasApiKey} key={providerOption.id}>
                      {providerOption.displayName}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>{labels.model}</span>
                <select
                  value={roleSelection.model}
                  disabled={disabled || !provider}
                  onChange={(event) => updateModel(role, event.target.value)}
                >
                  {(provider?.models ?? []).map((model) => (
                    <option value={model.id} key={model.id}>
                      {model.displayName}
                      {model.isCustom ? " (custom)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          );
        })}
      </div>}
    </section>
  );
}
