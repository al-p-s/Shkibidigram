async function openUserProfile(userId) {
    try {
        let userData = null;

        const currentChat = chats.find(c => c.id === currentChatId);
        if (currentChat && currentChat.type === 'direct') {
            const member = currentChat.members.find(m => m.user.id === userId);
            if (member) userData = member.user;
        }

        if (!userData && typeof contacts !== 'undefined') {
            const contact = contacts.find(c => c.contact.id === userId);
            if (contact) userData = contact.contact;
        }

        if (!userData) {
            userData = await api.users.getProfile(userId);
        }

        document.getElementById('user-profile-username').value = userData.username || 'N/A';
        document.getElementById('user-profile-display-name').value = userData.display_name || 'Not set';
        document.getElementById('user-profile-status-text').value = userData.status_text || 'No status';

        const avatarImg = document.getElementById('user-profile-avatar-img');
        if (avatarImg) {
            if (userData.avatar_url && !['null', 'undefined', ''].includes(userData.avatar_url)) {
                avatarImg.src = `${API}/users/${userId}/avatar?t=${Date.now()}`;
                avatarImg.onerror = () => {
                    const initials = (userData.username || 'U').substring(0, 2).toUpperCase();
                    avatarImg.src = `https://ui-avatars.com/api/?background=7c6af7&color=fff&name=${initials}&size=80&rounded=true`;
                };
            } else {
                const initials = (userData.username || 'U').substring(0, 2).toUpperCase();
                avatarImg.src = `https://ui-avatars.com/api/?background=7c6af7&color=fff&name=${initials}&size=80&rounded=true`;
            }
        }

        const addBtn = document.getElementById('user-profile-add-contact');
        if (addBtn) {
            if (userId === currentUser.id) {
                addBtn.style.display = 'none';
            } else {
                const alreadyContact = typeof contacts !== 'undefined'
                    && contacts.some(c => c.contact.id === userId);

                if (alreadyContact) {
                    addBtn.style.display = 'none';
                } else {
                    addBtn.style.display = 'block';
                    addBtn.disabled = false;
                    addBtn.textContent = 'Add to contacts';
                    // Клонируем чтобы снять старые слушатели
                    const fresh = addBtn.cloneNode(true);
                    addBtn.replaceWith(fresh);
                    fresh.addEventListener('click', () => addContact(userId, fresh));
                }
            }
        }

        document.getElementById('user-profile-modal').classList.add('open');

    } catch (error) {
        console.error('Error loading user profile:', error);
    }
}

async function addContact(userId, btn) {
    const msgEl = document.getElementById('user-profile-msg');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        const newContact = await api.contacts.add(userId);
       if (typeof contacts !== 'undefined') contacts.push(newContact);
        if (msgEl) {
            msgEl.textContent = 'Contact added!';
            msgEl.className = 'modal-msg success show';
        }
        btn.textContent = '✓ Added';
    } catch (error) {
        if (msgEl) {
            msgEl.textContent = error.message;
            msgEl.className = 'modal-msg error show';
        }
        btn.disabled = false;
        btn.textContent = 'Add to contacts';
    }
}

function closeUserProfile() {
    const modal = document.getElementById('user-profile-modal');
    if (modal) modal.classList.remove('open');
    const msgEl = document.getElementById('user-profile-msg');
    if (msgEl) {
        msgEl.className = 'modal-msg';
        msgEl.textContent = '';
    }
}
