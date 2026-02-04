const API_URL = '/api/devices';
// Extract user_id
// Priority: 1. Telegram WebApp context 2. URL Query Params
let userId = null;

// Try Telegram WebApp
if (window.Telegram && window.Telegram.WebApp) {
    const tgUser = window.Telegram.WebApp.initDataUnsafe?.user;
    if (tgUser && tgUser.id) {
        userId = tgUser.id;
        console.log('Got user_id from Telegram WebApp:', userId);
    }
}

// Fallback to URL (for testing outside TG or if context is missing)
if (!userId) {
    const urlParams = new URLSearchParams(window.location.search);
    userId = urlParams.get('user_id');
    if (userId) console.log('Got user_id from URL:', userId);
}

let wsUrl = ((window.location.protocol === 'https:') ? 'wss://' : 'ws://') + window.location.host + '/ws/dashboard';
if (userId) {
    wsUrl += `?user_id=${userId}`;
}
const WS_URL = wsUrl;

// DOM Elements
const devicesGrid = document.getElementById('devices-grid');
const connectionStatus = document.getElementById('connection-status');
const statusDot = connectionStatus.querySelector('.dot');
const statusText = connectionStatus.querySelector('.text');

// State
let devices = [];
let pendingUpdates = new Set(); // Track devices currently being toggled via API
let socket = null;
let reconnectTimer = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
});

function connectWebSocket() {
    if (socket) {
        socket.close();
    }

    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        console.log('Dashboard connected');
        setSystemOnline(true);
        // Clear any reconnect timer
        if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleMessage(message);
        } catch (e) {
            console.error('Invalid JSON:', e);
        }
    };

    socket.onclose = () => {
        console.log('Dashboard disconnected');
        setSystemOnline(false);
        // Attempt reconnect
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        socket.close();
    };
}

function handleMessage(msg) {
    if (msg.type === 'full_state') {
        devices = msg.devices;
        updateUI();
    } else if (msg.type === 'device_connected') {
        // Add or update existing device status
        const content = msg.device;
        const exists = devices.find(d => d.device_id === content.device_id);
        if (exists) {
            exists.status = 'online';
            exists.state = content.state; // Sync state
        } else {
            devices.push(content);
        }
        updateUI();
    } else if (msg.type === 'device_disconnected') {
        const devId = msg.device_id;
        const device = devices.find(d => d.device_id === devId);
        if (device) {
            device.status = 'offline';
            updateUI();
        }
    } else if (msg.type === 'state_change') {
        const { device_id, state } = msg;
        const device = devices.find(d => d.device_id === device_id);

        // If we have a pending update for this device, we might skip this 
        // to avoid "flickering" if the WS message arrives before the API returns.
        // However, usually WS is the source of truth.
        if (device) {
            // Only update if not pending OR if the state matches what we expect
            // Actually, let's trust the server state always.
            device.state = state;
            updateUI();
        }
    }
}

function updateUI() {
    // If grid is empty (first load), clear shimmer or empty state
    if (devicesGrid.querySelector('.loading-card')) {
        devicesGrid.innerHTML = '';
    }

    // Get existing cards
    const existingCards = Array.from(devicesGrid.children);

    // Remove deleted devices (if any logic for removal exists, currently only offline)
    existingCards.forEach(card => {
        if (!devices.find(d => d.device_id === card.dataset.id)) {
            card.remove();
        }
    });

    // Add or Update devices
    devices.forEach(device => {
        let card = devicesGrid.querySelector(`.device-card[data-id="${device.device_id}"]`);

        if (!card) {
            // Create new card
            card = createDeviceCard(device);
            devicesGrid.appendChild(card);
        } else {
            // Update existing card
            updateDeviceCard(card, device);
        }
    });
}

function createDeviceCard(device) {
    const card = document.createElement('div');
    card.className = `device-card ${device.state === 'ON' ? 'on' : ''} ${device.status === 'offline' ? 'offline' : ''}`;
    card.dataset.id = device.device_id;

    card.innerHTML = `
        <div class="device-header">
            <div class="device-icon">
                💡
            </div>
            <div class="device-status ${device.status === 'online' ? 'status-online' : 'status-offline'}">
                ${device.status}
            </div>
        </div>
        <h3 class="device-name">${device.name || device.device_id}</h3>
        <p class="device-room">Room 101</p>
        
        <div class="toggle-switch">
            <span class="switch-label">${device.state}</span>
            <div class="switch-btn"></div>
        </div>
    `;

    // Attach listener ONLY to the switch
    const switchEl = card.querySelector('.toggle-switch');
    switchEl.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDevice(device);
    });

    return card;
}

function updateDeviceCard(card, device) {
    // Update classes (preserve processing class if present)
    const isProcessing = card.classList.contains('processing');
    card.className = `device-card ${device.state === 'ON' ? 'on' : ''} ${device.status === 'offline' ? 'offline' : ''}`;
    if (isProcessing) card.classList.add('processing');

    // Update Status Text
    const statusEl = card.querySelector('.device-status');
    statusEl.textContent = device.status;
    statusEl.className = `device-status ${device.status === 'online' ? 'status-online' : 'status-offline'}`;

    // Update Label
    const label = card.querySelector('.switch-label');
    if (label) label.textContent = device.state;
}

// Logic: Turn On/Off via API
async function toggleDevice(deviceArg) {
    const deviceId = deviceArg.device_id;

    const currentDevice = devices.find(d => d.device_id === deviceId);
    if (!currentDevice) return;

    if (currentDevice.status === 'offline' || pendingUpdates.has(deviceId)) return;

    const newState = currentDevice.state === 'ON' ? 'OFF' : 'ON';
    const action = currentDevice.state === 'ON' ? 'turn_off' : 'turn_on';

    // 1. Mark as pending
    pendingUpdates.add(deviceId);

    // 2. Optimistic Update
    const deviceIndex = devices.findIndex(d => d.device_id === deviceId);
    if (deviceIndex !== -1) {
        devices[deviceIndex].state = newState;
    }

    // 3. Update UI immediately
    const card = devicesGrid.querySelector(`.device-card[data-id="${deviceId}"]`);
    if (card) {
        card.classList.add('processing');
        updateDeviceCard(card, devices[deviceIndex]);
    }

    try {
        await fetch(`/api/devices/${deviceId}/${action}`, { method: 'POST' });
        // Success: Remove from pending
        if (card) card.classList.remove('processing');
        pendingUpdates.delete(deviceId);

    } catch (error) {
        console.error('Error toggling device:', error);
        // Revert State
        if (deviceIndex !== -1) {
            devices[deviceIndex].state = (newState === 'ON' ? 'OFF' : 'ON');
            if (card) {
                card.classList.remove('processing');
                updateDeviceCard(card, devices[deviceIndex]);
            }
        }
        pendingUpdates.delete(deviceId);
    }
}

function setSystemOnline(isOnline) {
    if (isOnline) {
        statusDot.style.backgroundColor = 'var(--success)';
        statusDot.style.boxShadow = '0 0 8px var(--success)';
        // Show ID for validation
        const statusMsg = userId ? `Online (ID: ${userId})` : 'Online (Guest)';
        statusText.textContent = statusMsg;
        connectionStatus.style.background = 'rgba(34, 197, 94, 0.1)';
    } else {
        statusDot.style.backgroundColor = 'var(--danger)';
        statusDot.style.boxShadow = '0 0 8px var(--danger)';
        statusText.textContent = 'Disconnected';
        connectionStatus.style.background = 'rgba(239, 68, 68, 0.1)';
    }
}
