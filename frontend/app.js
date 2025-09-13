// frontend/app.js
// Connects to backend WebSocket server and handles UI updates

const hostname = location.hostname;
const wsProt = location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_PORT = 6789; // must match backend
const WS_URL = `${wsProt}//${hostname}:${WS_PORT}`;

let socket = null;
let username = null;
let room = null;

// Elements
const loginOverlay = document.getElementById('login-overlay');
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username');
const roomInput = document.getElementById('room');

const messagesEl = document.getElementById('messages');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const roomLabel = document.getElementById('room-label');

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": "&#39;" }[m]));
}

function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleTimeString();
}

function addMessage(msg) {
    const el = document.createElement('div');
    el.className = 'message';
    if (msg.type === 'system') {
        el.classList.add('system');
        el.innerHTML = `<em>${escapeHtml(msg.text)} <span class="timestamp">${formatTime(msg.timestamp)}</span></em>`;
    } else if (msg.type === 'message') {
        el.innerHTML = `<strong>${escapeHtml(msg.username)}:</strong> ${escapeHtml(msg.content)} <span class="timestamp">${formatTime(msg.timestamp)}</span>`;
    }
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    username = usernameInput.value.trim() || 'Anonymous';
    room = roomInput.value.trim() || 'lobby';
    roomLabel.textContent = room;
    loginOverlay.style.display = 'none';
    connect();
});

function connect() {
    socket = new WebSocket(WS_URL);

    socket.addEventListener('open', () => {
        socket.send(JSON.stringify({ type: 'join', username, room }));
    });

    socket.addEventListener('message', (ev) => {
        try {
            const data = JSON.parse(ev.data);
            if (data.type === 'history') {
                messagesEl.innerHTML = '';
                data.messages.forEach(addMessage);
            } else {
                addMessage(data);
            }
        } catch (err) {
            console.error('Invalid message', err);
        }
    });

    socket.addEventListener('close', () => {
        addMessage({ type: 'system', text: 'Disconnected from server', timestamp: new Date().toISOString() });
    });

    socket.addEventListener('error', (err) => {
        console.error('WebSocket error', err);
    });
}

messageForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const content = messageInput.value.trim();
    if (!content || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: 'message', content }));
    messageInput.value = '';
});