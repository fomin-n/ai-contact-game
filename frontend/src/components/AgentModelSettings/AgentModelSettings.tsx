import type { AgentModelSelection, ProviderModelCatalog } from "../../types/game";
import type { UiCopy } from "../../i18n/copy";
import "./AgentModelSettings.css";

type ModelRole = keyof AgentModelSelection;

const roleOrder: ModelRole[] = ["wordMaster", "playerA", "playerB"];

function roleLabel(labels: UiCopy, role: ModelRole): string {
  return role === "wordMaster" ? labels.wordMaster : role === "playerA" ? labels.playerA : labels.playerB;
}

function encode(providerId: string, modelId: string): string {
  return `${providerId}:${modelId}`;
}

function decode(value: string): { providerId: string; modelId: string } {
  const idx = value.indexOf(":");
  return { providerId: value.slice(0, idx), modelId: value.slice(idx + 1) };
}

type AgentModelSettingsProps = {
  labels: UiCopy;
  catalog: ProviderModelCatalog[];
  selection: AgentModelSelection;
  disabled: boolean;
  onSelectionChange: (selection: AgentModelSelection) => void;
};

export function AgentModelSettings({
  labels,
  catalog,
  selection,
  disabled,
  onSelectionChange,
}: AgentModelSettingsProps) {
  function handleChange(role: ModelRole, value: string) {
    const { providerId, modelId } = decode(value);
    onSelectionChange({ ...selection, [role]: { provider: providerId, model: modelId } });
  }

  return (
    <section className="panel ai-models-panel" aria-label={labels.aiModels}>
      <h2 className="ai-models-heading">{labels.aiModels}</h2>

      {!catalog.length && <p className="muted">...</p>}

      {!!catalog.length && (
        <div className="role-rows">
          {roleOrder.map((role) => {
            const rs = selection[role];
            const roleName = roleLabel(labels, role);
            return (
              <div className="role-row" key={role}>
                <span className="role-row-name">{roleName}</span>
                <select
                  className="role-model-select"
                  value={encode(rs.provider, rs.model)}
                  disabled={disabled}
                  aria-label={roleName}
                  onChange={(e) => handleChange(role, e.target.value)}
                >
                  {catalog.map((provider) => (
                    <optgroup label={provider.displayName} key={provider.id}>
                      {provider.models.map((model) => (
                        <option
                          value={encode(provider.id, model.id)}
                          key={model.id}
                          disabled={!provider.hasApiKey}
                        >
                          {model.id}
                          {model.isCustom ? " (custom)" : ""}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
