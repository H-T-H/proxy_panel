import CodeMirror from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";


export default function YamlEditor({ value, onChange, minHeight = "320px", readOnly = false }) {
  return (
    <div className="yaml-editor">
      <CodeMirror
        value={value || ""}
        height={minHeight}
        extensions={[yaml()]}
        editable={!readOnly}
        basicSetup={{
          lineNumbers: true,
          foldGutter: true,
          highlightActiveLine: !readOnly,
          bracketMatching: true
        }}
        onChange={onChange}
      />
    </div>
  );
}
