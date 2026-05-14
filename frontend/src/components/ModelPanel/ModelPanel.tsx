import type { UiCopy } from "../../i18n/copy";
import type { ProviderInfo } from "../../types/game";

type ModelPanelProps = {
  labels: UiCopy;
  providerInfo: ProviderInfo;
};

export function ModelPanel({ labels, providerInfo }: ModelPanelProps) {
  const rows = [
    {
      label: labels.wordMasterModel,
      provider: providerInfo.providers.wordMasterDisplayName,
      hasApiKey: providerInfo.providers.wordMasterHasApiKey,
      model: providerInfo.models.wordMasterModel
    },
    {
      label: labels.playerAModel,
      provider: providerInfo.providers.playerADisplayName,
      hasApiKey: providerInfo.providers.playerAHasApiKey,
      model: providerInfo.models.playerAModel
    },
    {
      label: labels.playerBModel,
      provider: providerInfo.providers.playerBDisplayName,
      hasApiKey: providerInfo.providers.playerBHasApiKey,
      model: providerInfo.models.playerBModel
    }
  ];

  return (
    <section className="panel model-panel" aria-label="Agent models">
      {rows.map((row) => (
        <div className="model-row" key={row.label}>
          <span>{row.label}</span>
          <strong>
            {row.provider} / {row.model}
            {!row.hasApiKey && <em>{labels.providerMissingKey}</em>}
          </strong>
        </div>
      ))}
    </section>
  );
}
