async function loadMessages(chatId) {
    const wrap = document.getElementById('messages-wrap');
    wrap.innerHTML = '';

    try {
        const msgs = await api.messages.list(chatId);
        msgs.reverse();

        let lastDate = null;
        msgs.forEach(m => {
            const msgDate = new Date(m.created_at).toDateString();
            if (msgDate !== lastDate) {
                appendDateSeparator(getDateLabel(m.created_at));
                lastDate = msgDate;
            }
            appendMessage(m, true);
        });

        scrollBottom();

        msgs.forEach(m => {
            if (m.sender_id !== currentUser.id) {
                const alreadyRead = m.statuses?.some(s =>
                    s.user_id === currentUser.id && s.status === 'read'
                );
                if (!alreadyRead) {
                    wsSend({ type: 'message.read', message_id: m.id });
                }
            }
        });
    } catch {}
}

function getDateLabel(date) {
    const d = new Date(date);

    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

function appendDateSeparator(dateStr) {
    const wrap = document.getElementById('messages-wrap');
    const sep = document.createElement('div');
    sep.className = 'date-separator';
    sep.innerHTML = `<span>${dateStr}</span>`;
    wrap.appendChild(sep);
}

function appendMessage(msg, initial = false) {
    const wrap = document.getElementById('messages-wrap');
    const isMine = msg.sender_id === currentUser.id;
    const isRead = msg.statuses?.some(s => s.status === 'read');

    const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let senderName = 'you';
    if (!isMine) {
        const chat = chats.find(c => c.id === currentChatId);
        const member = chat?.members.find(m => m.user.id === msg.sender_id);
        senderName = member?.user.display_name || member?.user.username || 'unknown';
    }

    // Блок цитаты если это ответ
    let replyBlock = '';
    if (msg.reply_to_id) {
        const repliedRow = document.querySelector(`.msg-row[data-id="${msg.reply_to_id}"]`);
        const repliedMsg = repliedRow?._msgData;

        const repliedContent = repliedMsg?.content || msg.reply_to_content || '...';

        let repliedSender = '...';
        if (repliedMsg) {
            repliedSender = repliedMsg.sender_id === currentUser.id
                ? 'you'
                : (() => {
                    const chat = chats.find(c => c.id === currentChatId);
                    const member = chat?.members.find(m => m.user.id === repliedMsg.sender_id);
                    return member?.user.display_name || member?.user.username || 'unknown';
                })();
        } else if (msg.reply_to_sender_id) {
            if (msg.reply_to_sender_id === currentUser.id) {
                repliedSender = 'you';
            } else {
                const chat = chats.find(c => c.id === currentChatId);
                const member = chat?.members.find(m => m.user.id === msg.reply_to_sender_id);
                repliedSender = member?.user.display_name || member?.user.username || 'unknown';
            }
        }

        replyBlock = `
            <div class="bubble-reply" data-reply-id="${msg.reply_to_id}">
                <span class="bubble-reply-sender">${escHtml(repliedSender)}</span>
                <span class="bubble-reply-text">${escHtml(repliedContent.substring(0, 80))}${repliedContent.length > 80 ? '...' : ''}</span>
            </div>
        `;
    }

    const row = document.createElement('div');
    row.className = 'msg-row' + (isMine ? ' mine' : '');
    row.dataset.id = msg.id;

    row.innerHTML = `
        <div class="bubble">
            ${replyBlock}
            <div class="bubble-meta">
                <span class="bubble-sender">${senderName}</span>
                <span class="bubble-time">${time}</span>
                ${isMine ? `<span class="bubble-status ${isRead ? 'read' : ''}" id="status-${msg.id}">${isRead ? '✓✓' : '✓'}</span>` : ''}
            </div>
            <div class="bubble-content">${escHtml(msg.content || '')}</div>
            ${msg.is_edited ? '<div class="bubble-edited">edited</div>' : ''}
        </div>
    `;

    // Клик по цитате — скролл к оригиналу
    const replyEl = row.querySelector('.bubble-reply');
    if (replyEl) {
        replyEl.addEventListener('click', () => scrollToMessage(msg.reply_to_id));
    }

    row.addEventListener('contextmenu', (e) => showMessageContextMenu(e, msg, isMine));
    row._msgData = msg;
    wrap.appendChild(row);
}

function scrollToMessage(msgId) {
    const target = document.querySelector(`.msg-row[data-id="${msgId}"]`);
    if (!target) return;

    target.scrollIntoView({ behavior: 'smooth', block: 'center' });

    target.classList.add('highlighted');
    setTimeout(() => target.classList.remove('highlighted'), 1500);
}

function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

let contextMenu = null;

function showMessageContextMenu(e, msg, isMine) {
    e.preventDefault();
    removeContextMenu();

    const row = document.querySelector(`.msg-row[data-id="${msg.id}"]`);
    const actualMsg = row?._msgData || msg;

    const menu = document.createElement('div');
    menu.className = 'msg-context-menu';
    menu.style.top = `${e.clientY}px`;
    menu.style.left = `${e.clientX}px`;

    // Reply — для всех сообщений
    const replyBtn = document.createElement('div');
    replyBtn.className = 'context-menu-item';
    replyBtn.textContent = 'Reply';
    replyBtn.addEventListener('click', () => {
        startReply(actualMsg);
        removeContextMenu();
    });
    menu.appendChild(replyBtn);

    if (isMine) {
        const msgAge = (Date.now() - new Date(msg.created_at).getTime()) / 1000;
        if (msgAge < 86400) {
            const editBtn = document.createElement('div');
            editBtn.className = 'context-menu-item';
            editBtn.textContent = 'Edit';
            editBtn.addEventListener('click', () => {
                startEditMessage(msg);
                removeContextMenu();
            });
            menu.appendChild(editBtn);
        }

        const readBy = actualMsg.statuses?.filter(s => s.status === 'read') || [];

        const divider = document.createElement('div');
        divider.className = 'context-menu-divider';
        menu.appendChild(divider);

        const label = document.createElement('div');
        label.className = 'context-menu-label';
        label.textContent = readBy.length > 0 ? 'Read by:' : 'Not read yet';
        menu.appendChild(label);

        if (readBy.length > 0) {
            const chat = chats.find(c => c.id === currentChatId);
            readBy.forEach(s => {
                const member = chat?.members.find(m => m.user.id === s.user_id);
                if (!member) return;
                const name = member.user.display_name || member.user.username;
                const readerRow = document.createElement('div');
                readerRow.className = 'context-menu-item context-menu-reader';
                readerRow.textContent = name;
                menu.appendChild(readerRow);
            });
        }

        const divider2 = document.createElement('div');
        divider2.className = 'context-menu-divider';
        menu.appendChild(divider2);

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
            wsSend({ type: 'message.delete', message_id: msgId });
            // Убираем из DOM сразу у себя
            const row = document.querySelector(`.msg-row[data-id="${msgId}"]`);
            if (row) row.remove();
        } else {
            await api.messages.deleteForMe(msgId);
            const row = document.querySelector(`.msg-row[data-id="${msgId}"]`);
            if (row) row.remove();
        }
    } catch (e) {
        console.error('Failed to delete message:', e);
    }
}

