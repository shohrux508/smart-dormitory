const API_URL = '/api/devices';
// Polling removed in favor of WebSocket
// const UPDATE_INTERVAL = 2000; 

// DOM Elements
const devicesGrid = document.getElementById('devices-grid');
const connectionStatus = document.getElementById('connection-status');
const statusDot = connectionStatus.querySelector('.dot');
const statusText = connectionStatus.querySelector('.text');

// State
let devices = [];
let pendingUpdates = new Set(); // Track devices currently being toggled
let ws = null;
let reconnectTimer = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
});

function initWebSocket() {
    // Determine protocol (ws or wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('Connected to Dashboard WebSocket');
        setSystemOnline(true);
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('Error parsing WS message:', e);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        setSystemOnline(false);
        // Try to reconnect in 3 seconds
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(initWebSocket, 3000);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        ws.close();
    };
}

function handleWebSocketMessage(message) {
    if (message.type === 'full_state') {
        // Initial load or full refresh
        devices = message.devices;
        updateUI();
    } else if (message.type === 'state_change') {
        const device = devices.find(d => d.device_id === message.device_id);
        if (device) {
            device.state = message.state;
            // Also update status if implied (usually online if sending updates)
            device.status = 'online';
            updateUI();
        }
    } else if (message.type === 'device_connected') {
        // Check if exists
        const index = devices.findIndex(d => d.device_id === message.device.device_id);
        if (index !== -1) {
            devices[index] = message.device;
        } else {
            devices.push(message.device);
        }
        updateUI();
    } else if (message.type === 'device_disconnected') {
        const device = devices.find(d => d.device_id === message.device_id);
        if (device) {
            device.status = 'offline';
            updateUI();
        }
    }
}

// Kept for initial API fetch fallback if needed, but WS handles it now.
// Leaving fetchDevices for reference or fallback not used here.
async function fetchDevices() {
    // Deprecated by WebSocket
}

async function fetchDevices() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();

        // Merge data: Don't overwrite devices that are being updated by user
        if (devices.length === 0) {
            devices = data;
        } else {
            // Update devices array, but respect pending updates
            devices = data.map(serverDevice => {
                if (pendingUpdates.has(serverDevice.device_id)) {
                    // Find local version which has the optimistic state
                    const localDevice = devices.find(d => d.device_id === serverDevice.device_id);
                    return localDevice || serverDevice;
                }
                return serverDevice;
            });
        }

        updateUI();
        setSystemOnline(true);
    } catch (error) {
        console.error('Error fetching devices:', error);
        setSystemOnline(false);
    }
}

function updateUI() {
    // If grid is empty (first load), clear shimmer
    if (devicesGrid.querySelector('.loading-card')) {
        devicesGrid.innerHTML = '';
    }

    // Get existing cards
    const existingCards = Array.from(devicesGrid.children);

    // Remove deleted devices
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
        <h3 class="device-name">${device.device_id}</h3>
        <p class="device-room">Room 101</p>
        
        <div class="toggle-switch">
            <span class="switch-label">${device.state}</span>
            <div class="switch-btn"></div>
        </div>
    `;

    // Attach listener ONLY to the switch
    const switchEl = card.querySelector('.toggle-switch');
    switchEl.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent card click if we ever add one
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
    card.querySelector('.switch-label').textContent = device.state;
}

// Logic: Turn On/Off
async function toggleDevice(deviceArg) {
    const deviceId = deviceArg.device_id;

    // Find the CURRENT state from the global array,
    // because 'deviceArg' comes from the event listener closure and might be stale.
    const currentDevice = devices.find(d => d.device_id === deviceId);
    if (!currentDevice) return;

    // Prevent if offline or already processing
    if (currentDevice.status === 'offline' || pendingUpdates.has(deviceId)) return;

    const newState = currentDevice.state === 'ON' ? 'OFF' : 'ON';
    const action = currentDevice.state === 'ON' ? 'turn_off' : 'turn_on';

    // 1. Mark as pending
    pendingUpdates.add(deviceId);

    // 2. Update Local State (Optimistic)
    // We update the object in the 'devices' array directly
    const deviceIndex = devices.indexOf(currentDevice);
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
        // Success: Remove from pending, next poll will confirm state
        // For smoother UX, remove processing class now
        if (card) card.classList.remove('processing');
        pendingUpdates.delete(deviceId);

    } catch (error) {
        console.error('Error toggling device:', error);
        // Revert State
        if (deviceIndex !== -1) {
            devices[deviceIndex].state = (newState === 'ON' ? 'OFF' : 'ON'); // toggle back
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
        statusText.textContent = 'System Online';
        connectionStatus.style.background = 'rgba(34, 197, 94, 0.1)';
    } else {
        statusDot.style.backgroundColor = 'var(--danger)';
        statusDot.style.boxShadow = '0 0 8px var(--danger)';
        statusText.textContent = 'Connection Lost';
        connectionStatus.style.background = 'rgba(239, 68, 68, 0.1)';
    }
}
