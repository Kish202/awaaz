import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/**
 * Microphone recording with MediaRecorder.
 *
 *   const rec = useRecorder({ maxSeconds: 15 })
 *   rec.toggle()            start, or stop if recording
 *   rec.recording           boolean
 *   rec.elapsed             seconds, updated 10x/s while recording
 *   rec.blob / rec.url      the finished clip (null until stopped)
 *   rec.file()              a File ready for upload (webm or m4a)
 *   rec.reset()             drop the clip
 *   rec.error               'denied' when the browser refused the microphone
 */
export function useRecorder({ maxSeconds = 15 } = {}) {
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [blob, setBlob] = useState(null)
  const [error, setError] = useState(null)
  const recorder = useRef(null)
  const chunks = useRef([])
  const timer = useRef(null)

  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])
  useEffect(() => () => url && URL.revokeObjectURL(url), [url])
  useEffect(() => () => clearInterval(timer.current), [])

  const reset = useCallback(() => {
    setBlob(null)
    setElapsed(0)
    setError(null)
  }, [])

  const toggle = useCallback(async () => {
    if (recording) {
      recorder.current?.stop()
      return
    }
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((m) => MediaRecorder.isTypeSupported(m))
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      chunks.current = []
      rec.ondataavailable = (e) => chunks.current.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        setBlob(new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' }))
        setRecording(false)
      }
      rec.start()
      recorder.current = rec
      setBlob(null)
      setRecording(true)
      setElapsed(0)
      const t0 = Date.now()
      timer.current = setInterval(() => {
        const s = (Date.now() - t0) / 1000
        setElapsed(s)
        if (s >= maxSeconds) rec.stop()
      }, 100)
    } catch {
      setError('denied')
    }
  }, [recording, maxSeconds])

  const file = useCallback(() => {
    if (!blob) return null
    const ext = blob.type.includes('mp4') ? 'm4a' : 'webm'
    return new File([blob], `clip.${ext}`, { type: blob.type })
  }, [blob])

  return { recording, elapsed, blob, url, error, toggle, reset, file, maxSeconds }
}
