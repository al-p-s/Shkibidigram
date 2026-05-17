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
    wsOn('message.read', onMessageRead);
    wsOn('message.deleted', onMessageDeleted);
    wsOn('error', onWsError);
    wsOn('blocked_by', onBlockedBy);
    wsOn('unblocked_by', onUnblockedBy);

    await loadChats();
    await loadContacts();
    await loadBlockedUsers();
}

async function loadChats() {
    chats = await api.chats.list();
    chats.sort((a, b) => {
        const ta = a.last_message_at ? new Date(a.last_message_at) : new Date(a.created_at);
        const tb = b.last_message_at ? new Date(b.last_message_at) : new Date(b.created_at);
        return tb - ta;
    });
    renderChatList();
}

function renderChatList() {
    const list = document.getElementById('chat-list');
    list.innerHTML = '';

    chats.forEach(chat => {
        const other = chat.type === 'direct'
            ? chat.members.find(m => m.user.id !== currentUser.id)
            : null;

        const name = getChatName(chat);
        const initial = name[0].toUpperCase();
        const avatarSrc = chat.type === 'direct' && other?.user.avatar_url
            ? `${API}/users/${other.user.id}/avatar?t=${Date.now()}`
            : chat.type === 'group' && chat.avatar_url
                ? `${API}/chats/${chat.id}/avatar?t=${Date.now()}`
                : null;

        const item = document.createElement('div');
        item.className = 'chat-item' + (chat.id === currentChatId ? ' active' : '');
        item.dataset.id = chat.id;
        item.innerHTML = `
            <div class="avatar" id="av-${chat.id}">
                ${avatarSrc
                    ? `<img src="${avatarSrc}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" style="width:100%;height:100%;border-radius:2px;object-fit:cover;">`
                    : ''
                }
                <span style="display:${avatarSrc ? 'none' : 'flex'}; align-items:center; justify-content:center; width:100%; height:100%;">
                    ${initial}
                </span>
                <div class="online-dot" id="dot-${chat.id}"></div>
            </div>
            <div class="chat-info">
                <div class="chat-name">${name}</div>
                <div class="chat-preview">${chat.type === 'direct' ? 'direct' : 'group · ' + chat.members.length}</div>
            </div>
            ${chat.unread_count > 0
                ? `<div class="unread-badge">${chat.unread_count > 99 ? '99+' : chat.unread_count}</div>`
                : ''
            }
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
    const chatToReset = chats.find(c => c.id === chatId);
    if (chatToReset) chatToReset.unread_count = 0;
    renderChatList();

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
    document.getElementById('chat-header-name').style.cursor = 'pointer';
    document.getElementById('chat-header-name').title = 'Click to view profile';

    const callBtn = document.getElementById('btn-call');
    if (callBtn) {
        if (chat.type === 'direct') {
            callBtn.style.display = 'block';
            console.log('[UI] Call button shown for direct chat');
        } else {
            callBtn.style.display = 'none';
            console.log('[UI] Call button hidden for group chat');
        }
    }

    document.getElementById('chat-header-name').onclick = () => {
        if (chat.type === 'direct') {
            const other = chat.members.find(m => m.user.id !== currentUser.id);
            if (other) {
                openUserProfile(other.user.id);
            }
        }
    };

    if (chat.type === 'group') {
    document.getElementById('chat-header-name').style.cursor = 'pointer';
    document.getElementById('chat-header-name').title = 'Click to view group info';
    document.getElementById('chat-header-name').onclick = () => openGroupInfo(chat);
}
    await loadMessages(chatId);
    await updateChatInputState(chat);
}

function onPresence(event) {
    const dot = document.getElementById(`dot-${currentChatId}`);
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
    const chat = chats.find(c => c.id === event.message.chat_id);
    if (chat) {
        chat.last_message_at = event.message.created_at;
        chats.sort((a, b) => {
            const ta = a.last_message_at ? new Date(a.last_message_at) : new Date(a.created_at);
            const tb = b.last_message_at ? new Date(b.last_message_at) : new Date(b.created_at);
            return tb - ta;
        });
    }

    if (event.message.chat_id === currentChatId) {
        // Проверяем нужен ли разделитель
        const wrap = document.getElementById('messages-wrap');
        const lastRow = wrap.querySelector('.msg-row:last-child');
        if (lastRow) {
            const lastMsg = lastRow._msgData;
            if (lastMsg) {
                const lastDate = new Date(lastMsg.created_at).toDateString();
                const newDate = new Date(event.message.created_at).toDateString();
                if (lastDate !== newDate) {
                    appendDateSeparator(getDateLabel(event.message.created_at));
                }
            }
        }

        appendMessage(event.message, false);
        scrollBottom();
        if (event.message.sender_id !== currentUser.id) {
            wsSend({ type: 'message.read', message_id: event.message.id });
        }
    } else {
        if (chat && event.message.sender_id !== currentUser.id) {
            chat.unread_count = (chat.unread_count || 0) + 1;
        }
    }
    renderChatList();
}

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
        if (!user) {
            err.textContent = 'User not found';
            err.className = 'modal-msg show';
            return;
        }

        const chat = await api.chats.create({type: 'direct', member_ids: [user.id]});
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

document.getElementById('new-chat-btn').addEventListener('click', () => {
    document.getElementById('chat-type-modal').classList.add('open');
});

document.getElementById('type-cancel').addEventListener('click', () => {
    document.getElementById('chat-type-modal').classList.remove('open');
});

document.getElementById('type-direct').addEventListener('click', () => {
    document.getElementById('chat-type-modal').classList.remove('open');
    document.getElementById('new-chat-modal').classList.add('open');
});

document.getElementById('type-group').addEventListener('click', () => {
    document.getElementById('chat-type-modal').classList.remove('open');
    openGroupModal();
});

let selectedMemberIds = new Set();

function openGroupModal() {
    selectedMemberIds.clear();
    document.getElementById('group-name-input').value = '';
    document.getElementById('group-msg').className = 'modal-msg';
    document.getElementById('group-msg').textContent = '';
    document.getElementById('group-selected-count').textContent = '0 selected';

    renderGroupContacts();
    document.getElementById('new-group-modal').classList.add('open');
}

function renderGroupContacts() {
    const list = document.getElementById('group-contacts-list');
    list.innerHTML = '';

    if (!contacts || contacts.length === 0) {
        list.innerHTML = '<div style="padding:12px;color:var(--muted);text-align:center;font-size:12px;">No contacts yet</div>';
        return;
    }

    contacts.forEach(entry => {
        const user = entry.contact;
        const name = user.display_name || user.username;
        const isSelected = selectedMemberIds.has(user.id);

        const item = document.createElement('div');
        item.className = 'group-member-item' + (isSelected ? ' selected' : '');
        item.dataset.id = user.id;
        item.innerHTML = `
            <div class="group-member-check">${isSelected ? '✓' : ''}</div>
            <div>
                <div class="group-member-name">${name}</div>
                <div class="group-member-username">@${user.username}</div>
            </div>
        `;

        item.addEventListener('click', () => toggleGroupMember(user.id));
        list.appendChild(item);
    });
}

function toggleGroupMember(userId) {
    if (selectedMemberIds.has(userId)) {
        selectedMemberIds.delete(userId);
    } else {
        selectedMemberIds.add(userId);
    }

    document.getElementById('group-selected-count').textContent = `${selectedMemberIds.size} selected`;

    const item = document.querySelector(`#group-contacts-list [data-id="${userId}"]`);
    if (item) {
        const isSelected = selectedMemberIds.has(userId);
        item.classList.toggle('selected', isSelected);
        item.querySelector('.group-member-check').textContent = isSelected ? '✓' : '';
    }
}

document.getElementById('group-cancel').addEventListener('click', () => {
    document.getElementById('new-group-modal').classList.remove('open');
});

document.getElementById('group-create').addEventListener('click', async () => {
    const name = document.getElementById('group-name-input').value.trim();
    const msgEl = document.getElementById('group-msg');
    const btn = document.getElementById('group-create');

    msgEl.className = 'modal-msg';

    if (!name) {
        msgEl.textContent = 'Enter a group name';
        msgEl.className = 'modal-msg error show';
        return;
    }

    if (selectedMemberIds.size === 0) {
        msgEl.textContent = 'Select at least one member';
        msgEl.className = 'modal-msg error show';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating...';

    try {
        const chat = await api.chats.create({
            type: 'group',
            name: name,
            member_ids: [...selectedMemberIds],
        });

        document.getElementById('new-group-modal').classList.remove('open');
        await loadChats();
        await openChat(chat.id);
    } catch (e) {
        msgEl.textContent = e.message;
        msgEl.className = 'modal-msg error show';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create group';
    }
});

function openGroupInfo(chat) {
    const isOwner = chat.members.find(m => m.user.id === currentUser.id)?.role === 'owner';

    document.getElementById('group-info-name').textContent = chat.name || 'Group';
    document.getElementById('group-info-count').textContent = `${chat.members.length} members`;

    document.getElementById('group-info-view').style.display = '';
    document.getElementById('group-info-edit').style.display = 'none';
    document.getElementById('group-info-save-btn').style.display = 'none';
    document.getElementById('group-info-edit-btn').style.display = isOwner ? '' : 'none';
    document.getElementById('group-info-edit-msg').className = 'modal-msg';

    const avatarImg = document.getElementById('group-info-avatar-img');
    const avatarBtn = document.getElementById('group-avatar-upload-btn');

    if (chat.avatar_url) {
        avatarImg.src = `${API}/chats/${chat.id}/avatar?t=${Date.now()}`;
        avatarImg.onerror = () => {
            avatarImg.src = `https://ui-avatars.com/api/?background=4a3fa0&color=fff&name=${encodeURIComponent(chat.name || 'G')}&size=80&rounded=true`;
        };
    } else {
        avatarImg.src = `https://ui-avatars.com/api/?background=4a3fa0&color=fff&name=${encodeURIComponent(chat.name || 'G')}&size=80&rounded=true`;
    }

    avatarBtn.style.display = 'none';

    const freshBtn = avatarBtn.cloneNode(true);
    avatarBtn.replaceWith(freshBtn);
    const oldInput = document.getElementById('group-avatar-input');
    const freshInput = oldInput.cloneNode(true);
    oldInput.replaceWith(freshInput);

    freshBtn.addEventListener('click', () => {
        document.getElementById('group-avatar-input').click();
    });

    document.getElementById('group-avatar-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        freshBtn.disabled = true;
        freshBtn.textContent = 'Uploading...';

        try {
            const updated = await api.chats.uploadAvatar(chat.id, formData);
            const idx = chats.findIndex(c => c.id === chat.id);
            if (idx !== -1) chats[idx] = updated;
            renderChatList();
            openGroupInfo(updated);
        } catch (err) {
            console.error('Failed to upload avatar:', err);
        } finally {
            freshBtn.disabled = false;
            freshBtn.textContent = 'Change avatar';
            e.target.value = '';
        }
    });

    const list = document.getElementById('group-info-members');
    list.innerHTML = '';

    chat.members.forEach(m => {
        const user = m.user;
        const isCurrentUser = user.id === currentUser.id;
        const name = user.display_name || user.username;
        const initial = name[0].toUpperCase();
        const avatarSrc = user.avatar_url ? `${API}/users/${user.id}/avatar?t=${Date.now()}` : null;

        const item = document.createElement('div');
        item.className = 'chat-item';
        item.style.cursor = !isCurrentUser ? 'pointer' : 'default';
        item.innerHTML = `
            <div class="avatar">
                ${avatarSrc
                    ? `<img src="${avatarSrc}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" style="width:100%;height:100%;border-radius:2px;object-fit:cover;">`
                    : ''}
                <span style="display:${avatarSrc ? 'none' : 'flex'};align-items:center;justify-content:center;width:100%;height:100%;">
                    ${initial}
                </span>
            </div>
            <div class="chat-info">
                <div class="chat-name">
                    ${name}
                    ${isCurrentUser ? '<span style="color:var(--muted);font-size:11px;"> (you)</span>' : ''}
                    ${m.role === 'owner' ? '<span class="member-owner-badge">owner</span>' : ''}
                </div>
                <div class="chat-preview">@${user.username}</div>
            </div>
        `;

        if (!isCurrentUser) {
            item.addEventListener('click', () => {
                document.getElementById('group-info-modal').classList.remove('open');
                openUserProfile(user.id);
            });
        }

        list.appendChild(item);
    });

    document.getElementById('group-info-modal').classList.add('open');
}

document.getElementById('group-info-close').addEventListener('click', () => {
    document.getElementById('group-info-modal').classList.remove('open');
});

document.getElementById('group-info-leave').addEventListener('click', async () => {
    const btn = document.getElementById('group-info-leave');
    btn.disabled = true;
    btn.textContent = 'Leaving...';

    try {
        await api.chats.leave(currentChatId);
        document.getElementById('group-info-modal').classList.remove('open');

        chats = chats.filter(c => c.id !== currentChatId);
        currentChatId = null;
        renderChatList();

        document.getElementById('chat-view').style.display = 'none';
        document.getElementById('empty-state').style.display = 'flex';
    } catch (e) {
        btn.disabled = false;
        btn.textContent = 'Leave chat';
        console.error('Failed to leave chat:', e);
    }
});

document.getElementById('group-info-add-members').addEventListener('click', () => {
    document.getElementById('group-info-modal').classList.remove('open');
    openAddMembersModal(chats.find(c => c.id === currentChatId));
});

function openAddMembersModal(chat) {
    const existingIds = new Set(chat.members.map(m => m.user.id));
    const available = contacts.filter(c => !existingIds.has(c.contact.id));

    const list = document.getElementById('add-members-list');
    list.innerHTML = '';
    selectedMemberIds.clear();
    document.getElementById('add-members-msg').className = 'modal-msg';
    document.getElementById('add-members-selected').textContent = '0 selected';

    if (available.length === 0) {
        list.innerHTML = '<div style="padding:12px;color:var(--muted);text-align:center;font-size:12px;">All contacts are already in this chat</div>';
    } else {
        available.forEach(entry => {
            const user = entry.contact;
            const name = user.display_name || user.username;

            const item = document.createElement('div');
            item.className = 'group-member-item';
            item.dataset.id = user.id;
            item.innerHTML = `
                <div class="group-member-check"></div>
                <div>
                    <div class="group-member-name">${name}</div>
                    <div class="group-member-username">@${user.username}</div>
                </div>
            `;
            item.addEventListener('click', () => {
                if (selectedMemberIds.has(user.id)) {
                    selectedMemberIds.delete(user.id);
                } else {
                    selectedMemberIds.add(user.id);
                }
                const isSelected = selectedMemberIds.has(user.id);
                item.classList.toggle('selected', isSelected);
                item.querySelector('.group-member-check').textContent = isSelected ? '✓' : '';
                document.getElementById('add-members-selected').textContent = `${selectedMemberIds.size} selected`;
            });
            list.appendChild(item);
        });
    }

    document.getElementById('add-members-modal').classList.add('open');
}

document.getElementById('add-members-cancel').addEventListener('click', () => {
    document.getElementById('add-members-modal').classList.remove('open');
    openGroupInfo(chats.find(c => c.id === currentChatId));
});

document.getElementById('add-members-confirm').addEventListener('click', async () => {
    if (selectedMemberIds.size === 0) {
        const msgEl = document.getElementById('add-members-msg');
        msgEl.textContent = 'Select at least one member';
        msgEl.className = 'modal-msg error show';
        return;
    }

    const btn = document.getElementById('add-members-confirm');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        for (const userId of selectedMemberIds) {
            await api.chats.addMember(currentChatId, userId);
        }

        const updated = await api.chats.get(currentChatId);
        const idx = chats.findIndex(c => c.id === currentChatId);
        if (idx !== -1) chats[idx] = updated;

        document.getElementById('add-members-modal').classList.remove('open');
        openGroupInfo(updated);
    } catch (e) {
        const msgEl = document.getElementById('add-members-msg');
        msgEl.textContent = e.message;
        msgEl.className = 'modal-msg error show';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Add';
    }
});

document.getElementById('group-info-modal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('group-info-modal')) {
        document.getElementById('group-info-modal').classList.remove('open');
    }
});

