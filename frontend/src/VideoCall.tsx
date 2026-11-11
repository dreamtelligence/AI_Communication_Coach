import { useEffect, useRef, useState } from 'react'
import type { DailyCall, DailyParticipant } from '@daily-co/daily-js'
import { Mic, MicOff, Video, VideoOff, Volume2 } from 'lucide-react'

export function releaseSession(conversationId: string, sessionToken: string): Promise<Response> {
  return fetch(`/api/session/${encodeURIComponent(conversationId)}/end`, {
    method: 'POST', headers: { 'X-Session-Token': sessionToken }, keepalive: true,
  })
}

interface Props {
  url: string
  conversationId: string
  sessionToken: string
  name: string
  onError: (message: string) => void
}

export default function VideoCall({ url, conversationId, sessionToken, name, onError }: Props) {
  const instance = useRef<DailyCall | null>(null)
  const avatar = useRef<HTMLVideoElement>(null)
  const self = useRef<HTMLVideoElement>(null)
  const audio = useRef<HTMLAudioElement>(null)
  const lastFrame = useRef(0)
  const releaseTimer = useRef<number>()
  const [remote, setRemote] = useState<DailyParticipant>()
  const [local, setLocal] = useState<DailyParticipant>()
  const [joined, setJoined] = useState(false)
  const [error, setError] = useState('')
  const [soundBlocked, setSoundBlocked] = useState(false)

  useEffect(() => {
    window.clearTimeout(releaseTimer.current)
    let disposed = false
    let call: DailyCall | undefined
    const release = () => { void releaseSession(conversationId, sessionToken).catch(() => {}) }
    const fail = (message: string) => {
      if (disposed) return
      setError(message)
      setJoined(false)
      release()
      void call?.destroy().catch(() => {})
      onError(message)
    }
    // The async import also lets React StrictMode dispose its first effect before media is acquired.
    void import('@daily-co/daily-js').then(async ({ default: Daily }) => {
      if (disposed) return
      call = Daily.createCallObject({ dailyConfig: { avoidEval: true } })
      instance.current = call
      const sync = () => {
        if (disposed || !call || call.isDestroyed()) return
        const participants = Object.values(call.participants())
        setLocal(participants.find(p => p.local))
        setRemote(participants.find(p => !p.local && p.tracks.video.persistentTrack))
      }
      call.on('participant-joined', sync).on('participant-updated', sync).on('participant-left', sync)
      call.on('joined-meeting', () => { if (!disposed) { setJoined(true); sync() } })
      call.on('left-meeting', () => { if (!disposed) setJoined(false); release() })
      call.on('error', () => fail('Die Videoverbindung wurde unterbrochen. Bitte starte ein neues Gespräch.'))
      call.on('camera-error', event => {
        if (!disposed) setError(event?.errorMsg.audioOk
          ? 'Die Kamera ist nicht verfügbar. Du kannst ohne Kamera weiterreden.'
          : 'Mikrofon nicht verfügbar. Bitte erlaube den Zugriff und starte erneut.')
        if (!event?.errorMsg.audioOk) fail('Mikrofon nicht verfügbar. Bitte erlaube den Zugriff und starte erneut.')
      })
      await call.join({ url, userName: 'Teilnehmer/in' })
    }).catch(() => fail('Die Videoverbindung konnte nicht aufgebaut werden. Bitte prüfe Kamera und Mikrofon und starte erneut.'))

    // Do not use visibilitychange: briefly switching apps must not immediately end a conversation.
    window.addEventListener('pagehide', release)
    return () => {
      disposed = true
      window.removeEventListener('pagehide', release)
      instance.current = null
      if (call && !call.isDestroyed()) void call.destroy().catch(() => {})
      // StrictMode immediately replays mount effects; cancel this deferred release on that replay.
      releaseTimer.current = window.setTimeout(release, 0)
    }
  }, [url, conversationId, sessionToken, onError])

  const remoteVideo = remote?.tracks.video.persistentTrack
  const remoteAudio = remote?.tracks.audio.persistentTrack
  const localVideo = local?.tracks.video.persistentTrack

  useEffect(() => {
    const element = avatar.current
    if (!element || !remoteVideo) return
    element.srcObject = new MediaStream([remoteVideo])
    void element.play().catch(() => {})
    let frameId = 0
    let fallbackTimer: number | undefined
    const frame = () => {
      lastFrame.current = Date.now()
      frameId = element.requestVideoFrameCallback(frame)
    }
    if (typeof element.requestVideoFrameCallback === 'function') {
      frameId = element.requestVideoFrameCallback(frame)
    } else {
      let previousTime = element.currentTime
      fallbackTimer = window.setInterval(() => {
        if (element.currentTime !== previousTime) lastFrame.current = Date.now()
        previousTime = element.currentTime
      }, 1000)
    }
    return () => {
      if (frameId) element.cancelVideoFrameCallback(frameId)
      window.clearInterval(fallbackTimer)
      element.srcObject = null
      lastFrame.current = 0
    }
  }, [remoteVideo])

  useEffect(() => {
    if (!self.current) return
    self.current.srcObject = localVideo ? new MediaStream([localVideo]) : null
    if (localVideo) void self.current.play().catch(() => {})
  }, [localVideo])

  useEffect(() => {
    const element = audio.current
    if (!element || !remoteAudio) return
    element.srcObject = new MediaStream([remoteAudio])
    void element.play().then(() => setSoundBlocked(false)).catch(() => setSoundBlocked(true))
    return () => { element.srcObject = null }
  }, [remoteAudio])

  useEffect(() => {
    if (!joined) return
    let disposed = false
    const heartbeat = async () => {
      const video = avatar.current
      // Only decoded video frames renew the lease, not a running JS timer in a stuck tab.
      if (!video || video.readyState < 2 || Date.now() - lastFrame.current > 20_000) return
      try {
        const response = await fetch(`/api/session/${encodeURIComponent(conversationId)}/heartbeat`, {
          method: 'POST', headers: { 'X-Session-Token': sessionToken },
        })
        if ([403, 410].includes(response.status) && !disposed) {
          setError('Das Gespräch wurde wegen einer unterbrochenen Verbindung freigegeben. Bitte starte neu.')
          setJoined(false)
          void instance.current?.destroy().catch(() => {})
          onError('Die Videoverbindung ist abgelaufen. Bitte starte ein neues Gespräch.')
        }
      } catch { /* The server watchdog releases the lease if the connection does not recover. */ }
    }
    const timer = window.setInterval(() => { void heartbeat() }, 15_000)
    return () => { disposed = true; window.clearInterval(timer) }
  }, [joined, conversationId, sessionToken, onError])

  const micOn = local?.audio ?? false
  const cameraOn = local?.video ?? false
  return (
    <div className="video-call">
      <video ref={avatar} className="avatar-video" autoPlay playsInline muted aria-label={`KI-Video: ${name}`} />
      <audio ref={audio} autoPlay />
      {!remoteVideo && <div className="video-wait" role="status">{error || 'Videoverbindung wird aufgebaut …'}</div>}
      <div className="self-preview" aria-label="Deine Kameravorschau">
        <video ref={self} autoPlay playsInline muted hidden={!cameraOn} />
        {!cameraOn && <VideoOff size={22} aria-hidden="true" />}
        <span>Du</span>
      </div>
      {error && remoteVideo && <p className="video-message" role="alert">{error}</p>}
      <div className="video-controls">
        <button className="btn" disabled={!joined} aria-label={micOn ? 'Mikrofon ausschalten' : 'Mikrofon einschalten'} aria-pressed={micOn}
          onClick={() => instance.current?.setLocalAudio(!micOn)}>{micOn ? <Mic /> : <MicOff />}</button>
        <button className="btn" disabled={!joined} aria-label={cameraOn ? 'Kamera ausschalten' : 'Kamera einschalten'} aria-pressed={cameraOn}
          onClick={() => instance.current?.setLocalVideo(!cameraOn)}>{cameraOn ? <Video /> : <VideoOff />}</button>
        {soundBlocked && <button className="btn" onClick={() => {
          void audio.current?.play().then(() => setSoundBlocked(false)).catch(() => setError('Ton ist blockiert. Bitte prüfe deine Browsereinstellungen.'))
        }}><Volume2 /> Ton aktivieren</button>}
      </div>
    </div>
  )
}
