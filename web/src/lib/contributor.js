// The contributor id is the only thing we persist in the browser. It is a random
// server-issued UUID tied to nothing but the consent record and the person's own
// contributions. Clearing site data makes them a new anonymous contributor.

import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

const KEY = 'awaaz.contributor'

export function loadContributor() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveContributor(c) {
  localStorage.setItem(KEY, JSON.stringify({ id: c.id, display_name: c.display_name ?? null }))
}

export function clearContributor() {
  localStorage.removeItem(KEY)
}

/** React hook: current contributor (or null), plus consent/forget actions. */
export function useContributor() {
  const [contributor, setContributor] = useState(() => loadContributor())
  const [profile, setProfile] = useState(null)
  const id = contributor?.id ?? null

  useEffect(() => {
    if (!id) return
    let alive = true
    api
      .getContributor(id)
      .then((p) => alive && setProfile(p))
      .catch((e) => {
        // The server no longer knows this id (e.g. database reset): start over.
        if (alive && e.status === 404) {
          clearContributor()
          setContributor(null)
        }
      })
    return () => {
      alive = false
    }
  }, [id])

  const consent = useCallback(async (form) => {
    const c = await api.createContributor(form)
    saveContributor(c)
    setContributor({ id: c.id, display_name: c.display_name })
    return c
  }, [])

  const forget = useCallback(() => {
    clearContributor()
    setContributor(null)
  }, [])

  const refresh = useCallback(() => {
    if (id) api.getContributor(id).then(setProfile).catch(() => {})
  }, [id])

  // Profile only makes sense for the current contributor; drop it when they forget themselves.
  return { contributor, profile: id && profile?.id === id ? profile : null, consent, forget, refresh }
}
