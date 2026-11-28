import { getApiBase, getMainAccessToken } from '../../cloudSync'

export interface AiExchange {
  prompt: string
  answer: string
}

export class AiSearchError extends Error {
  constructor(readonly code: string) {
    super(code)
  }
}

const interrupted = () => new AiSearchError('workspace_ai_interrupted')

/** 发起一次受控流式请求；仅在收到 done 后视为成功，不自动重试付费调用。 */
export async function streamAiAnswer(
  token: string, prompt: string, previous: AiExchange | null, signal: AbortSignal,
  onText: (text: string) => void,
): Promise<void> {
  const response = await fetch(getApiBase() + '/workspace/ai/stream', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(previous ? { prompt, previous } : { prompt }),
    cache: 'no-store',
    redirect: 'error',
    signal,
  })
  if (getMainAccessToken() !== token) {
    await response.body?.cancel()
    throw new AiSearchError('account_changed')
  }
  if (!response.ok) {
    await response.body?.cancel()
    const code = ({
      401: 'workspace_ai_session_invalid',
      402: 'workspace_ai_insufficient_quota',
      403: 'workspace_ai_model_denied',
      413: 'workspace_ai_invalid_prompt',
      422: 'workspace_ai_invalid_prompt',
      429: 'workspace_ai_rate_limited',
    } as Record<number, string>)[response.status]
    throw new AiSearchError(code || 'workspace_ai_unavailable')
  }
  if (!response.body || !response.headers.get('content-type')?.match(/^text\/event-stream(?:\s*;|$)/i)) {
    await response.body?.cancel()
    throw new AiSearchError('workspace_ai_unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let pending = ''
  try {
    // 网络分块不等于事件边界；按服务端空行分帧，仅消费定义过的纯文本事件。
    while (!signal.aborted) {
      const { value, done } = await reader.read()
      if (getMainAccessToken() !== token) throw new AiSearchError('account_changed')
      if (signal.aborted) throw interrupted()
      if (done) break
      pending += decoder.decode(value, { stream: true })
      let boundary = /\r?\n\r?\n/.exec(pending)
      while (boundary) {
        if (boundary.index > 128 * 1024) throw interrupted()
        const frame = pending.slice(0, boundary.index)
        pending = pending.slice(boundary.index + boundary[0].length)
        const lines = frame.split(/\r?\n/)
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim()
        const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
        if (event === 'error' || event === 'delta') {
          const payload = JSON.parse(data)
          if (event === 'error') throw new AiSearchError(typeof payload?.code === 'string' ? payload.code : '')
          if (typeof payload?.text !== 'string') throw interrupted()
          onText(payload.text)
        } else if (event === 'done') {
          return
        }
        boundary = /\r?\n\r?\n/.exec(pending)
      }
      if (pending.length > 128 * 1024) throw interrupted()
    }
    throw interrupted()
  } finally {
    await reader.cancel().catch(() => undefined) // 已取消或断开的流无需二次报错。
    reader.releaseLock()
  }
}