document.getElementById('group-info-edit-btn').addEventListener('click', () => {
    const chat = chats.find(c => c.id === currentChatId);
    document.getElementById('group-info-name-input').value = chat.name || '';
    document.getElementById('group-info-view').style.display = 'none';
    document.getElementById('group-info-edit').style.display = '';
    document.getElementById('group-info-edit-btn').style.display = 'none';
    document.getElementById('group-info-save-btn').style.display = '';
    document.getElementById('group-avatar-upload-btn').style.display = '';
});

document.getElementById('group-info-save-btn').addEventListener('click', async () => {
    const name = document.getElementById('group-info-name-input').value.trim();
    const msgEl = document.getElementById('group-info-edit-msg');
    const btn = document.getElementById('group-info-save-btn');

    if (!name) {
        msgEl.textContent = 'Name cannot be empty';
        msgEl.className = 'modal-msg error show';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
        const updated = await api.chats.update(currentChatId, { name });
        const idx = chats.findIndex(c => c.id === currentChatId);
        if (idx !== -1) chats[idx] = updated;
        renderChatList();
        openGroupInfo(updated);
    } catch (e) {
        msgEl.textContent = e.message;
        msgEl.className = 'modal-msg error show';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Save';
    }
});

function onMessageRead(event) {
    const statusEl = document.getElementById(`status-${event.message_id}`);
    if (statusEl) {
        statusEl.textContent = '✓✓';
        statusEl.classList.add('read');
    }

    const row = document.querySelector(`.msg-row[data-id="${event.message_id}"]`);
    if (row?._msgData) {
        const existing = row._msgData.statuses?.find(s => s.user_id === event.user_id);
        if (existing) {
            existing.status = 'read';
        } else {
            row._msgData.statuses = row._msgData.statuses || [];
            row._msgData.statuses.push({ user_id: event.user_id, status: 'read' });
        }
    }
}

