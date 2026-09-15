// 后端接口封装：SSE 流式对话 + 历史 + 恢复中断。
// 后端是 POST + SSE，浏览器自带 EventSource 只支持 GET，所以用 fetch 手动读流。

const API_BASE = 'http://localhost:8000';

// 发送一条消息，流式回调每个 SSE 事件。
// onEvent(event) 会收到 { type, ... } 对象，type 可能是 token/tool_start/interrupt/done 等。
export function streamChat(message, threadId, onEvent, signal) {
  return fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`请求失败 ${res.status}: ${text}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE 事件之间用 \n\n 分隔
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = raw.trim();
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload));
        } catch (err) {
          console.warn('解析 SSE 事件失败:', payload, err);
        }
      }
    }
  });
}

// 恢复一个被中断的对话（第 1 层补数据 / 第 2 层审批）。
export function resumeChat(threadId, resumePayload, onEvent, signal) {
  return fetch(`${API_BASE}/api/chat/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId, resume: resumePayload }),
    signal,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`恢复失败 ${res.status}: ${text}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = raw.trim();
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload));
        } catch (err) {
          console.warn('解析 SSE 事件失败:', payload, err);
        }
      }
    }
  });
}

// 历史接口（后面历史列表小步用）。
export async function listSessions() {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error(`获取会话列表失败 ${res.status}`);
  const data = await res.json();
  return data.sessions || [];
}

export async function getSession(threadId) {
  const res = await fetch(`${API_BASE}/api/history/${threadId}`);
  if (!res.ok) throw new Error(`获取会话失败 ${res.status}`);
  return res.json();
}

export async function deleteSession(threadId) {
  const res = await fetch(`${API_BASE}/api/history/${threadId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`删除会话失败 ${res.status}`);
  return res.json();
}
