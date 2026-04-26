import { useEffect } from "react";
import type { View } from "./domain/types";
import { useLocalAppState } from "./store/localStore";
import { EvalCorpusPage } from "./components/EvalCorpusPage";
import { HubPage } from "./components/HubPage";
import { ResultPage } from "./components/ResultPage";
import { SkillPage } from "./components/SkillPage";
import { WorkbenchPage } from "./components/WorkbenchPage";
import { ManagePage } from "./components/ManagePage";
import { latestVersionForSkill } from "./domain/scoring";
import { applyRouteToState, pathForState } from "./domain/routes";

export function App() {
  const [state, setState, reset, ready] = useLocalAppState();
  useEffect(() => {
    if (!ready) return;
    const nextPath = pathForState(state);
    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath);
    }
  }, [ready, state]);

  useEffect(() => {
    const onPopState = () => {
      setState((prev) => applyRouteToState(prev, window.location.pathname));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [setState]);

  const skill = state.data.skills.find((item) => item.id === state.selectedSkillRef);
  const defaultVariant = skill ? state.data.variants.find((item) => item.id === skill.defaultVariantRef) : undefined;
  const selectedVariant =
    state.data.variants.find((item) => item.id === state.selectedVariantRef) ?? defaultVariant;
  const selectedVariantVersion =
    state.data.variantVersions.find((item) => item.id === state.selectedVersionRef && item.variantRef === selectedVariant?.id) ??
    state.data.variantVersions.find((item) => item.id === selectedVariant?.currentVersionRef);
  const versions = state.data.evalSetVersions.filter((item) => {
    const corpus = state.data.evalCorpora.find((candidate) => candidate.id === item.corpusRef);
    return corpus?.skillRef === state.selectedSkillRef;
  });
  const version = state.data.evalSetVersions.find((item) => item.id === state.evalSetVersionRef) ?? versions[0];

  const page = pageTitle(state.view, skill?.slug);

  const setView = (view: View) => setState((prev) => ({ ...prev, view }));

  const toggleTag = (tag: string) =>
    setState((prev) => ({
      ...prev,
      requestedTags: prev.requestedTags.includes(tag)
        ? prev.requestedTags.filter((item) => item !== tag)
        : [...prev.requestedTags, tag],
    }));

  const installDefault = () => {
    if (defaultVariant) window.alert(`已选择安装默认变体 ${defaultVariant.name}。这是本地 demo，不会写入系统。`);
  };

  return (
    <div className="app-shell">
      <aside className="side-nav" aria-label="主导航">
        <div className="brand">
          <div className="brand-mark">SH</div>
          <div>
            <div className="brand-title">SkillHub Lab</div>
            <div className="brand-subtitle">Eval-backed demo</div>
          </div>
        </div>

        <nav className="nav-stack">
          <NavButton active={state.view === "hub"} icon="⌂" label="Hub" onClick={() => setView("hub")} />
          <NavButton active={state.view === "skill"} icon="◆" label="Variant Page" onClick={() => setView("skill")} />
          <NavButton active={state.view === "eval"} icon="▦" label="Eval Corpus" onClick={() => setView("eval")} />
          <NavButton active={state.view === "result"} icon="✓" label="Eval Result" onClick={() => setView("result")} />
          <NavButton active={state.view === "workbench"} icon="✎" label="Experiment" onClick={() => setView("workbench")} />
          <NavButton active={state.view === "manage"} icon="⚙" label="Manage" onClick={() => setView("manage")} />
        </nav>

        <div className="side-footer">
          <div className="mini-label">当前样例</div>
          <div className="mini-title">{defaultVariant?.name ?? skill?.slug ?? "未选择"}</div>
          <div className="mini-copy">变体分发，测评集支撑，来源反馈进入回归。</div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <div className="eyebrow">{page.eyebrow}</div>
            <h1>{page.title}</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" type="button" title="重置 demo 状态" aria-label="重置 demo 状态" onClick={reset}>
              ↺
            </button>
            {state.view !== "hub" && (
              <button className="primary-button" type="button" onClick={installDefault}>
                安装默认变体
              </button>
            )}
          </div>
        </header>

        <section className={`view ${state.view === "hub" ? "is-active" : ""}`}>
          <HubPage
            data={state.data}
            onOpenSkill={(skillRef) =>
              setState((prev) => {
                const nextSkill = prev.data.skills.find((item) => item.id === skillRef);
                const nextVariant = prev.data.variants.find((variant) => variant.id === nextSkill?.defaultVariantRef);
                const nextEvalSetVersion = latestVersionForSkill(prev.data, skillRef);
                return {
                  ...prev,
                  selectedSkillRef: skillRef,
                  selectedVariantRef: nextVariant?.id ?? prev.selectedVariantRef,
                  selectedVersionRef: nextVariant?.currentVersionRef ?? prev.selectedVersionRef,
                  evalSetVersionRef: nextEvalSetVersion?.id ?? prev.evalSetVersionRef,
                  view: "skill",
                };
              })
            }
          />
        </section>

        <section className={`view ${state.view === "skill" ? "is-active" : ""}`}>
          <SkillPage
            state={state}
            versions={versions}
            onToggleTag={toggleTag}
            onSetVersion={(evalSetVersionRef) => setState((prev) => ({ ...prev, evalSetVersionRef }))}
            onSelectVariant={(selectedVariantRef) =>
              setState((prev) => {
                const variant = prev.data.variants.find((item) => item.id === selectedVariantRef);
                return {
                  ...prev,
                  selectedVariantRef,
                  selectedVersionRef: variant?.currentVersionRef ?? prev.selectedVersionRef,
                };
              })
            }
            onSelectVersion={(selectedVersionRef) => setState((prev) => ({ ...prev, selectedVersionRef }))}
            onOpenEvalSet={() => setState((prev) => ({ ...prev, view: "eval" }))}
            onOpenResult={() => setState((prev) => ({ ...prev, view: "result" }))}
            onOpenWorkbench={() => setState((prev) => ({ ...prev, view: "workbench" }))}
          />
        </section>

        <section className={`view ${state.view === "eval" ? "is-active" : ""}`}>
          {version && (
            <EvalCorpusPage
              data={state.data}
              version={version}
              skillRef={state.selectedSkillRef}
              setState={setState}
            />
          )}
        </section>

        <section className={`view ${state.view === "result" ? "is-active" : ""}`}>
          {version && selectedVariant && selectedVariantVersion && (
            <ResultPage
              data={state.data}
              variant={selectedVariant}
              variantVersion={selectedVariantVersion}
              evalSetVersion={version}
            />
          )}
        </section>

        <section className={`view ${state.view === "workbench" ? "is-active" : ""}`}>
          <WorkbenchPage state={state} setState={setState} />
        </section>

        <section className={`view ${state.view === "manage" ? "is-active" : ""}`}>
          <ManagePage state={state} setState={setState} />
        </section>
      </main>
    </div>
  );
}

function NavButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className={`nav-item ${active ? "is-active" : ""}`} type="button" onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function pageTitle(view: View, slug = "code-reviewer") {
  if (view === "hub") return { eyebrow: "SkillHub", title: "Explore Skills" };
  if (view === "eval") return { eyebrow: "Eval Corpus", title: `${slug} corpus` };
  if (view === "result") return { eyebrow: "Eval Result", title: "当前测评结果" };
  if (view === "workbench") return { eyebrow: "Experiment", title: `${slug} 实验台` };
  if (view === "manage") return { eyebrow: "Manage", title: `${slug} 管理` };
  return { eyebrow: "Variant Page", title: slug };
}
