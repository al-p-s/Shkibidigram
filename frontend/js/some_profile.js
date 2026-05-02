async function openUserProfile(userId) {
    try {
        let userData = null;

        const currentChat = chats.find(c => c.id === currentChatId);
        if (currentChat && currentChat.type === 'direct') {
            const member = currentChat.members.find(m => m.user.id === userId);
            if (member) userData = member.user;
        }

        if (!userData) {
            console.log('User not found in local cache');
            return;
        }

        document.getElementById('user-profile-username').value = userData.username || 'N/A';
        document.getElementById('user-profile-display-name').value = userData.display_name || 'Not set';
        document.getElementById('user-profile-status-text').value = userData.status_text || 'No status';

        const avatarImg = document.getElementById('user-profile-avatar-img');
        if (avatarImg) {
            if (userData.avatar_url && userData.avatar_url !== 'null' && userData.avatar_url !== 'undefined' && userData.avatar_url !== '') {
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
            if (userId !== currentUser.id) {
                addBtn.style.display = 'block';
                addBtn.replaceWith(addBtn.cloneNode(true));
                const newAddBtn = document.getElementById('user-profile-add-contact');
                newAddBtn.addEventListener('click', () => addContact(userId));
            } else {
                addBtn.style.display = 'none';
            }
        }

        document.getElementById('user-profile-modal').classList.add('open');

    } catch (error) {
        console.error('Error loading user profile:', error);
    }
}

async function addContact(userId) {
    const msgEl = document.getElementById('user-profile-msg');
    const btn = document.getElementById('user-profile-add-contact');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        await api.contacts.add(userId);
        if (msgEl) {
            msgEl.textContent = 'Contact added!';
            msgEl.className = 'modal-msg success show';
        }
        btn.textContent = '✓ Added';
        btn.disabled = true;
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
