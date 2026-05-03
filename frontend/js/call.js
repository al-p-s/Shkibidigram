// ─── call.js ────────────────────────────────────────────────────────────────

const ICE_SERVERS = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
  ],
};

let callState = {
  active: false,
  roomId: null,
  peerId: null,
  remotePeerId: null,
  callWs: null,
  pc: null,
  localStream: null,
  role: null,           // "caller" | "callee"
  incoming: null,
  videoEnabled: false,
};

let iceCandidateBuffer = [];

wsOn("call.incoming", onCallIncoming);
wsOn("call.accepted", onCallAccepted);
wsOn("call.rejected", onCallRejected);
wsOn("call.ended",    onCallEnded);

// ═══════════════════════════════════════════════════════════════════════════
// ИНИЦИАЦИЯ ЗВОНКА
// ═══════════════════════════════════════════════════════════════════════════

async function startCall() {
  if (!currentChatId) return;

  const chat = chats.find(c => c.id === currentChatId);
  if (!chat || chat.type !== "direct") return;

  const callee = chat.members.find(m => m.user.id !== currentUser.id);
  if (!callee) return;

  const res = await fetch("/webrtc/rooms", {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  const { roomId } = await res.json();

  callState.roomId = roomId;
  callState.role = "caller";

  wsSend({
    type: "call.invite",
    chat_id: currentChatId,
    room_id: roomId,
    callee_id: callee.user.id,
    caller_name: currentUser.display_name || currentUser.username,
  });

  openCallWindow({ waitingForAccept: true, remoteName: callee.user.display_name || callee.user.username });
  await connectToRoom(roomId);
  // Caller вошёл первым — ждём peer-joined от callee, offer делаем там
}

// ═══════════════════════════════════════════════════════════════════════════
// ВХОДЯЩИЙ ЗВОНОК
// ═══════════════════════════════════════════════════════════════════════════

function onCallIncoming(event) {
  callState.incoming = event;
  showIncomingNotification(event);
}

async function acceptCall() {
  const event = callState.incoming;
  if (!event) return;

  hideIncomingNotification();

  callState.roomId  = event.room_id;
  callState.role    = "callee";
  callState.incoming = null;

  wsSend({
    type: "call.accept",
    room_id: event.room_id,
    caller_id: event.caller_id,
  });

  openCallWindow({ waitingForAccept: false, remoteName: event.caller_name });
  await connectToRoom(event.room_id);
  // Callee вошёл вторым — room-state придёт с caller в списке,
  // caller получит peer-joined и сделает offer
}

function rejectCall() {
  const event = callState.incoming;
  if (!event) return;

  hideIncomingNotification();
  callState.incoming = null;

  wsSend({
    type: "call.reject",
    room_id: event.room_id,
    caller_id: event.caller_id,
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// ОТВЕТЫ ЗВОНЯЩЕМУ
// ═══════════════════════════════════════════════════════════════════════════

async function onCallAccepted(event) {
  hideWaitingLabel();
  // Callee принял — он сейчас подключается к комнате.
  // Когда подключится — мы получим peer-joined и сделаем offer там.
}

function onCallRejected(event) {
  showCallStatus("Звонок отклонён");
  setTimeout(hangupCall, 2000);
}

function onCallEnded(event) {
  showCallStatus("Звонок завершён");
  setTimeout(closeCallWindow, 1500);
  cleanupCall();
}

// ═══════════════════════════════════════════════════════════════════════════
// SIGNALING WS
// ═══════════════════════════════════════════════════════════════════════════

async function connectToRoom(roomId) {
  return new Promise((resolve) => {
    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    callState.callWs = new WebSocket(`${wsProto}//${location.host}/webrtc/ws/${roomId}`);
    callState.callWs.onopen    = () => resolve();
    callState.callWs.onmessage = (e) => handleSignalingMessage(JSON.parse(e.data));
    callState.callWs.onerror   = () => callState.callWs.close();
    callState.callWs.onclose   = () => { if (callState.active) cleanupCall(); };
  });
}

function sigSend(data) {
  if (callState.callWs && callState.callWs.readyState === WebSocket.OPEN) {
    callState.callWs.send(JSON.stringify(data));
  }
}

async function handleSignalingMessage(msg) {
  switch (msg.type) {

    // Сервер сообщает нам наш id
    case "self-id":
      callState.peerId = msg.peerId;
      break;

    // Сервер сообщает нам кто УЖЕ был в комнате (только нам, при входе)
    case "room-state":
      if (msg.peers.length > 0) {
        // В комнате уже есть участник — мы вошли вторыми
        callState.remotePeerId = msg.peers[0];
        callState.active = true;
        // Caller делает offer когда видит что callee уже в комнате
        if (callState.role === "caller") await initiateOffer();
      }
      // peers пустой — мы первые, просто ждём peer-joined
      break;

    // Сервер сообщает всем остальным что кто-то вошёл (не нам самим)
    case "peer-joined":
      callState.remotePeerId = msg.peerId;
      callState.active = true;
      // Мы были первыми, вошёл второй участник — caller делает offer
      if (callState.role === "caller") await initiateOffer();
      break;

    case "offer":
      callState.remotePeerId = msg.fromId;
      await handleOffer(msg.sdp);
      break;

    case "answer":
      await callState.pc.setRemoteDescription(
        new RTCSessionDescription({ type: "answer", sdp: msg.sdp })
      );
      await flushIceCandidates();
      break;

    case "ice-candidate":
      if (callState.pc && callState.pc.remoteDescription) {
        await callState.pc.addIceCandidate(new RTCIceCandidate(msg.candidate)).catch(() => {});
      } else {
        iceCandidateBuffer.push(msg.candidate);
      }
      break;

    case "peer-left":
      onCallEnded({});
      break;
  }
}

async function flushIceCandidates() {
  for (const candidate of iceCandidateBuffer) {
    await callState.pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {});
  }
  iceCandidateBuffer = [];
}

// ═══════════════════════════════════════════════════════════════════════════
// WebRTC
// ═══════════════════════════════════════════════════════════════════════════

async function ensureLocalStream(video = false) {
  if (callState.localStream) return;
  callState.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video });
  const localVideo = document.getElementById("call-local-video");
  if (localVideo) localVideo.srcObject = callState.localStream;
}

function createPeerConnection() {
  callState.pc = new RTCPeerConnection(ICE_SERVERS);

  callState.localStream.getTracks().forEach(t => callState.pc.addTrack(t, callState.localStream));

  callState.pc.ontrack = (e) => {
    const remoteVideo = document.getElementById("call-remote-video");
    if (remoteVideo) remoteVideo.srcObject = e.streams[0];
    showCallStatus("Подключено");
  };

  callState.pc.onicecandidate = (e) => {
    if (e.candidate) {
      sigSend({ type: "ice-candidate", candidate: e.candidate, targetId: callState.remotePeerId });
    }
  };

  callState.pc.onconnectionstatechange = () => {
    const state = callState.pc.connectionState;
    if (state === "failed" || state === "disconnected") showCallStatus("Потеря соединения...");
  };
}

async function initiateOffer() {
  await ensureLocalStream(true);
  createPeerConnection();
  const offer = await callState.pc.createOffer();
  await callState.pc.setLocalDescription(offer);
  sigSend({ type: "offer", sdp: offer.sdp, targetId: callState.remotePeerId });
}

async function handleOffer(sdp) {
  await ensureLocalStream(true);
  createPeerConnection();
  await callState.pc.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp }));
  await flushIceCandidates();
  const answer = await callState.pc.createAnswer();
  await callState.pc.setLocalDescription(answer);
  sigSend({ type: "answer", sdp: answer.sdp, targetId: callState.remotePeerId });
}

