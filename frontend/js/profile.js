let profileUserData = null;
let isEditMode = false;

async function loadProfile() {
    try {
        profileUserData = await api.users.me();

        const usernameField = document.getElementById('profile-username');
        const emailField = document.getElementById('profile-email');
        const displayNameField = document.getElementById('profile-display-name');
        const statusTextField = document.getElementById('profile-status-text');
        const createdAtField = document.getElementById('profile-created-at');

        if (usernameField) usernameField.value = profileUserData.username;
        if (emailField) emailField.value = profileUserData.email;
        if (displayNameField) displayNameField.value = profileUserData.display_name || '';
        if (statusTextField) statusTextField.value = profileUserData.status_text || '';

        if (createdAtField) {
            const createdDate = new Date(profileUserData.created_at);
            createdAtField.value = createdDate.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        }

        updateAvatarDisplay(profileUserData.avatar_url, profileUserData.username);

        const currentUserSpan = document.getElementById('current-user');
        if (currentUserSpan) currentUserSpan.innerHTML = `@${profileUserData.username}`;

        setViewMode();
    } catch (error) {
        console.error('Load profile error:', error);
        showProfileMsg(error.message, 'error');
    }
}

function updateAvatarDisplay(avatarObjectKey, username) {
    const avatarImg = document.getElementById('profile-avatar-img');
    if (!avatarImg) return;
    if (avatarObjectKey) {
        avatarImg.src = `${API}/users/${profileUserData.id}/avatar?t=${Date.now()}`;
    } else {
        avatarImg.src = `https://ui-avatars.com/api/?background=7c6af7&color=fff&name=${username.substring(0,2).toUpperCase()}`;
    }
}

function enableEditMode() {
    console.log('Enabling edit mode...');
    isEditMode = true;

    const displayNameField = document.getElementById('profile-display-name');
    const statusTextField = document.getElementById('profile-status-text');

    if (!displayNameField || !statusTextField) {
        console.error('Fields not found!');
        return;
    }

    displayNameField.removeAttribute('readonly');
    displayNameField.removeAttribute('disabled');
    displayNameField.classList.add('editable');

    statusTextField.removeAttribute('readonly');
    statusTextField.removeAttribute('disabled');
    statusTextField.classList.add('editable');

    const editBtn = document.getElementById('profile-edit-btn');
    const saveBtn = document.getElementById('profile-save');

    if (editBtn) editBtn.style.display = 'none';
    if (saveBtn) saveBtn.style.display = 'block';

    const editStatus = document.getElementById('profile-edit-status');
    if (editStatus) {
        editStatus.style.display = 'block';
        editStatus.textContent = 'Edit mode is ON - you can edit fields';
    }

    const avatarUploadBtn = document.getElementById('avatar-upload-btn');
    if (avatarUploadBtn) {
        avatarUploadBtn.style.display = 'inline-block';
    }

    displayNameField.focus();
}

function disableEditMode() {
    console.log('Disabling edit mode...');
    isEditMode = false;

    const displayNameField = document.getElementById('profile-display-name');
    const statusTextField = document.getElementById('profile-status-text');

    if (displayNameField) {
        displayNameField.setAttribute('readonly', 'readonly');
        displayNameField.setAttribute('disabled', 'disabled');
        displayNameField.classList.remove('editable');
    }

    if (statusTextField) {
        statusTextField.setAttribute('readonly', 'readonly');
        statusTextField.setAttribute('disabled', 'disabled');
        statusTextField.classList.remove('editable');
    }

    const editBtn = document.getElementById('profile-edit-btn');
    const saveBtn = document.getElementById('profile-save');

    if (editBtn) editBtn.style.display = 'block';
    if (saveBtn) saveBtn.style.display = 'none';

    const editStatus = document.getElementById('profile-edit-status');
    if (editStatus) editStatus.style.display = 'none';

    const avatarUploadBtn = document.getElementById('avatar-upload-btn');
    if (avatarUploadBtn) {
        avatarUploadBtn.style.display = 'none';
    }
}

function setViewMode() {
    disableEditMode();
}

async function saveProfile() {
    if (!isEditMode) {
        showProfileMsg('Please click Edit button first', 'error');
        return;
    }

    const displayName = document.getElementById('profile-display-name').value.trim();
    const statusText = document.getElementById('profile-status-text').value.trim();

    const saveBtn = document.getElementById('profile-save');
    if (!saveBtn) return;

    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const updated = await api.users.update({
            display_name: displayName || null,
            status_text: statusText || null
        });

        profileUserData = updated;
        showProfileMsg('Profile updated successfully!', 'success');

        disableEditMode();

        const currentUserSpan = document.getElementById('current-user');
        if (currentUserSpan) currentUserSpan.innerHTML = `@${updated.username}`;

    } catch (error) {
        console.error('Save profile error:', error);
        showProfileMsg(error.message, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
    }
}

