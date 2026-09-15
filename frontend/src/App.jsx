import { useState, useEffect, useCallback, useRef } from 'react';
import {
  streamChat,
  resumeChat,
  listSessions,
  getSession,
  deleteSession,
} from './api';
import Message from './components/Message';
import ToolCall from './components/ToolCall';
import InterruptBanner from './components/InterruptBanner';
import History from './components/History';

export default function App() {
  // items 里混合三种条目：user / assistant / tool
  const [items, setItems] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [interrupt, setInterrupt] = useState(null);
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [sessions, setSessions] = useState([]);
  const abortRef = useRef(null);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await listSessions());
    } catch (err) {
      console.warn('加载历史失败', err);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // 统一处理所有 SSE 事件（初次请求 + resume 复用同一套）
  const handleEvent = useCallback((event) => {
    switch (event.type) {
      case 'token':
        setItems((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last && last.type === 'assistant') {
            next[next.length - 1] = { ...last, content: last.content + event.content };
          } else {
            next.push({ type: 'assistant', content: event.content });
          }
          return next;
        });
        break;

      case 'tool_start':
        setItems((prev) => [
          ...prev,
          {
            type: 'tool',
            name: event.name,
            index: event.index,
            id: event.id,
            args: '',
            result: null,
            status: 'running',
          },
        ]);
        break;

      case 'tool_args':
        setItems((prev) => {
          const next = prev.slice();
          const i = next.findIndex(
            (it) => it.type === 'tool' && it.index === event.index && it.status === 'running'
          );
          if (i >= 0) next[i] = { ...next[i], args: next[i].args + event.args };
          return next;
        });
        break;

      case 'tool_result':
        setItems((prev) => {
          const next = prev.slice();
          let target = -1;
          // 优先按 tool_call_id 精确匹配
          if (event.id) {
            target = next.findIndex(
              (it) => it.type === 'tool' && it.status === 'running' && it.id === event.id
            );
          }
          // 没带 id 时退回按名字从后往前找
          if (target === -1) {
            for (let i = next.length - 1; i >= 0; i--) {
              const it = next[i];
              if (it.type === 'tool' && it.name === event.name && it.status === 'running') {
                target = i;
                break;
              }
            }
          }
          if (target >= 0) {
            next[target] = { ...next[target], result: event.content, status: 'done' };
          }
          return next;
        });
        break;

      case 'interrupt':
        setInterrupt(event.value);
        break;

      case 'done':
      default:
        break;
    }
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    setItems((prev) => [...prev, { type: 'user', content: text }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(text, threadId, handleEvent, controller.signal);
      loadSessions(); // 新会话落库后刷新左侧列表
    } catch (err) {
      if (err.name === 'AbortError') {
        setItems((prev) => [...prev, { type: 'assistant', content: '\n\n[已停止]' }]);
      } else {
        setItems((prev) => [
          ...prev,
          { type: 'assistant', content: `\n\n[错误] ${err.message}` },
        ]);
      }
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }, [input, sending, threadId, handleEvent, loadSessions]);

  const handleInterruptSubmit = useCallback(
    async (payload) => {
      setInterrupt(null);
      setSending(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await resumeChat(threadId, payload, handleEvent, controller.signal);
        loadSessions();
      } catch (err) {
        if (err.name === 'AbortError') {
          setItems((prev) => [...prev, { type: 'assistant', content: '\n\n[已停止]' }]);
        } else {
          setItems((prev) => [
            ...prev,
            { type: 'assistant', content: `\n\n[错误] ${err.message}` },
          ]);
        }
      } finally {
        abortRef.current = null;
        setSending(false);
      }
    },
    [threadId, handleEvent, loadSessions]
  );

  const newChat = useCallback(() => {
    setThreadId(crypto.randomUUID());
    setItems([]);
    setInterrupt(null);
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const openSession = useCallback(async (tid) => {
    try {
      const data = await getSession(tid);
      setThreadId(tid);
      setItems(data.messages.map((m) => ({ type: m.role, content: m.content })));
      setInterrupt(null);
    } catch (err) {
      console.warn('加载会话失败', err);
    }
  }, []);

  const removeSession = useCallback(
    async (tid) => {
      try {
        await deleteSession(tid);
        setSessions((prev) => prev.filter((s) => s.thread_id !== tid));
        if (tid === threadId) newChat();
      } catch (err) {
        console.warn('删除会话失败', err);
      }
    },
    [threadId, newChat]
  );

  return (
    <div className="app">
      <History
        sessions={sessions}
        currentThreadId={threadId}
        onSelect={openSession}
        onNew={newChat}
        onDelete={removeSession}
      />

      <div className="main">
        <header className="app-header">
          <h1>采购智能助手</h1>
          <span className="app-subtitle">基于 Harness 架构的采购领域专家智能助手</span>
        </header>

        <div className="message-list">
          {items.length === 0 && (
            <div className="empty-tip">
              输入问题开始对话，例如：查询所有库存预警物料
            </div>
          )}
          {items.map((m, i) =>
            m.type === 'tool' ? (
              <ToolCall key={i} tool={m} />
            ) : (
              <Message key={i} message={m} />
            )
          )}
        </div>

        {interrupt && (
          <InterruptBanner
            value={interrupt}
            onSubmit={handleInterruptSubmit}
            disabled={sending}
          />
        )}

        <div className="input-bar">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的问题...（Enter 发送，Shift+Enter 换行）"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          {sending ? (
            <button onClick={stop} style={{ background: '#e5484d' }}>
              停止
            </button>
          ) : (
            <button onClick={send} disabled={!input.trim()}>
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
