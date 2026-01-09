/**
 * ET Phone Home - Web Dashboard
 * Frontend JavaScript for real-time client monitoring
 */

// State
let apiKey = null;
let ws = null;
let wsReconnectTimer = null;
let clients = [];

// DOM elements (populated on init)
let elements = {};

/**
 * Initialize the application
 */
function initApp() {
  // Cache DOM elements
  elements = {
    authModal: document.getElementById('authModal'),
    apiKeyInput: document.getElementById('apiKeyInput'),
    authError: document.getElementById('authError'),
    wsStatus: document.getElementById('wsStatus'),
    wsStatusText: document.getElementById('wsStatusText'),
    onlineCount: document.getElementById('onlineCount'),
    serverStatus: document.getElementById('serverStatus'),
    tunnelStatus: document.getElementById('tunnelStatus'),
    clientStatus: document.getElementById('clientStatus'),
    clientList: document.getElementById('clientList'),
    activityStream: document.getElementById('activityStream'),
  };

  // Check for stored API key
  apiKey = localStorage.getItem('etphonehome_api_key');

  if (apiKey) {
    // Validate stored key
    validateAndConnect();
  } else {
    showAuthModal();
  }

  // Handle enter key in auth input
  elements.apiKeyInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      authenticate();
    }
  });
}

/**
 * Show the authentication modal
 */
function showAuthModal() {
  elements.authModal.classList.remove('hidden');
  elements.apiKeyInput.focus();
}

/**
 * Hide the authentication modal
 */
function hideAuthModal() {
  elements.authModal.classList.add('hidden');
}

/**
 * Authenticate with the provided API key
 */
async function authenticate() {
  const key = elements.apiKeyInput.value.trim();
  if (!key) {
    elements.authError.textContent = 'Please enter an API key';
    return;
  }

  elements.authError.textContent = '';
  apiKey = key;

  try {
    const valid = await validateApiKey(key);
    if (valid) {
      localStorage.setItem('etphonehome_api_key', key);
      hideAuthModal();
      connectWebSocket();
      loadDashboard();
    } else {
      elements.authError.textContent = 'Invalid API key';
      apiKey = null;
    }
  } catch (err) {
    elements.authError.textContent = 'Connection failed: ' + err.message;
    apiKey = null;
  }
}

/**
 * Validate API key by making a test request
 */
