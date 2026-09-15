import { useState } from 'react';

// 人工介入横幅：区分第 1 层（补数据）和第 2 层（审批）。
// onSubmit(payload) 提交恢复数据，payload 直接作为 /api/chat/resume 的 resume 字段。
export default function InterruptBanner({ value, onSubmit, disabled }) {
  const [text, setText] = useState('');

  if (!value) return null;

  // 第 1 层：缺字段，请求补充信息
  if (value.type === 'order_info_request') {
    return (
      <div className="interrupt-banner">
        <div className="interrupt-title">需要补充信息</div>
        <div className="interrupt-desc">缺少字段：{value.missing_fields}</div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="输入补充的信息，例如：物料编号 P001，数量 100"
          rows={2}
        />
        <button
          disabled={disabled || !text.trim()}
          onClick={() => onSubmit({ supplement: text.trim() })}
        >
          提交补充
        </button>
      </div>
    );
  }

  // 第 2 层：写操作审批
  const requests = value.action_requests || [];
  if (requests.length > 0) {
    return (
      <div className="interrupt-banner">
        <div className="interrupt-title">需要你的审批</div>
        {requests.map((req, i) => (
          <div key={i} className="interrupt-action">
            <div className="interrupt-action-name">{req.name}</div>
            {req.description && (
              <div className="interrupt-desc">{req.description}</div>
            )}
            {req.args && (
              <pre className="interrupt-args">
                {JSON.stringify(req.args, null, 2)}
              </pre>
            )}
          </div>
        ))}
        <div className="interrupt-buttons">
          <button
            className="btn-approve"
            disabled={disabled}
            onClick={() =>
              onSubmit({
                decisions: requests.map(() => ({ type: 'approve' })),
              })
            }
          >
            批准
          </button>
          <button
            className="btn-reject"
            disabled={disabled}
            onClick={() =>
              onSubmit({
                decisions: requests.map(() => ({
                  type: 'reject',
                  message: '用户拒绝',
                })),
              })
            }
          >
            拒绝
          </button>
        </div>
      </div>
    );
  }

  return null;
}