// --- Reply ---
let replyingToMsg = null;

function startReply(msg) {
    replyingToMsg = msg;
    cancelEdit();

    let indicator = document.getElementById('edit-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'edit-indicator';
        indicator.className = 'edit-indicator';
        document.getElementById('input-area').prepend(indicator);
    }

    const chat = chats.find(c => c.id === currentChatId);
    const member = chat?.members.find(m => m.user.id === msg.sender_id);
    const senderName = msg.sender_id === currentUser.id
        ? 'you'
        : member?.user.display_name || member?.user.username || 'unknown';

    indicator.innerHTML = `
        <div class="reply-indicator-content">
            <span class="reply-indicator-sender">${escHtml(senderName)}</span>
            <span class="reply-indicator-text">${escHtml((msg.content || '').substring(0, 60))}${(msg.content || '').length > 60 ? '...' : ''}</span>
        </div>
        <button id="edit-cancel-btn">✕</button>
    `;
    indicator.style.display = 'flex';

    document.getElementById('edit-cancel-btn').addEventListener('click', cancelReply);
    document.getElementById('msg-input').focus();
}

function cancelReply() {
    replyingToMsg = null;
    const indicator = document.getElementById('edit-indicator');
    if (indicator) indicator.style.display = 'none';
}

// --- Edit ---
let editingMsgId = null;

function startEditMessage(msg) {
    editingMsgId = msg.id;
    cancelReply();

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
    if (e.key === 'Escape') {
        cancelReply();
        cancelEdit();
    }
});

input.addEventListener('input', () => {
    if (currentChatId) {
        wsSend({ type: 'typing', chat_id: currentChatId });
    }
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';

    const len = input.value.length;
    const counter = document.getElementById('msg-counter');
    counter.textContent = `${len} / 2000`;
    counter.style.color = len > 2000 ? 'var(--error)' : 'var(--muted)';
});

sendBtn.addEventListener('click', sendMessage);

async function sendMessage() {
    const content = input.value.trim();
    if (!content || !currentChatId) return;

    if (content.length > 2000) {
        document.getElementById('msg-counter').style.color = 'var(--error)';
        return;
    }

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

    const replyToId = replyingToMsg?.id || null;
    cancelReply();

    input.value = '';
    input.style.height = 'auto';
    document.getElementById('msg-counter').textContent = '0 / 2000';

    wsSend({
        type: 'message.send',
        chat_id: currentChatId,
        content,
        reply_to_id: replyToId,
    });
}