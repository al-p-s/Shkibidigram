let currentChatId = null;
let currentUser = null;
let chats = [];
let typingTimer = null;

async function initApp() {
  if (!localStorage.getItem('access_token')) {
    window.location.href = 'index.html';
    return;
  }

  try {
    currentUser = await api.users.me();
    document.getElementById('current-user').textContent = `@${currentUser.username}`;
  } catch {
    logout();
    return;
  }

  wsConnect();
  wsOn('message.new', onNewMessage);
  wsOn('presence', onPresence);
  wsOn('typing', onTyping);
  // call.* события регистрируются в call.js

  await loadChats();
}

async function loadChats() {
  chats = await api.chats.list();
  renderChatList();
}

function renderChatList() {
  const list = document.getElementById('chat-list');
  list.innerHTML = '';

  chats.forEach(chat => {
    const name = getChatName(chat);
    const initial = name[0].toUpperCase();
    const item = document.createElement('div');
    item.className = 'chat-item' + (chat.id === currentChatId ? ' active' : '');
    item.dataset.id = chat.id;
    item.innerHTML = `
      <div class="avatar" id="av-${chat.id}">
        ${initial}
        <div class="online-dot" id="dot-${chat.id}"></div>
      </div>
      <div class="chat-info">
        <div class="chat-name">${name}</div>
        <div class="chat-preview">${chat.type === 'direct' ? 'direct' : 'group · ' + chat.members.length}</div>
      </div>
    `;
    item.addEventListener('click', () => openChat(chat.id));
    list.appendChild(item);
  });
}

function getChatName(chat) {
  if (chat.type === 'group') return chat.name || 'Group';
  const other = chat.members.find(m => m.user.id !== currentUser.id);
  return other ? (other.user.display_name || other.user.username) : 'Chat';
}

async function openChat(chatId) {
  currentChatId = chatId;
  document.querySelectorAll('.chat-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === chatId);
  });

  const chat = chats.find(c => c.id === chatId);
  const name = getChatName(chat);

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('chat-view').style.display = 'flex';
  document.getElementById('chat-header-name').textContent = name;
  document.getElementById('chat-header-status').textContent = chat.type === 'group' ? `${chat.members.length} members` : '';

  // Кнопка звонка — только для direct чатов
  document.getElementById('btn-call').style.display = chat.type === 'direct' ? 'block' : 'none';

  await loadMessages(chatId);
}

function onPresence(event) {
  chats.forEach(chat => {
    if (chat.type === 'direct') {
      const other = chat.members.find(m => m.user.id === event.user_id);
      if (other) {
        const d = document.getElementById(`dot-${chat.id}`);
        if (d) d.classList.toggle('visible', event.online);
      }
    }
  });
}

function onTyping(event) {
  if (event.chat_id !== currentChatId) return;
  const el = document.getElementById('typing-indicator');
  el.classList.add('visible');
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => el.classList.remove('visible'), 2000);
}

function onNewMessage(event) {
  if (event.message.chat_id === currentChatId) {
    appendMessage(event.message, false);
    scrollBottom();
  }
}

// NEW CHAT MODAL
document.getElementById('new-chat-btn').addEventListener('click', () => {
  document.getElementById('new-chat-modal').classList.add('open');
});

document.getElementById('modal-cancel').addEventListener('click', () => {
  document.getElementById('new-chat-modal').classList.remove('open');
});

document.getElementById('modal-start').addEventListener('click', async () => {
  const username = document.getElementById('modal-username').value.trim();
  const err = document.getElementById('modal-msg');
  err.className = 'modal-msg';

  if (!username) return;

  try {
    const user = await api.users.search(username);
    if (!user) { err.textContent = 'User not found'; err.className = 'modal-msg show'; return; }

    const chat = await api.chats.create({ type: 'direct', member_ids: [user.id] });
    document.getElementById('new-chat-modal').classList.remove('open');
    document.getElementById('modal-username').value = '';

    await loadChats();
    await openChat(chat.id);
  } catch (e) {
    err.textContent = e.message;
    err.className = 'modal-msg show';
  }
});

function logout() {
  localStorage.clear();
  window.location.href = 'index.html';
}

document.getElementById('logout-btn').addEventListener('click', logout);

function scrollBottom() {
  const wrap = document.getElementById('messages-wrap');
  wrap.scrollTop = wrap.scrollHeight;
}

initApp();
