import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api } from "../api";
import type { SystemSettings } from "../types";
import { ui } from "../i18n";
import type { Lang } from "../i18n";
import { IntegrationPanel } from "../components/IntegrationPanel";
import { PathInput } from "../components/PathInput";

export function SettingsPage({ t, settings, setSettings, setLang, setMessage }: {
  t: typeof ui.zh.settings;
  settings: SystemSettings;
  setSettings: (settings: SystemSettings) => void;
  setLang: (lang: Lang) => void;
  setMessage: (message: string) => void;
}) {
  const [draft, setDraft] = useState<SystemSettings>(settings);

  useEffect(() => setDraft(settings), [settings]);

  async function save(nextDraft = draft) {
    const saved = await api.updateSettings(nextDraft);
    setSettings(saved);
    const nextLang = saved.general.language === "en-US" ? "en" : "zh";
    setLang(nextLang);
    localStorage.setItem("rrw-lang", nextLang);
    setMessage(t.saved);
  }

  async function test(integration: string) {
    const result = await api.testSettings(integration, draft);
    setMessage(result.message);
  }

  function update<K extends keyof SystemSettings>(section: K, value: SystemSettings[K]) {
    setDraft((current) => ({ ...current, [section]: value }));
  }

  const integrations = draft.integrations;
  return (
    <section className="settings-layout">
      <div className="panel accent-cyan">
        <h2>{t.general}</h2>
        <label className="field-label"><span>{t.language}</span>
          <select value={draft.general.language} onChange={(event) => {
            const next = { ...draft, general: { language: event.target.value } };
            setDraft(next);
            void save(next);
          }}>
            <option value="zh-CN">{t.chinese}</option>
            <option value="en-US">{t.english}</option>
          </select>
        </label>
      </div>

      <div className="panel accent-green settings-wide">
        <div className="panel-heading compact-heading"><h2>{t.paths}</h2><button onClick={() => void test("paths")}>{t.test}</button></div>
        <div className="settings-grid">
          <PathInput label={t.projectsRoot} value={draft.paths.projects_root} onChange={(value) => update("paths", { ...draft.paths, projects_root: value })} />
          <PathInput label={t.knowledgeRoot} value={draft.paths.knowledge_root} onChange={(value) => update("paths", { ...draft.paths, knowledge_root: value })} />
          <PathInput label={t.vaultPath} value={draft.paths.obsidian_vault} onChange={(value) => update("paths", { ...draft.paths, obsidian_vault: value })} />
          <PathInput label={t.datasetRoot} value={draft.paths.dataset_root} onChange={(value) => update("paths", { ...draft.paths, dataset_root: value })} />
          <PathInput label={t.experimentRoot} value={draft.paths.experiment_root} onChange={(value) => update("paths", { ...draft.paths, experiment_root: value })} />
        </div>
      </div>

      <div className="panel accent-violet settings-wide">
        <h2>{t.integrations}</h2>
        <div className="integration-grid">
          <IntegrationPanel title={t.obsidian} enabled={integrations.obsidian.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, enabled } })} onTest={() => void test("obsidian")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.vaultPath} value={integrations.obsidian.vault_path} onChange={(value) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, vault_path: value } })} />
            <PathInput label={t.knowledgeRoot} value={integrations.obsidian.knowledge_root} onChange={(value) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, knowledge_root: value } })} />
            <label className="checkbox-line"><input type="checkbox" checked={integrations.obsidian.use_obsidian_uri} onChange={(event) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, use_obsidian_uri: event.target.checked } })} />{t.useObsidianUri}</label>
          </IntegrationPanel>

          <IntegrationPanel title={t.zotero} enabled={integrations.zotero.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, enabled } })} onTest={() => void test("zotero")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.connectionMode} value={integrations.zotero.connection_mode} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, connection_mode: value } })} />
            <PathInput label={t.userId} value={integrations.zotero.user_id} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, user_id: value } })} />
            <PathInput label={t.apiKey} value={integrations.zotero.api_key ?? integrations.zotero.api_key_masked ?? ""} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, api_key: value } })} password />
            <PathInput label={t.library} value={integrations.zotero.library} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, library: value } })} />
          </IntegrationPanel>

          <IntegrationPanel title={t.github} enabled={integrations.github.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, github: { ...integrations.github, enabled } })} onTest={() => void test("github")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.username} value={integrations.github.username} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, username: value } })} />
            <PathInput label={t.token} value={integrations.github.personal_access_token ?? integrations.github.personal_access_token_masked ?? ""} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, personal_access_token: value } })} password />
            <PathInput label={t.defaultOwner} value={integrations.github.default_owner} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, default_owner: value } })} />
            <PathInput label={t.defaultBranch} value={integrations.github.default_branch} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, default_branch: value } })} />
          </IntegrationPanel>

          <IntegrationPanel title={t.ai} enabled={integrations.ai.provider !== "none"} onEnabled={(enabled) => update("integrations", { ...integrations, ai: { ...integrations.ai, provider: enabled ? "openai-compatible" : "none" } })} onTest={() => void test("ai")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.aiApiBase} value={integrations.ai.api_base} onChange={(value) => update("integrations", { ...integrations, ai: { ...integrations.ai, api_base: value } })} />
            <PathInput label={t.apiKey} value={integrations.ai.api_key ?? integrations.ai.api_key_masked ?? ""} onChange={(value) => update("integrations", { ...integrations, ai: { ...integrations.ai, api_key: value } })} password />
            <PathInput label={t.aiModel} value={integrations.ai.model} onChange={(value) => update("integrations", { ...integrations, ai: { ...integrations.ai, model: value } })} />
            <label className="field-label"><span>{t.aiOutputLanguage}</span>
              <select value={integrations.ai.output_language} onChange={(event) => update("integrations", { ...integrations, ai: { ...integrations.ai, output_language: event.target.value } })}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </label>
            <PathInput label={t.aiResearchInterests} value={integrations.ai.research_interests} onChange={(value) => update("integrations", { ...integrations, ai: { ...integrations.ai, research_interests: value } })} />
            <PathInput label={t.aiMaxPdfChars} value={String(integrations.ai.max_pdf_chars ?? 60000)} onChange={(value) => update("integrations", { ...integrations, ai: { ...integrations.ai, max_pdf_chars: Number(value.replace(/\D/g, "")) || 60000 } })} />
            <PathInput label={t.aiZoteroDataDir} value={integrations.zotero.data_dir ?? ""} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, data_dir: value } })} />
          </IntegrationPanel>
        </div>
        <button className="primary settings-save" onClick={() => void save()}><Check size={16} />{t.save}</button>
      </div>

      <div className="panel accent-amber"><h2>{t.appearance}</h2><p className="muted">{t.placeholderOnly}</p></div>
      <div className="panel accent-rose"><h2>{t.advanced}</h2><p className="muted">{t.placeholderOnly}</p></div>
    </section>
  );
}

