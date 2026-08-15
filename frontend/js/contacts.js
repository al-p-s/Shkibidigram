let contacts = [];

async function loadContacts() {
    try {
        contacts = await api.contacts.list();
        renderContactList();
    } catch (e) {
        console.error('Failed to load contacts:', e);
    }
}

function renderContactList() {
    const list = document.getElementById('contact-list');
    list.innerHTML = '';

    if (contacts.length === 0) {
        list.innerHTML = '<div class="empty-contacts">No contacts yet</div>';
        return;
    }

    contacts.forEach(entry => {
        const user = entry.contact;
        const name = user.display_name || user.username;
        const initial = name[0].toUpperCase();
        const avatarSrc = user.avatar_url ? `${API}/users/${user.id}/avatar?t=${Date.now()}` : null;

        const item = document.createElement('div');
        item.className = 'chat-item';
        item.dataset.id = user.id;
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
                <div class="chat-name">${name}</div>
                <div class="chat-preview">@${user.username}</div>
            </div>
            <button class="btn-remove-contact" data-id="${user.id}" title="Remove">✕</button>
        `;

        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-remove-contact')) return;
            openUserProfile(user.id);
        });

        item.querySelector('.btn-remove-contact').addEventListener('click', async () => {
            try {
                await api.contacts.remove(user.id);
                contacts = contacts.filter(c => c.contact.id !== user.id);
                renderContactList();
            } catch (e) {
                console.error('Failed to remove contact:', e);
            }
        });

        list.appendChild(item);
    });
}

document.querySelectorAll('.sidebar-tab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.sidebar-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const tab = btn.dataset.tab;
        document.getElementById('chat-list').style.display    = tab === 'chats'    ? '' : 'none';
        document.getElementById('contact-list').style.display = tab === 'contacts' ? '' : 'none';

        if (tab === 'contacts') loadContacts();
    });
});
