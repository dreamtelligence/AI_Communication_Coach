// Isolated browser regression fixture. No provider call, microphone or camera is used.
export default {
  createCallObject() {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    let frame = 0
    const draw = () => {
      context.fillStyle = '#332166'
      context.fillRect(0, 0, 640, 360)
      context.fillStyle = '#fff'
      context.font = '24px sans-serif'
      context.fillText('Isolierte Videoprüfung', 150, 175)
      context.fillRect((frame++ * 8) % 600, 240, 40, 40)
    }
    draw()
    const stream = canvas.captureStream(10)
    const track = stream.getVideoTracks()[0]
    const timer = setInterval(draw, 100)
    const handlers = new Map()
    let destroyed = false
    let mic = true
    let camera = true
    const emit = event => handlers.get(event)?.forEach(fn => fn({ action: event }))
    const participant = local => ({
      local, session_id: local ? 'local' : 'avatar', audio: local ? mic : true, video: local ? camera : true,
      tracks: { video: { state: 'playable', persistentTrack: track }, audio: {} },
    })
    const call = {
      on(event, fn) { handlers.set(event, [...(handlers.get(event) || []), fn]); return call },
      participants: () => ({ local: participant(true), avatar: participant(false) }),
      isDestroyed: () => destroyed,
      meetingState: () => 'joined-meeting',
      async join() { emit('joined-meeting') },
      setLocalAudio(value) { mic = value; emit('participant-updated') },
      setLocalVideo(value) { camera = value; emit('participant-updated') },
      async destroy() { destroyed = true; clearInterval(timer); stream.getTracks().forEach(t => t.stop()) },
    }
    window.__videoFixture = { freeze: () => clearInterval(timer), disconnect: () => emit('error'), call }
    return call
  },
}