document.querySelector('.logo').addEventListener('click', () => {
    currentChatId = null;
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    document.getElementById('chat-view').style.display = 'none';
    document.getElementById('empty-state').style.display = 'flex';
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && currentChatId) {
        currentChatId = null;
        document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
        document.getElementById('chat-view').style.display = 'none';
        document.getElementById('empty-state').style.display = 'flex';
    }
});

function onMessageDeleted(event) {
    const row = document.querySelector(`.msg-row[data-id="${event.message_id}"]`);
    if (row) row.remove();
}

async function updateChatInputState(chat) {
    const inputArea = document.getElementById('input-area');
    const blockedNotice = document.getElementById('blocked-notice');
    const noticeText = document.getElementById('blocked-notice-text');

    if (chat.type !== 'direct') {
        inputArea.style.display = '';
        blockedNotice.style.display = 'none';
        return;
    }

    const other = chat.members.find(m => m.user.id !== currentUser.id);
    if (!other) return;

    // Я заблокировал его
    const iBlockedThem = typeof blockedUsers !== 'undefined'
        && blockedUsers.some(b => b.blocked.id === other.user.id);

    if (iBlockedThem) {
        inputArea.style.display = 'none';
        noticeText.textContent = 'You have blocked this user.';
        blockedNotice.style.display = 'flex';
        return;
    }

    // Он заблокировал меня — проверяем через API
    try {
        const res = await fetch(`${API}/contacts/blocked/check/${other.user.id}`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (res.ok) {
            const isBlockedByThem = await res.json();
            if (isBlockedByThem) {
                inputArea.style.display = 'none';
                noticeText.textContent = 'You have been blocked by this user.';
                blockedNotice.style.display = 'flex';
                return;
            }
        }
    } catch (e) {
        console.error('Failed to check block status:', e);
    }

    inputArea.style.display = '';
    blockedNotice.style.display = 'none';
}

function onWsError(event) {
    if (event.error === 'You are blocked by this user') {
        const inputArea = document.getElementById('input-area');
        const blockedNotice = document.getElementById('blocked-notice');
        inputArea.style.display = 'none';
        document.getElementById('blocked-notice-text').textContent = 'You have been blocked by this user.';
        blockedNotice.style.display = 'flex';
    }
}

function onBlockedBy(event) {
    const chat = chats.find(c =>
        c.type === 'direct' && c.members.some(m => m.user.id === event.user_id)
    );
    if (chat && chat.id === currentChatId) {
        document.getElementById('input-area').style.display = 'none';
        document.getElementById('blocked-notice-text').textContent = 'You have been blocked by this user.';
        document.getElementById('blocked-notice').style.display = 'flex';
    }
}

function onUnblockedBy(event) {
    const chat = chats.find(c =>
        c.type === 'direct' && c.members.some(m => m.user.id === event.user_id)
    );
    if (chat && chat.id === currentChatId) {
        document.getElementById('input-area').style.display = '';
        document.getElementById('blocked-notice').style.display = 'none';
    }
}

initApp();
