import { navigate, store } from '../main';

export function Navbar() {
  const nav = document.createElement('nav');
  nav.className = 'navbar';

  const currentPath = window.location.pathname;

  nav.innerHTML = `
        <div class="navbar-brand" id="nav-brand" style="cursor: pointer">
            <span>ECO-SENTINEL</span>
        </div>
        <div class="navbar-nav">
            <button class="nav-btn ${currentPath === '/dashboard' ? 'active' : ''}" id="nav-dashboard">Dashboard</button>
            <button class="nav-btn ${currentPath === '/map' ? 'active' : ''}" id="nav-map">New Operation</button>
            <button class="nav-btn ${currentPath === '/watchdog' ? 'active' : ''}" id="nav-watchdog">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px; vertical-align: middle;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M12 6v6l4 2"></path>
                </svg>
                Watchdog
            </button>
            <button class="nav-btn logout" id="nav-logout">Logout</button>
        </div>
    `;

  nav.querySelector('#nav-brand').addEventListener('click', () => {
    navigate('/dashboard');
  });

  nav.querySelector('#nav-dashboard').addEventListener('click', () => {
    navigate('/dashboard');
  });

  nav.querySelector('#nav-map').addEventListener('click', () => {
    navigate('/map');
  });

  nav.querySelector('#nav-watchdog').addEventListener('click', () => {
    navigate('/watchdog');
  });

  nav.querySelector('#nav-logout').addEventListener('click', async () => {

    store.user = null;
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    navigate('/');
  });

  return nav;
}
