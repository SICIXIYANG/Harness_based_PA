export default function Message({ message }) {
  const isUser = message.type === 'user';
  const content = message.content;
  const loading = !isUser && !content;

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-role">{isUser ? '你' : 'Agent'}</div>
      <div className="message-content">
        {loading ? <span className="typing">思考中…</span> : content}
      </div>
    </div>
  );
}
