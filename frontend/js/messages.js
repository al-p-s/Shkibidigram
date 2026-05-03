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

    let senderName = 'you';
    if (!isMine) {
        const chat = chats.find(c => c.id === currentChatId);
        const member = chat?.members.find(m => m.user.id === msg.sender_id);
        senderName = member?.user.display_name || member?.user.username || 'unknown';
    }

    const row = document.createElement('div');
    row.className = 'msg-row' + (isMine ? ' mine' : '');
    row.dataset.id = msg.id;

    row.innerHTML = `
        <div class="bubble">
            <div class="bubble-meta">
                <span class="bubble-sender">${senderName}</span>
                <span class="bubble-time">${time}</span>
                ${isMine ? `<span class="bubble-status" id="status-${msg.id}">·</span>` : ''}
            </div>
            <div class="bubble-content">${escHtml(msg.content || '')}</div>
            ${msg.is_edited ? '<div class="bubble-edited">edited</div>' : ''}
        </div>
    `;

    row.addEventListener('contextmenu', (e) => showMessageContextMenu(e, msg, isMine));
    wrap.appendChild(row);
}

function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

let contextMenu = null;

function showMessageContextMenu(e, msg, isMine) {
    e.preventDefault();
    removeContextMenu();

    const menu = document.createElement('div');
    menu.className = 'msg-context-menu';
    menu.style.top = `${e.clientY}px`;
    menu.style.left = `${e.clientX}px`;

    if (isMine) {
        const editBtn = document.createElement('div');
        editBtn.className = 'context-menu-item';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => {
            startEditMessage(msg);
            removeContextMenu();
        });
        menu.appendChild(editBtn);

        const deleteAll = document.createElement('div');
        deleteAll.className = 'context-menu-item danger';
        deleteAll.textContent = 'Delete for everyone';
        deleteAll.addEventListener('click', () => {
            deleteMessage(msg.id, 'all');
            removeContextMenu();
        });
        menu.appendChild(deleteAll);
    }

    const deleteMe = document.createElement('div');
    deleteMe.className = 'context-menu-item danger';
    deleteMe.textContent = 'Delete for me';
    deleteMe.addEventListener('click', () => {
        deleteMessage(msg.id, 'me');
        removeContextMenu();
    });
    menu.appendChild(deleteMe);

    const cancel = document.createElement('div');
    cancel.className = 'context-menu-item';
    cancel.textContent = 'Cancel';
    cancel.addEventListener('click', removeContextMenu);
    menu.appendChild(cancel);

    document.body.appendChild(menu);
    contextMenu = menu;

    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
        menu.style.left = `${e.clientX - rect.width}px`;
    }
    if (rect.bottom > window.innerHeight) {
        menu.style.top = `${e.clientY - rect.height}px`;
    }
}

function removeContextMenu() {
    if (contextMenu) {
        contextMenu.remove();
        contextMenu = null;
    }
}

document.addEventListener('click', removeContextMenu);

async function deleteMessage(msgId, mode) {
    try {
        if (mode === 'all') {
            await api.messages.deleteForAll(msgId);
        } else {
            await api.messages.deleteForMe(msgId);
        }
        const row = document.querySelector(`.msg-row[data-id="${msgId}"]`);
        if (row) row.remove();
    } catch (e) {
        console.error('Failed to delete message:', e);
    }
}

let editingMsgId = null;

function startEditMessage(msg) {
    editingMsgId = msg.id;
    const input = document.getElementById('msg-input');
    input.value = msg.content;
    input.focus();

    let indicator = document.getElementById('edit-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'edit-indicator';
        indicator.className = 'edit-indicator';
        document.getElementById('input-area').prepend(indicator);
    }
    indicator.innerHTML = `
        <span>Editing message</span>
        <button id="edit-cancel-btn">✕</button>
    `;
    indicator.style.display = 'flex';

    document.getElementById('edit-cancel-btn').addEventListener('click', cancelEdit);
}

function cancelEdit() {
    editingMsgId = null;
    document.getElementById('msg-input').value = '';
    const indicator = document.getElementById('edit-indicator');
    if (indicator) indicator.style.display = 'none';
}

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

    if (editingMsgId) {
        try {
            const updated = await api.messages.edit(editingMsgId, { content });
            const row = document.querySelector(`.msg-row[data-id="${editingMsgId}"]`);
            if (row) {
                row.querySelector('.bubble-content').textContent = updated.content;
                if (!row.querySelector('.bubble-edited')) {
                    const edited = document.createElement('div');
                    edited.className = 'bubble-edited';
                    edited.textContent = 'edited';
                    row.querySelector('.bubble').appendChild(edited);
                }
            }
            cancelEdit();
        } catch (e) {
            console.error('Failed to edit message:', e);
        }
        return;
    }

    input.value = '';
    input.style.height = 'auto';
    wsSend({ type: 'message.send', chat_id: currentChatId, content });
}
