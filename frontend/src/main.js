import './styles/base.css';
import { renderLogin } from './pages/login';
import { renderDashboard } from './pages/dashboard';
import { renderMap } from './pages/map';
import { renderAnalysis } from './pages/analysis';
import { renderReport } from './pages/report';
import { renderWatchdog } from './pages/watchdog';

const app = document.querySelector('#app');

// Simple Router
const routes = {
    '/': renderLogin,
    '/dashboard': renderDashboard,
    '/map': renderMap,
    '/analysis': renderAnalysis,
    '/report': renderReport,
    '/watchdog': renderWatchdog
};

export function navigate(path, state = {}) {
    const query = state.id ? `?id=${encodeURIComponent(state.id)}` : '';
    window.history.pushState(state, '', path + query);
    handleRoute();
}

function handleRoute() {
    if (store.pageCleanup) { store.pageCleanup(); store.pageCleanup = null; }
    if (store.dashboardCleanup) { store.dashboardCleanup(); store.dashboardCleanup = null; }
    if (location.pathname !== '/' && !localStorage.getItem('token')) {
        window.history.replaceState({}, '', '/');
    }
    const path = window.location.pathname;
    const renderer = routes[path] || routes['/'];
    app.innerHTML = '';
    renderer(app);
}

window.addEventListener('popstate', handleRoute);
window.addEventListener('load', handleRoute);

// Global State
export const store = {
    user: null,
    currentAnalysisId: null,
    isAuthenticated: () => !!localStorage.getItem('token')
};

// Load user from localStorage
if (localStorage.getItem('user')) {
    store.user = JSON.parse(localStorage.getItem('user'));
}

/**
 * Authenticated fetch wrapper - adds JWT token to all requests
 */
export async function authFetch(url, options = {}) {
    const token = localStorage.getItem('token');

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        ...options,
        headers
    });

    // If unauthorized, redirect to login
    if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        store.user = null;
        navigate('/');
        return response;
    }

    return response;
}

/**
 * Logout helper - clears token and redirects
 */
export function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    store.user = null;
    navigate('/');
}
