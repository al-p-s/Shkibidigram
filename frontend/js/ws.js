let socket = null;
let reconnectTimer = null;
const handlers = {};

function wsOn(type, fn) { handlers[type] = fn; }

function wsConnect() {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  socket = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

  socket.onopen = () => {
    console.log('[ws] connected');
    clearTimeout(reconnectTimer);
  };

  socket.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      const handler = handlers[event.type];
      if (handler) handler(event);
    } catch {}
  };

  socket.onclose = () => {
    console.log('[ws] disconnected, reconnecting...');
    reconnectTimer = setTimeout(wsConnect, 3000);
  };

  socket.onerror = () => socket.close();
}

function wsSend(payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}