async function validateApiKey(key) {
  try {
    const response = await fetch('/api/v1/dashboard', {
      headers: { 'Authorization': `Bearer ${key}` }
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

/**
 * Validate stored key and connect
 */
async function validateAndConnect() {
  try {
    const valid = await validateApiKey(apiKey);
    if (valid) {
      hideAuthModal();
      connectWebSocket();
      loadDashboard();
    } else {
      // Clear invalid stored key
      localStorage.removeItem('etphonehome_api_key');
      apiKey = null;
      showAuthModal();
    }
  } catch (err) {
    showAuthModal();
  }
}

/**
 * Make an authenticated API request
 */
async function apiFetch(endpoint) {
  const response = await fetch(endpoint, {
    headers: { 'Authorization': `Bearer ${apiKey}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      // Auth failed, show login
      localStorage.removeItem('etphonehome_api_key');
      apiKey = null;
      showAuthModal();
      throw new Error('Authentication required');
    }
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

/**
 * Connect to WebSocket for real-time updates
 */
function connectWebSocket() {
  if (ws) {
    ws.close();
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(apiKey)}`;

  setWsStatus('connecting');

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setWsStatus('connected');
    clearTimeout(wsReconnectTimer);
  };

  ws.onclose = (event) => {
    setWsStatus('disconnected');
    // Reconnect after delay (unless auth error)
    if (event.code !== 4001) {
      wsReconnectTimer = setTimeout(connectWebSocket, 3000);
    }
  };

  ws.onerror = () => {
    setWsStatus('error');
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleWsMessage(message);
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  };

  // Ping every 30 seconds to keep connection alive
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    }
  }, 30000);
}

/**
 * Set WebSocket connection status indicator
 */
function setWsStatus(status) {
  const statusClasses = {
    connecting: '',
    connected: 'connected',
    disconnected: '',
    error: ''
  };
  const statusTexts = {
    connecting: 'Connecting...',
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Connection error'
  };

  elements.wsStatus.className = 'status-dot ' + (statusClasses[status] || '');
  elements.wsStatusText.textContent = statusTexts[status] || status;
}

/**
 * Handle incoming WebSocket messages
 */
function handleWsMessage(message) {
  switch (message.type) {
    case 'initial_state':
      clients = message.data.clients || [];
      renderClients();
      updateStats(message.data);
      break;

    case 'client.connected':
      addActivityItem({
        timestamp: message.timestamp,
        type: 'client.connected',
        client_name: message.data.display_name,
        summary: 'Connected'
      });
      // Refresh client list
      loadClients();
      break;

    case 'client.disconnected':
      addActivityItem({
        timestamp: message.timestamp,
        type: 'client.disconnected',
        client_name: message.data.display_name,
        summary: 'Disconnected'
      });
      // Refresh client list
      loadClients();
      break;

    case 'command_executed':
      addActivityItem({
        timestamp: message.timestamp,
        type: 'command_executed',
        client_name: message.data.client_name,
        summary: message.data.command || 'Command executed'
      });
      break;

    default:
      console.log('Unknown message type:', message.type);
  }
}

/**
 * Load dashboard data
 */
async function loadDashboard() {
  try {
    const [dashboard, clientsData, events] = await Promise.all([
      apiFetch('/api/v1/dashboard'),
      apiFetch('/api/v1/clients'),
      apiFetch('/api/v1/events')
    ]);

    // Update dashboard stats
    updateDashboardStats(dashboard);

    // Update clients
    clients = clientsData.clients || [];
    renderClients();

    // Update activity stream
    renderActivityStream(events.events || []);

  } catch (err) {
    console.error('Failed to load dashboard:', err);
  }
}

/**
 * Load just the clients list
 */
async function loadClients() {
  try {
    const data = await apiFetch('/api/v1/clients');
    clients = data.clients || [];
    renderClients();

    // Update online count
    const onlineCount = clients.filter(c => c.online).length;
    elements.onlineCount.textContent = `${onlineCount} online`;

  } catch (err) {
    console.error('Failed to load clients:', err);
  }
}

/**
 * Update dashboard statistics
 */
function updateDashboardStats(data) {
  // Server status
  const uptime = formatUptime(data.server.uptime_seconds);
  elements.serverStatus.textContent = `Uptime ${uptime} · v${data.server.version}`;

  // Tunnel status
  elements.tunnelStatus.textContent = `${data.tunnels.active} active connections`;

  // Client status
  elements.clientStatus.textContent = `${data.clients.online} online / ${data.clients.total} total`;

  // Online count pill
  elements.onlineCount.textContent = `${data.clients.online} online`;
}

/**
 * Update stats from WebSocket initial state
 */
function updateStats(data) {
  elements.onlineCount.textContent = `${data.online_count} online`;
  elements.clientStatus.textContent = `${data.online_count} online / ${data.total_count} total`;
  elements.tunnelStatus.textContent = `${data.online_count} active connections`;
}

/**
 * Render the clients list
 */
function renderClients() {
  if (!clients || clients.length === 0) {
    elements.clientList.innerHTML = '<div class="empty-state">No clients registered</div>';
    return;
  }

  // Sort: online first, then by name
  const sorted = [...clients].sort((a, b) => {
    if (a.online !== b.online) return b.online ? 1 : -1;
    return (a.display_name || '').localeCompare(b.display_name || '');
  });

  elements.clientList.innerHTML = sorted.map(client => `
    <div class="list-item" onclick="viewClient('${client.uuid}')">
      <div class="row" style="flex: 1; min-width: 0;">
        <img class="icon" src="/static/icons/icon_client.svg" alt="Client" style="width: 28px; height: 28px;" />
        <div class="client-info">
          <div class="client-name">${escapeHtml(client.display_name || client.hostname || 'Unknown')}</div>
          <div class="stat">${escapeHtml(formatTags(client))}</div>
        </div>
      </div>
      <span class="pill ${client.online ? 'pill-online' : 'pill-offline'}">${client.online ? 'Online' : 'Offline'}</span>
    </div>
  `).join('');
}

/**
 * Render the activity stream
 */
function renderActivityStream(events) {
  if (!events || events.length === 0) {
    elements.activityStream.innerHTML = '<div class="empty-state">No recent activity</div>';
    return;
  }

  elements.activityStream.innerHTML = events.map(event => {
    const time = formatTime(event.timestamp);
    const typeClass = getEventTypeClass(event.type);
    return `
      <div class="timeline-item ${typeClass}">
        ${time} · ${escapeHtml(event.type)} · ${escapeHtml(event.client_name)}
      </div>
    `;
  }).join('');
}

/**
 * Add a new activity item to the stream
 */
function addActivityItem(event) {
  const time = formatTime(event.timestamp);
  const typeClass = getEventTypeClass(event.type);

  const item = document.createElement('div');
  item.className = `timeline-item ${typeClass}`;
  item.innerHTML = `${time} · ${escapeHtml(event.type)} · ${escapeHtml(event.client_name)}`;

  // Remove empty state if present
  const emptyState = elements.activityStream.querySelector('.empty-state');
  if (emptyState) {
    emptyState.remove();
  }

  // Add to top of list
  elements.activityStream.insertBefore(item, elements.activityStream.firstChild);

  // Limit to 20 items
  while (elements.activityStream.children.length > 20) {
    elements.activityStream.removeChild(elements.activityStream.lastChild);
  }
}

/**
 * Navigate to client detail page
 */
function viewClient(uuid) {
  window.location.href = `/client.html?uuid=${encodeURIComponent(uuid)}`;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format uptime in human-readable format
 */
function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/**
 * Format timestamp to time only
 */
function formatTime(isoString) {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  } catch (err) {
    return '--:--';
  }
}

/**
 * Format client tags for display
 */
function formatTags(client) {
  const parts = [];
  if (client.purpose) parts.push(client.purpose);
  if (client.tags && client.tags.length > 0) {
    parts.push(client.tags.slice(0, 3).join(', '));
  }
  if (client.platform) {
    // Shorten platform string
    const platform = client.platform.split(' ')[0];
    parts.push(platform);
  }
  return parts.join(' · ') || 'No tags';
}

/**
 * Get CSS class for event type
 */
function getEventTypeClass(type) {
  if (type.includes('connected')) return 'connected';
  if (type.includes('disconnected')) return 'disconnected';
  if (type.includes('command')) return 'command';
  return '';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
