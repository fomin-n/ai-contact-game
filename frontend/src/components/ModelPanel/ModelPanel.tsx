import type { UiCopy } from "../../i18n/copy";
import type { ProviderInfo } from "../../types/game";

type ModelPanelProps = {
  labels: UiCopy;
  providerInfo: ProviderInfo;
};

export function ModelPanel({ labels, providerInfo }: ModelPanelProps) {
  return (
    <section className="panel model-panel" aria-label="Agent models">
      <div className="model-row">
        <span>{labels.wordMasterModel}</span>
        <strong>
          {providerInfo.providers.wordMasterDisplayName} / {providerInfo.models.wordMasterModel}
        </strong>
      </div>
      <div className="model-row">
        <span>{labels.playerAModel}</span>
        <strong>
          {providerInfo.providers.playerADisplayName} / {providerInfo.models.playerAModel}
        </strong>
      </div>
      <div className="model-row">
        <span>{labels.playerBModel}</span>
        <strong>
          {providerInfo.providers.playerBDisplayName} / {providerInfo.models.playerBModel}
        </strong>
      </div>
    </section>
  );
}