// ═══════════════════════════════════════════════════════════════════════════
// УПРАВЛЕНИЕ
// ═══════════════════════════════════════════════════════════════════════════

let _micEnabled = true;
let _videoEnabled = false;

function toggleMic() {
  if (!callState.localStream) return;
  const track = callState.localStream.getAudioTracks()[0];
  if (!track) return;
  _micEnabled = !_micEnabled;
  track.enabled = _micEnabled;
  document.getElementById("call-btn-mic").textContent = _micEnabled ? "MIC: ON" : "MIC: OFF";
}

async function toggleVideo() {
  _videoEnabled = !_videoEnabled;
  callState.videoEnabled = _videoEnabled;

  if (!callState.localStream) {
    await ensureLocalStream(_videoEnabled);
    if (callState.pc) {
      callState.localStream.getTracks().forEach(t => callState.pc.addTrack(t, callState.localStream));
    }
  } else {
    const videoTracks = callState.localStream.getVideoTracks();
    if (_videoEnabled && videoTracks.length === 0) {
      const vs = await navigator.mediaDevices.getUserMedia({ video: true });
      const vTrack = vs.getVideoTracks()[0];
      callState.localStream.addTrack(vTrack);
      if (callState.pc) callState.pc.addTrack(vTrack, callState.localStream);
      document.getElementById("call-local-video").srcObject = callState.localStream;
    } else {
      videoTracks.forEach(t => { t.enabled = _videoEnabled; });
    }
  }

  document.getElementById("call-btn-video").textContent = _videoEnabled ? "CAM: ON" : "CAM: OFF";
  document.getElementById("call-local-video").style.display = _videoEnabled ? "block" : "none";
}

function hangupCall() {
  if (callState.remotePeerId && callState.roomId) {
    wsSend({ type: "call.end", room_id: callState.roomId, peer_id: callState.remotePeerId });
  }
  closeCallWindow();
  cleanupCall();
}

function cleanupCall() {
  if (callState.pc) callState.pc.close();
  if (callState.callWs) callState.callWs.close();
  if (callState.localStream) callState.localStream.getTracks().forEach(t => t.stop());
  callState = {
    active: false, roomId: null, peerId: null, remotePeerId: null,
    callWs: null, pc: null, localStream: null, role: null, incoming: null,
    videoEnabled: false,
  };
  iceCandidateBuffer = [];
  _micEnabled = true;
  _videoEnabled = false;
}

// ═══════════════════════════════════════════════════════════════════════════
// UI
// ═══════════════════════════════════════════════════════════════════════════

function openCallWindow({ remoteName = "", waitingForAccept = false }) {
  document.getElementById("call-remote-name").textContent = remoteName;
  document.getElementById("call-status").textContent = waitingForAccept ? "Вызов..." : "Соединение...";
  document.getElementById("call-local-video").style.display = "none";
  document.getElementById("call-btn-mic").textContent = "MIC: ON";
  document.getElementById("call-btn-video").textContent = "CAM: OFF";
  document.getElementById("call-overlay").classList.add("open");
}

function closeCallWindow() {
  document.getElementById("call-overlay").classList.remove("open");
}

function hideWaitingLabel() {
  document.getElementById("call-status").textContent = "Соединение...";
}

function showCallStatus(text) {
  document.getElementById("call-status").textContent = text;
}

function showIncomingNotification(event) {
  document.getElementById("incoming-caller-name").textContent = event.caller_name || "Неизвестный";
  document.getElementById("incoming-overlay").classList.add("open");
}

function hideIncomingNotification() {
  document.getElementById("incoming-overlay").classList.remove("open");
}
