import { javascript } from "@codemirror/lang-javascript";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import CodeMirror from "@uiw/react-codemirror";

type CodeEditorProps = {
  path: string;
  value: string;
  onChange: (value: string) => void;
};

export function CodeEditor({ path, value, onChange }: CodeEditorProps) {
  return (
    <CodeMirror
      aria-label={`编辑 ${path}`}
      basicSetup={{ foldGutter: true, highlightActiveLine: true, lineNumbers: true }}
      className="bundle-code-editor"
      extensions={languageExtensions(path)}
      height="100%"
      theme="light"
      value={value}
      onChange={onChange}
    />
  );
}

function languageExtensions(path: string) {
  const lowerPath = path.toLowerCase();
  if (lowerPath.endsWith(".md") || lowerPath.endsWith(".markdown")) return [markdown()];
  if (lowerPath.endsWith(".json")) return [json()];
  if (lowerPath.endsWith(".yaml") || lowerPath.endsWith(".yml")) return [yaml()];
  if (lowerPath.endsWith(".py")) return [python()];
  if (lowerPath.endsWith(".js") || lowerPath.endsWith(".jsx")) return [javascript({ jsx: true })];
  if (lowerPath.endsWith(".ts") || lowerPath.endsWith(".tsx")) return [javascript({ jsx: lowerPath.endsWith(".tsx"), typescript: true })];
  return [];
}
