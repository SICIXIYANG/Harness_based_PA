import logo from '../assets/logo.jpg';

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${mm}/${dd} ${hh}:${mi}`;
}

// 左侧历史会话侧边栏。
export default function History({
  sessions,
  currentThreadId,
  onSelect,
  onNew,
  onDelete,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img className="sidebar-logo" src={logo} alt="采购智能助手" />
      </div>
      <button className="new-chat-btn" onClick={onNew}>
        ＋ 新建对话
      </button>
      <div className="session-list">
        {sessions.length === 0 && (
          <div className="session-empty">暂无历史会话</div>
        )}
        {sessions.map((s) => (
          <div
            key={s.thread_id}
            className={`session-item ${
              s.thread_id === currentThreadId ? 'session-active' : ''
            }`}
            onClick={() => onSelect(s.thread_id)}
          >
            <div className="session-title">{s.title || '（空会话）'}</div>
            <div className="session-meta">
              <span className="session-time">{formatTime(s.updated_at)}</span>
              <button
                className="session-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(s.thread_id);
                }}
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
