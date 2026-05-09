let isMobile = window.innerWidth <= 768;
let isSidebarOpen = false;

function fixMobileKeyboard() {
    const msgInput = document.getElementById('msg-input');
    if (!msgInput) return;

    msgInput.addEventListener('focus', () => {
        setTimeout(() => {
            const messagesWrap = document.getElementById('messages-wrap');
            if (messagesWrap) {
                messagesWrap.scrollTop = messagesWrap.scrollHeight;
            }
            msgInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
    });
}

function initMobile() {
    checkMobile();
    fixMobileKeyboard();
    window.addEventListener('resize', () => {
        checkMobile();
        if (window.innerWidth > 768 && isSidebarOpen) {
            closeMobileSidebar();
        }
    });

    const burgerBtn = document.getElementById('burger-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');

    if (burgerBtn) {
        burgerBtn.addEventListener('click', toggleMobileSidebar);
    }

    if (overlay) {
        overlay.addEventListener('click', closeMobileSidebar);
    }

    document.addEventListener('click', (e) => {
        if (isMobile && isSidebarOpen && e.target.closest('.chat-item')) {
            closeMobileSidebar();
        }
    });
}

function checkMobile() {
    isMobile = window.innerWidth <= 768;
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');

    if (!isMobile && isSidebarOpen) {
        closeMobileSidebar();
    }
}

function toggleMobileSidebar() {
    if (isSidebarOpen) {
        closeMobileSidebar();
    } else {
        openMobileSidebar();
    }
}

function openMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');
    const burgerBtn = document.getElementById('burger-btn');

    isSidebarOpen = true;
    if (sidebar) sidebar.classList.add('mobile-open');
    if (overlay) overlay.classList.add('active');
    if (burgerBtn) burgerBtn.classList.add('active');

    document.body.style.overflow = 'hidden';
}

function closeMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');
    const burgerBtn = document.getElementById('burger-btn');

    isSidebarOpen = false;
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');
    if (burgerBtn) burgerBtn.classList.remove('active');

    document.body.style.overflow = '';
}

window.mobileUtils = {
    closeSidebar: closeMobileSidebar,
    isMobile: () => isMobile
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobile);
} else {
    initMobile();
}
