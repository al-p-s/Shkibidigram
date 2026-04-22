async function loadMessages(chatId) {
  const wrap = document.getElementById('messages-wrap');
  wrap.innerHTML = '';

  try {
    const msgs = await api.messages.list(chatId);
    msgs.reverse().forEach(m => appendMessage(m, true));
    scrollBottom();
  } catch {}
}

function appendMessage(msg, initial = false) {
  const wrap = document.getElementById('messages-wrap');
  const isMine = msg.sender_id === currentUser.id;

  const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const row = document.createElement('div');
  row.className = 'msg-row' + (isMine ? ' mine' : '');
  row.dataset.id = msg.id;

  row.innerHTML = `
    <div class="bubble">
      <div class="bubble-meta">
        <span class="bubble-sender">${isMine ? 'you' : ''}</span>
        <span class="bubble-time">${time}</span>
        ${isMine ? `<span class="bubble-status" id="status-${msg.id}">·</span>` : ''}
      </div>
      <div class="bubble-content">${escHtml(msg.content || '')}</div>
      ${msg.is_edited ? '<div class="bubble-edited">edited</div>' : ''}
    </div>
  `;

  wrap.appendChild(row);
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// SEND
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

input.addEventListener('input', () => {
  if (currentChatId) {
    wsSend({ type: 'typing', chat_id: currentChatId });
  }
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
});

sendBtn.addEventListener('click', sendMessage);

async function sendMessage() {
  const content = input.value.trim();
  if (!content || !currentChatId) return;

  input.value = '';
  input.style.height = 'auto';

  wsSend({ type: 'message.send', chat_id: currentChatId, content });
}
