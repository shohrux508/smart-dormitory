const API_URL = '/api/devices';
const WS_URL = ((window.location.protocol === 'https:') ? 'wss://' : 'ws://') + window.location.host + '/ws/dashboard';

// DOM Elements
const devicesGrid = document.getElementById('devices-grid');
const connectionStatus = document.getElementById('connection-status');
const statusDot = connectionStatus.querySelector('.dot');
const statusText = connectionStatus.querySelector('.text');
const toastContainer = document.getElementById('toast-container');

// State
let devices = [];
let pendingUpdates = new Set(); // Track devices currently being toggled locally
let websocket = null;
let reconnectTimer = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchDevices();
    connectWebSocket();
});

// --- WebSockets ---

function connectWebSocket() {
    console.log('Connecting to WebSocket...', WS_URL);
    websocket = new WebSocket(WS_URL);

    websocket.onopen = () => {
        console.log('WebSocket Connected');
        setSystemOnline(true);
        if (reconnectTimer) {
            clearInterval(reconnectTimer);
            reconnectTimer = null;
        }
        showToast('Connected to server', 'success');
    };

    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('Error parsing WS message:', e);
        }
    };

    websocket.onclose = () => {
        console.log('WebSocket Disconnected');
        setSystemOnline(false);
        // Try to reconnect every 3 seconds
        if (!reconnectTimer) {
            reconnectTimer = setInterval(connectWebSocket, 3000);
        }
    };

    websocket.onerror = (error) => {
        console.error('WebSocket Error:', error);
        websocket.close();
    };
}

function handleWebSocketMessage(data) {
    if (data.type === 'state_update') {
        updateDeviceState(data.device_id, data.state);
    }
}

function updateDeviceState(deviceId, newState) {
    // Update local model
    const device = devices.find(d => d.device_id === deviceId);
    if (device) {
        device.state = newState;

        // Update UI if we are NOT currently pending a user action on this device
        // OR if the update matches our optimistic expectation (clearing pending status)
        if (pendingUpdates.has(deviceId)) {
            // If we get an update that matches what we wanted, we can clear pending
            // But actually, we usually clear pending after HTTP IDLE. 
            // Let's just update the UI always to ensure consistency with server.
            // If user clicked 'ON', UI is 'ON'. Server says 'ON'. UI stays 'ON'.
        }

        // Update Card UI
        const card = devicesGrid.querySelector(`.device-card[data-id="${deviceId}"]`);
        if (card) {
            updateDeviceCard(card, device);
            // If the state matches what we set optimistically, remove processing class (if any)
            // But usually we remove processing after HTTP response. 
        }
    } else {
        // New device? Reload list
        fetchDevices();
    }
}

// --- HTTP API ---

async function fetchDevices() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) throw new Error('Network response was not ok');
        devices = await response.json();
        renderDevices();
    } catch (error) {
        console.error('Error fetching devices:', error);
        setSystemOnline(false);
    }
}

// --- UI Logic ---

function renderDevices() {
    devicesGrid.innerHTML = '';
    devices.forEach(device => {
        const card = createDeviceCard(device);
        devicesGrid.appendChild(card);
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
        <h3 class="device-name">${device.title || device.device_id}</h3>
        <p class="device-room">Room ${device.room || 'Unknown'}</p>
        
        <div class="toggle-switch">
            <span class="switch-label">${device.state}</span>
            <div class="switch-btn"></div>
        </div>
    `;

    // Attach listener
    const switchEl = card.querySelector('.toggle-switch');
    switchEl.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDevice(device);
    });

    return card;
}

function updateDeviceCard(card, device) {
    card.className = `device-card ${device.state === 'ON' ? 'on' : ''} ${device.status === 'offline' ? 'offline' : ''}`;

    // Preserve processing state if present (managed by toggleDevice)
    if (pendingUpdates.has(device.device_id)) {
        card.classList.add('processing');
    }

    const statusEl = card.querySelector('.device-status');
    statusEl.textContent = device.status;
    statusEl.className = `device-status ${device.status === 'online' ? 'status-online' : 'status-offline'}`;

    card.querySelector('.switch-label').textContent = device.state;
}

async function toggleDevice(device) {
    const deviceId = device.device_id;

    if (device.status === 'offline' || pendingUpdates.has(deviceId)) return;

    const oldState = device.state;
    const newState = oldState === 'ON' ? 'OFF' : 'ON';
    const action = oldState === 'ON' ? 'turn_off' : 'turn_on';

    // 1. Optimistic Update
    pendingUpdates.add(deviceId);
    device.state = newState;

    const card = devicesGrid.querySelector(`.device-card[data-id="${deviceId}"]`);
    if (card) {
        card.classList.add('processing');
        updateDeviceCard(card, device);
    }

    try {
        const response = await fetch(`/api/devices/${deviceId}/${action}`, { method: 'POST' });
        if (!response.ok) throw new Error('Command failed');

        const result = await response.json();

        // Success
        showToast(`Device ${newState === 'ON' ? 'turned ON' : 'turned OFF'}`, 'success');

    } catch (error) {
        console.error('Error toggling device:', error);

        // Revert State
        device.state = oldState;
        if (card) updateDeviceCard(card, device);
        showToast('Failed to toggle device', 'error');

    } finally {
        pendingUpdates.delete(deviceId);
        if (card) card.classList.remove('processing');
    }
}

function setSystemOnline(isOnline) {
    if (isOnline) {
        statusDot.style.backgroundColor = 'var(--success)';
        statusDot.style.boxShadow = '0 0 8px var(--success)';
        statusText.textContent = 'System Online';
        connectionStatus.classList.add('online');
    } else {
        statusDot.style.backgroundColor = 'var(--danger)';
        statusDot.style.boxShadow = '0 0 8px var(--danger)';
        statusText.textContent = 'Connection Lost';
        connectionStatus.classList.remove('online');
    }
}

// --- Toast System ---

function showToast(message, type = 'info') {
    const iconMap = {
        success: '✔️',
        error: '❌',
        info: 'ℹ️'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${iconMap[type]}</span>
        <span class="toast-message">${message}</span>
    `;

    toastContainer.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Remove after 3s
    setTimeout(() => {
        toast.classList.remove('show');
        toast.addEventListener('transitionend', () => {
            toast.remove();
        });
    }, 4000);
}
