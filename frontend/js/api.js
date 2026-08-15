const API = `${location.origin}/api/v1`;

function getToken() { return localStorage.getItem('access_token'); }
function setTokens(access, refresh) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}
function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

async function request(method, path, body = null, auth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = `Bearer ${getToken()}`;

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail?.map ? data.detail.map(e => e.msg).join(', ') : data.detail || 'Request failed');
  return data;
}

const api = {
  auth: {
    register: (body) => request('POST', '/auth/register', body, false),
    login:    (body) => request('POST', '/auth/login', body, false),
    logout:   (body) => request('POST', '/auth/logout', body),
  },
  users: {
    me:     ()       => request('GET', '/users/me'),
    update: (body)   => request('PATCH', '/users/me', body),
    search: (username) => request('GET', `/users/search?username=${username}`),
  },
  contacts: {
    list:   ()   => request('GET', '/contacts/'),
    add:    (id) => request('POST', `/contacts/${id}`),
    remove: (id) => request('DELETE', `/contacts/${id}`),
    blocked: {
        list:    ()   => request('GET', '/contacts/blocked'),
        block:   (id) => request('POST', `/contacts/blocked/${id}`),
        unblock: (id) => request('DELETE', `/contacts/blocked/${id}`),
    },
  },
  chats: {
    list:   ()       => request('GET', '/chats/'),
    get:    (id)     => request('GET', `/chats/${id}`),
    create: (body)   => request('POST', '/chats/', body),
    leave:  (id)     => request('DELETE', `/chats/${id}/leave`),
    addMember: (id, userId)  => request('POST', `/chats/${id}/members/${userId}`),
    update: (id, body) => request('PATCH', `/chats/${id}`, body),
    uploadAvatar: (id, formData) => {
        return fetch(`${API}/chats/${id}/avatar`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${getToken()}` },
            body: formData,
        }).then(r => r.json());
    },
    setRole: (chatId, userId, role) => request('PATCH', `/chats/${chatId}/members/${userId}/role?role=${role}`),
    removeMember: (id, userId)      => request('DELETE', `/chats/${id}/members/${userId}`),
  },
  messages: {
    list: (chatId, params = '') => request('GET', `/chats/${chatId}/messages${params}`),
    send: (chatId, body)               => request('POST', `/chats/${chatId}/messages`, body),
    deleteForAll:  (msgId)             => request('DELETE', `/chats/messages/${msgId}/all`),
    deleteForMe:   (msgId)             => request('DELETE', `/chats/messages/${msgId}/me`),
    edit: (msgId, body)                => request('PATCH', `/chats/messages/${msgId}`, body),
    upload:       (chatId, formData)    => fetch(`${API}/chats/${chatId}/messages/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getToken()}` },
        body: formData,
    }).then(async r => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || 'Upload failed');
        return data;
    }),
  },
};
