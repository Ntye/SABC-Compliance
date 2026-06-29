# BdC Compliance Platform — Frontend

React 18 + Vite + Tailwind CSS frontend for the BdC Compliance Platform.  
Communicates with the FastAPI backend over HTTP and WebSocket.

---

## Quick Start

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

App opens at **http://localhost:5173**

The backend must be running at **http://localhost:3000** (start it first — see `../backend/README.md`).

---

## Prerequisites

```bash
# Node.js 18+ required
node --version    # must be 18 or higher
npm --version
```

---

## Available Scripts

```bash
npm run dev       # Start dev server with hot-reload (port 5173)
npm run build     # Production build → dist/
npm run preview   # Serve the production build locally
```

---

## First Login

1. Start the backend (`cd ../backend && bash launch.sh`)
2. Copy the **admin username and password** printed to the backend console on first run
3. Open http://localhost:5173
4. You will be redirected to `/login` automatically
5. Enter the credentials and click **Sign in**

After login a JWT is stored in `localStorage` (`bdc_jwt_token`). You stay logged in across page refreshes until you sign out or the token expires (24 hours by default).

---

## Configuration

### Backend URL

The default backend URL is `http://localhost:3000`.  
You can change it **without restarting** using the inline editor at the bottom of the sidebar — click the URL to edit it. The value persists to `localStorage`.

### Environment variable (build-time)

Create a `.env.local` file to override the default at build time:

```bash
# frontend/.env.local
VITE_API_BASE=http://my-server:3000
```

---

## Authentication

Two credential types coexist:

| Type | Storage | Used for |
|------|---------|---------|
| JWT (user session) | `bdc_jwt_token` in localStorage | Web UI login via username + password |
| API Key | `bdc_api_key` in localStorage | Machine-to-machine, power-user header |

The `Authorization: Bearer <jwt>` header takes priority. If no JWT is present, the API key is sent as `X-API-Key`. On a 401 response the JWT is cleared and the user is redirected to `/login`.

**Sign out** button in the sidebar footer clears the JWT and returns to `/login`.

---

## Project Structure

```
frontend/
  index.html               # HTML entry point — loads Google Fonts
  vite.config.js
  tailwind.config.js       # Custom BdC color tokens
  postcss.config.js
  src/
    config.js              # Frozen config (reads VITE_API_BASE)
    index.css              # Tailwind directives + toast animation
    main.jsx               # React root mount
    App.jsx                # Router — /login is public, Shell wraps auth routes
    lib/
      api.js               # All API calls — never use fetch() in components
      tw.js                # Tailwind class-string helpers
    context/
      ToastContext.jsx      # Portal-based toast stack (top-right, 4s auto-dismiss)
    hooks/
      useApi.js            # Generic useApi(fn, {deps, immediate}) hook
    components/
      layout/
        Shell.jsx          # Route guard + grid layout (sidebar + header + outlet)
        Sidebar.jsx        # Nav, gateway URL editor, API docs link, sign out
        Header.jsx         # Page title, masked API key, copy/init buttons
      common/
        Button.jsx         # Primary / secondary / danger, sm / md sizes
        Badge.jsx          # Coloured pill for status/role/framework
        StatusDot.jsx      # Coloured dot for node/job status
        ConfirmDialog.jsx  # React portal modal with confirm/cancel
        SectionLabel.jsx   # Uppercase section header
        EmptyState.jsx     # Centered empty state with icon
        Spinner.jsx        # Animated SVG spinner (used inside buttons)
    pages/
      LoginPage.jsx        # ✅ Username + password form → JWT → /overview
      ApiKeysPage.jsx      # ✅ Create, list, revoke API keys
      OverviewPage.jsx     # 🔜 Feature 6
      NodesPage.jsx        # 🔜 Feature 2
      AddServerPage.jsx        # 🔜 Feature 2
      JobsPage.jsx         # 🔜 Feature 3
      CompliancePage.jsx   # 🔜 Feature 4
      PuppetRulesPage.jsx  # 🔜 Feature 5
      AuditLogPage.jsx     # 🔜 Feature 6
```

---

## Design System

### Colours (from `tailwind.config.js`)

| Token | Value | Used for |
|-------|-------|---------|
| `brand` | `#C0281F` | Primary buttons, active nav, logo |
| `surface.page` | `#F8F6F3` | Page background |
| `surface.card` | `#FFFFFF` | Card backgrounds |
| `sidebar.bg` | `#1C1C1E` | Sidebar background |
| `console.bg` | `#0C0E0F` | Log panels (Jobs page only) |
| `console.text` | `#C8D0D4` | Log text |

### Typography

- **DM Sans** — all UI text (`font-sans`)
- **IBM Plex Mono** — console areas and code only (`font-mono`)

### Console aesthetic rule

The dark console theme (`bg-console-bg`, `font-mono`, `text-console-*`) appears **only** in:
- Log output panel in `JobsPage`
- SSH setup helper in `AddServerPage`
- Puppet/InSpec code editors in `PuppetRulesPage`

It never appears elsewhere in the UI.

---

## API Docs Link

The sidebar footer contains a link to `{gatewayUrl}/docs` which opens the FastAPI Swagger UI in a new tab — the primary reference for all available endpoints.

---

## Features Roadmap

| Feature | Status | Pages updated |
|---------|--------|--------------|
| 0 — Scaffolding | ✅ Done | All config files |
| 1 — Auth | ✅ Done | LoginPage, ApiKeysPage, Shell, Sidebar, Header |
| 2 — Node Registry | ✅ Done | NodesPage, AddServerPage |
| 3 — Jobs | 🔜 | JobsPage (WebSocket log stream) |
| 4 — Compliance | 🔜 | CompliancePage |
| 5 — Rules | 🔜 | PuppetRulesPage (4-step stepper) |
| 6 — Health & Audit | 🔜 | OverviewPage, AuditLogPage |