async function uploadAvatar(file) {
    console.log('uploadAvatar called with file:', file);

    if (!isEditMode) {
        showProfileMsg('Please click Edit button first to change avatar', 'error');
        return;
    }

    if (!file.type.match('image/jpeg') && !file.type.match('image/png')) {
        showProfileMsg('Only JPG/PNG images allowed', 'error');
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        showProfileMsg('File too large, max 5MB', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const token = getToken();
    if (!token) {
        showProfileMsg('Authentication error', 'error');
        return;
    }

    const uploadBtn = document.getElementById('avatar-upload-btn');
    if (!uploadBtn) {
        console.error('Upload button not found');
        return;
    }

    const originalText = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = 'Uploading...';

    try {
        console.log('Sending upload request...');
        const response = await fetch(`${API}/users/me/avatar`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        console.log('Upload response status:', response.status);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const updatedUser = await response.json();
        console.log('Upload successful, updated user:', updatedUser);

        profileUserData = updatedUser;

        updateAvatarDisplay(updatedUser.avatar_url, updatedUser.username);
        showProfileMsg('Avatar updated successfully!', 'success');

    } catch (error) {
        console.error('Upload error details:', error);
        showProfileMsg(`${error.message}`, 'error');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    }
}

function showProfileMsg(text, type) {
    const msgEl = document.getElementById('profile-msg');
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.className = `modal-msg ${type} show`;
    setTimeout(() => {
        if (msgEl) msgEl.className = 'modal-msg';
    }, 3000);
}

function clearProfileMsg() {
    const msgEl = document.getElementById('profile-msg');
    if (msgEl) msgEl.className = 'modal-msg';
}

function openProfileModal() {
    console.log('Opening profile modal');
    setViewMode();
    loadProfile();
    const modal = document.getElementById('profile-modal');
    if (modal) modal.classList.add('open');
}

function closeProfileModal() {
    const modal = document.getElementById('profile-modal');
    if (modal) modal.classList.remove('open');
    clearProfileMsg();
    setViewMode();
}

function setupProfileEventListeners() {
    console.log('Setting up profile event listeners...');

    const profileBtn = document.getElementById('profile-btn');
    if (profileBtn) {
        console.log('Found profile button');
        profileBtn.addEventListener('click', openProfileModal);
    } else {
        console.error('Profile button not found');
    }

    const cancelBtn = document.getElementById('profile-cancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeProfileModal);
    }

    const editBtn = document.getElementById('profile-edit-btn');
    if (editBtn) {
        editBtn.addEventListener('click', enableEditMode);
    }

    const saveBtn = document.getElementById('profile-save');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveProfile);
    }

    const avatarUploadBtn = document.getElementById('avatar-upload-btn');
    const avatarInput = document.getElementById('avatar-upload');

    if (avatarUploadBtn && avatarInput) {
        console.log('Setting up avatar upload handlers');

        const newAvatarUploadBtn = avatarUploadBtn.cloneNode(true);
        avatarUploadBtn.parentNode.replaceChild(newAvatarUploadBtn, avatarUploadBtn);

        const newAvatarInput = avatarInput.cloneNode(true);
        avatarInput.parentNode.replaceChild(newAvatarInput, avatarInput);

        newAvatarUploadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Avatar upload button clicked, isEditMode:', isEditMode);

            if (!isEditMode) {
                showProfileMsg('Click Edit button first to change avatar', 'error');
                return;
            }
            document.getElementById('avatar-upload').click();
        });

        newAvatarInput.addEventListener('change', (e) => {
            console.log('File input changed');
            if (e.target.files && e.target.files[0]) {
                const file = e.target.files[0];
                console.log('Selected file:', file.name, file.type, file.size);
                uploadAvatar(file);
            }
            e.target.value = '';
        });
    } else {
        console.error('Avatar upload elements not found:', {
            button: !!avatarUploadBtn,
            input: !!avatarInput
        });
    }

    const modal = document.getElementById('profile-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeProfileModal();
            }
        });
    }

    const userProfileClose = document.getElementById('user-profile-close');
    if (userProfileClose) {
        userProfileClose.addEventListener('click', () => {
            document.getElementById('user-profile-modal').classList.remove('open');
        });
    }

    const userProfileModal = document.getElementById('user-profile-modal');
    if (userProfileModal) {
        userProfileModal.addEventListener('click', (e) => {
            if (e.target === userProfileModal) {
                userProfileModal.classList.remove('open');
            }
        });
    }

    console.log('Profile event listeners setup complete');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupProfileEventListeners);
} else {
    setupProfileEventListeners();
}
