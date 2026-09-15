import { useState } from 'react';

// 把累计的 args 字符串尽量格式化成可读 JSON；解析不了就原样返回。
function prettyArgs(args) {
  if (!args) return '';
  try {
    return JSON.stringify(JSON.parse(args), null, 2);
  } catch {
    return args;
  }
}

// 工具调用轨迹卡片：TOOL 标签 + 工具名 + 调用 ID + 状态 + 可折叠的参数/结果。
export default function ToolCall({ tool }) {
  const done = tool.status === 'done';
  const [showArgs, setShowArgs] = useState(true);
  const [showResult, setShowResult] = useState(true);

  return (
    <div className={`tool-call ${done ? 'tool-done' : 'tool-running'}`}>
      <div className="tool-header">
        <span className="tool-eyebrow">TOOL</span>
        <span className="tool-name">{tool.name}</span>
        <span className="tool-status">{done ? '完成' : '调用中…'}</span>
      </div>

      {tool.id && <div className="tool-id">{tool.id}</div>}

      {tool.args && (
        <div className="tool-section">
          <button
            className="tool-section-header"
            onClick={() => setShowArgs((v) => !v)}
          >
            <span className="tool-toggle">{showArgs ? '▼' : '▶'}</span>
            <span>参数</span>
          </button>
          {showArgs && <pre className="tool-body">{prettyArgs(tool.args)}</pre>}
        </div>
      )}

      {tool.result != null && (
        <div className="tool-section">
          <button
            className="tool-section-header"
            onClick={() => setShowResult((v) => !v)}
          >
            <span className="tool-toggle">{showResult ? '▼' : '▶'}</span>
            <span>结果</span>
          </button>
          {showResult && <pre className="tool-body">{tool.result}</pre>}
        </div>
      )}
    </div>
  );
}
