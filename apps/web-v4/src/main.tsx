import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/hub.css";
import "./styles/hub-cards.css";
import "./styles/hub-recent.css";
import "./styles/skill.css";
import "./styles/bundle.css";
import "./styles/workspaces.css";
import "./styles/version-upload.css";
import "./styles/skill-version-track.css";
import "./styles/version-inspector-actions.css";
import "./styles/history.css";
import "./styles/evaluation.css";
import "./styles/case-version-roadmap.css";
import "./styles/manual-evaluation.css";
import "./styles/manual-case-list.css";
import "./styles/manual-version-detail.css";
import "./styles/manual-evaluation-detail.css";
import "./styles/forms.css";
import "./styles/responsive.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
