// Thin client for the FastAPI backend (`lowres-asr-api`). Vite proxies /api in dev.

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, init) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError('The API is not reachable. Start it with `lowres-asr-api`.', 0)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status)
  }
  if (res.status === 204) return null
  return res.json()
}

function json(body, method = 'POST') {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export const api = {
  // stateless text tools
  languages: () => request('/api/languages'),
  splitSentences: (lang, text, source = 'pasted') =>
    request('/api/text/sentences', json({ lang, text, source })),
  charset: (lang, text) => request('/api/text/charset', json({ lang, text })),
  normalize: (lang, text, asr = false) => request('/api/text/normalize', json({ lang, text, asr })),
  transcribe: (lang, file, model) => {
    const form = new FormData()
    form.append('lang', lang)
    form.append('file', file)
    if (model) form.append('model', model)
    return request('/api/transcribe', { method: 'POST', body: form })
  },

  // contribution platform
  createContributor: (body) => request('/api/contributors', json(body)),
  getContributor: (id) => request(`/api/contributors/${id}`),
  contributeSentences: (lang, sentences, source, contributorId) =>
    request('/api/sentences/contribute', json({ lang, sentences, source, contributor_id: contributorId ?? null })),
  nextSentences: (lang, contributorId, limit = 5) =>
    request(`/api/sentences/next?lang=${lang}&contributor_id=${contributorId}&limit=${limit}`),
  uploadRecording: (contributorId, sentenceId, file) => {
    const form = new FormData()
    form.append('contributor_id', contributorId)
    form.append('sentence_id', sentenceId)
    form.append('file', file)
    return request('/api/recordings', { method: 'POST', body: form })
  },
  getRecording: (id) => request(`/api/recordings/${id}`),
  audioUrl: (id) => `${BASE}/api/recordings/${id}/audio`,
  nextToValidate: (lang, contributorId, limit = 5) =>
    request(`/api/validations/next?lang=${lang}&contributor_id=${contributorId}&limit=${limit}`),
  validate: (recordingId, contributorId, verdict) =>
    request('/api/validations', json({ recording_id: recordingId, contributor_id: contributorId, verdict })),
  stats: (lang) => request(`/api/stats?lang=${lang}`),

  // Talk: the bot asks, the contributor answers
  promptCategories: () => request('/api/prompts/categories'),
  nextPrompts: (lang, contributorId, { category, kind, limit = 5 } = {}) => {
    const q = new URLSearchParams({ lang, contributor_id: contributorId, limit })
    if (category) q.set('category', category)
    if (kind) q.set('kind', kind)
    return request(`/api/prompts/next?${q}`)
  },
  submitResponse: (contributorId, promptId, lang, { text, file } = {}) => {
    const form = new FormData()
    form.append('contributor_id', contributorId)
    form.append('prompt_id', promptId)
    form.append('lang', lang)
    if (text) form.append('text', text)
    if (file) form.append('file', file)
    return request('/api/responses', { method: 'POST', body: form })
  },
}

/** Poll a recording until the worker has settled it (or we give up). */
export async function waitForRecording(id, { tries = 20, intervalMs = 750 } = {}) {
  for (let i = 0; i < tries; i++) {
    const rec = await api.getRecording(id)
    if (!['uploaded', 'processing'].includes(rec.status)) return rec
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  return api.getRecording(id)
}
