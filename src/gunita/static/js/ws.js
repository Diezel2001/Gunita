/* ═══════════════════════════════════════════════════════════════════════
   ws.js — WebSocket connection for live graph + search updates
   ═══════════════════════════════════════════════════════════════════════ */

const WsManager = (() => {
    let _ws = null;
    let _connected = false;
    let _reconnectTimer = null;
    let _onGraphUpdate = null;
    let _onSearchUpdate = null;
    let _onDisconnect = null;
    let _pingInterval = null;
    const RECONNECT_DELAY = 3000;
    const PING_INTERVAL = 25000;

    /**
     * Initialize WebSocket connection.
     */
    function init(callbacks = {}) {
        _onGraphUpdate = callbacks.onGraphUpdate || null;
        _onSearchUpdate = callbacks.onSearchUpdate || null;
        _onDisconnect = callbacks.onDisconnect || null;
        connect();
    }

    function connect() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${window.location.host}/ws`;
            _ws = new WebSocket(url);

            _ws.onopen = () => {
                _connected = true;
                updateStatus(true);
                // Subscribe to graph updates
                send({ type: 'subscribe_graph' });
                // Start ping to keep alive
                if (_pingInterval) clearInterval(_pingInterval);
                _pingInterval = setInterval(() => {
                    if (_connected) {
                        send({ type: 'ping' });
                    }
                }, PING_INTERVAL);
            };

            _ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    handleMessage(msg);
                } catch (e) {
                    // ignore parse errors
                }
            };

            _ws.onclose = () => {
                _connected = false;
                updateStatus(false);
                if (_pingInterval) clearInterval(_pingInterval);
                // Reconnect after delay
                scheduleReconnect();
            };

            _ws.onerror = () => {
                _connected = false;
                updateStatus(false);
            };
        } catch (e) {
            _connected = false;
            updateStatus(false);
            scheduleReconnect();
        }
    }

    function scheduleReconnect() {
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        _reconnectTimer = setTimeout(() => {
            connect();
        }, RECONNECT_DELAY);
    }

    function send(msg) {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
            _ws.send(JSON.stringify(msg));
        }
    }

    function handleMessage(msg) {
        switch (msg.type) {
            case 'pong':
                // heartbeat response, ignore
                break;
            case 'subscribed':
                // subscription confirmed
                break;
            case 'graph_updated':
                if (_onGraphUpdate) _onGraphUpdate(msg);
                break;
            case 'search_results':
                if (_onSearchUpdate) _onSearchUpdate(msg);
                break;
            case 'refresh_needed':
                if (_onGraphUpdate) _onGraphUpdate(msg);
                break;
            default:
                break;
        }
    }

    function updateStatus(connected) {
        const el = document.getElementById('ws-status');
        if (el) {
            el.textContent = connected ? '🟢' : '⚪';
            el.title = connected ? 'WebSocket connected' : 'WebSocket disconnected';
        }
    }

    function isConnected() {
        return _connected;
    }

    function disconnect() {
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        if (_pingInterval) clearInterval(_pingInterval);
        if (_ws) {
            _ws.close();
            _ws = null;
        }
    }

    return { init, send, isConnected, disconnect };
})();