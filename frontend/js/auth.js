document.addEventListener('DOMContentLoaded', () => {
  // если уже залогинен — на app
  if (localStorage.getItem('access_token')) {
    window.location.href = 'app.html';
    return;
  }

  const tabs    = document.querySelectorAll('.tab-btn');
  const panels  = document.querySelectorAll('.form-panel');
  const msgEl   = document.getElementById('msg');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.panel).classList.add('active');
      clearMsg();
    });
  });

  // LOGIN
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('.btn');
    btn.disabled = true;
    clearMsg();

    try {
      const data = await api.auth.login({
        email:    document.getElementById('login-email').value.trim(),
        password: document.getElementById('login-password').value,
      });
      setTokens(data.access_token, data.refresh_token);
      window.location.href = 'app.html';
    } catch (err) {
      showMsg(err.message, 'error');
      btn.disabled = false;
    }
  });

  // REGISTER
  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('.btn');
    btn.disabled = true;
    clearMsg();

    const password = document.getElementById('reg-password').value;
    const confirm  = document.getElementById('reg-confirm').value;

    if (password !== confirm) {
      showMsg('Passwords do not match', 'error');
      btn.disabled = false;
      return;
    }

    try {
      const data = await api.auth.register({
        username:     document.getElementById('reg-username').value.trim(),
        email:        document.getElementById('reg-email').value.trim(),
        password,
        display_name: document.getElementById('reg-display').value.trim() || undefined,
      });
      setTokens(data.access_token, data.refresh_token);
      window.location.href = 'app.html';
    } catch (err) {
      showMsg(err.message, 'error');
      btn.disabled = false;
    }
  });

  function showMsg(text, type) {
    msgEl.textContent = text;
    msgEl.className = `msg ${type}`;
  }

  function clearMsg() {
    msgEl.className = 'msg';
    msgEl.textContent = '';
  }
});
