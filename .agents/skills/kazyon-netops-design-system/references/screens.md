# Kazyon NetOps — 12 Console Screen Blueprints

This file contains the exact markup, token classes, and state blueprints for all 12 screens of the Kazyon NetOps Console (`design/Kazyon NetOps Console.html`).
When implementing or updating any of these 12 pages in `frontend/src/views/`, follow the layout, `.kz-*` classes, token colors, and interactions from its section below.

## 1 · Login (`/login`)

```html
<div class="kz" data-theme="{{theme}}" style="min-height: 900px; display: flex; flex-wrap: wrap; background: var(--surface-000); color: var(--ink);">
  <aside style="flex: 1 1 520px; min-height: 360px; background: var(--brand-500); color: #1f1a17; padding: 48px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; gap: 32px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="width: 44px; height: 44px; border-radius: 12px; background: #1f1a17; color: #f47a20; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 22px;">K</span>
      <div><div style="font-weight: 800; font-size: 18px; line-height: 22px;">Kazyon NetOps</div><div style="font-size: 13px; line-height: 18px; font-weight: 500;">HQ IT Infrastructure</div></div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 16px; max-width: 520px;">
      <h1 style="margin: 0; font-size: 52px; line-height: 54px; font-weight: 800; letter-spacing: -0.02em;">Every branch online. Every ISP on the clock.</h1>
      <p style="margin: 0; font-size: 16px; line-height: 24px; font-weight: 500;">The AI support agent triages the service mailbox, runs dual-ping and 4G traceroute checks, escalates to NOOR, ORANGE and WE, and hands anything unusual to you.</p>
    </div>
    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
      <div style="background: var(--surface-000); color: var(--ink); border-radius: 14px; padding: 14px 18px; min-width: 140px;"><div style="font-size: 28px; line-height: 32px; font-weight: 800;">1,150</div><div style="font-size: 12px; line-height: 16px; font-weight: 600; color: var(--ink-muted);">branches monitored</div></div>
      <div style="background: var(--surface-000); color: var(--ink); border-radius: 14px; padding: 14px 18px; min-width: 140px;"><div style="font-size: 28px; line-height: 32px; font-weight: 800;">3</div><div style="font-size: 12px; line-height: 16px; font-weight: 600; color: var(--ink-muted);">network providers</div></div>
      <div style="background: var(--surface-000); color: var(--ink); border-radius: 14px; padding: 14px 18px; min-width: 140px;"><div style="font-size: 28px; line-height: 32px; font-weight: 800;">5</div><div style="font-size: 12px; line-height: 16px; font-weight: 600; color: var(--ink-muted);">regions</div></div>
    </div>
  </aside>
  <main style="flex: 1 1 480px; display: flex; align-items: center; justify-content: center; padding: 48px 24px; box-sizing: border-box;">
    <form style="width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 20px;" sc-camel-on-submit="{{noop}}">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
        <div class="kz-seg" role="group" aria-label="Environment">
          <sc-for list="{{envs}}" as="e" hint-placeholder-count="2">
            <button type="button" class="{{e.cls}}" sc-camel-on-click="{{e.pick}}">{{e.label}}</button>
          </sc-for>
        </div>
        <span style="display: flex; gap: 8px; align-items: center;"><span class="kz-live">API reachable · {{port}}</span><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" sc-camel-on-click="{{toggleTheme}}" aria-label="{{themeAria}}" aria-pressed="{{isDark}}">{{themeIcon}}</button></span>
      </div>
      <div>
        <h2 style="margin: 0 0 4px; font-size: 28px; line-height: 34px; font-weight: 700;">Sign in</h2>
        <p style="margin: 0; color: var(--ink-muted); font-size: 14px;">Use your Kazyon IT account.</p>
      </div>
      <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Username or email
        <input type="email" value="john.safwat@kazyon.com" style="height: 44px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); color: var(--ink); background: var(--surface-000);">
      </label>
      <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Password
        <input type="password" value="••••••••••" style="height: 44px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); color: var(--ink); background: var(--surface-000);">
      </label>
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
        <label style="display: flex; gap: 8px; align-items: center;"><input type="checkbox" checked="" style="accent-color: var(--brand-600); width: 16px; height: 16px;"> Keep me signed in</label>
        <a href="#">Forgot password?</a>
      </div>
      <a href="{{L.Main}}" class="kz-btn kz-btn-primary" style="height: 44px; justify-content: center; text-decoration: none; font-size: 15px;">Sign in</a>
      <p style="margin: 0; font-size: 12px; line-height: 18px; color: var(--ink-muted);">Access is granted by your Super Admin. Your role decides which pages and actions you see.</p>
    </form>
  </main>
</div>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:900}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { env: 'PROD' }; }
  renderVals() {
    var self = this, env = this.state.env;
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      isDark: this.themeName() === 'dark',
      themeIcon: this.themeName() === 'dark' ? '☀ Light' : '☾ Dark',
      themeAria: this.themeName() === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      envs: ['PROD', 'DEV'].map(function (e) { return { label: e + (e === 'PROD' ? ' :8084' : ' :8085'), cls: e === env ? 'on' : '', pick: function () { self.setState({ env: e }); } }; }),
      port: env === 'PROD' ? '10.100.109.9:8084' : '10.100.109.9:8085',
      noop: function (e) { e.preventDefault(); }
    };
  }
}
</script>
```

## 2 · Executive & SLA Dashboard (`/dashboard`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Dashboard" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1180px;">
  <div class="kz-page-hd">
    <div>
      <h1>Executive &amp; SLA Dashboard</h1>
      <p>1,150 branches · NOOR, ORANGE, WE · Updated 11:24 Cairo time</p>
    </div>
    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
      <div class="kz-seg" role="group" aria-label="Time range">
        <sc-for list="{{ranges}}" as="r" hint-placeholder-count="3">
          <button type="button" class="{{r.cls}}" sc-camel-on-click="{{r.pick}}">{{r.label}}</button>
        </sc-for>
      </div>
      <x-import component-from-global-scope="KzNet.Button" variant="secondary" icon="download">Export</x-import>
      <a href="{{L.Board}}" class="kz-btn kz-btn-primary" style="text-decoration: none;">+ New ticket</a>
    </div>
  </div>

  <x-import component-from-global-scope="KzNet.HealthBar" services="{{services}}"></x-import>

  <div class="kz-grid-kpi">
    <a href="{{L.TicketsList}}" aria-label="Open tickets: 37, view list" style="text-decoration: none; color: inherit; display: block;"><x-import component-from-global-scope="KzNet.KpiCard" label="Open tickets" value="{{k.open}}" icon="ticket" delta="+6" hint="vs. yesterday"></x-import></a>
    <a href="{{L.Escalations}}" aria-label="Needs human review: 4, open queue" style="text-decoration: none; color: inherit; display: block;"><x-import component-from-global-scope="KzNet.KpiCard" label="Needs human review" value="{{k.review}}" icon="alert" tone="critical" hint="Quota, MSAN, unknown mail"></x-import></a>
    <a href="{{L.Board}}" aria-label="Overdue 2 hour welcome: 3, open board" style="text-decoration: none; color: inherit; display: block;"><x-import component-from-global-scope="KzNet.KpiCard" label="Overdue 2h welcome" value="{{k.welcome}}" icon="mail" tone="warning" hint="ISP has not opened a case"></x-import></a>
    <a href="{{L.Board}}" aria-label="Overdue 4 to 6 hour update: 5, open board" style="text-decoration: none; color: inherit; display: block;"><x-import component-from-global-scope="KzNet.KpiCard" label="Overdue 4–6h update" value="{{k.followup}}" icon="clock" tone="warning" hint="Chasers sent automatically"></x-import></a>
    <a href="{{L.Replication}}" aria-label="Not updated today: 12, open replication monitor" style="text-decoration: none; color: inherit; display: block;"><x-import component-from-global-scope="KzNet.KpiCard" label="Not updated today" value="{{k.repl}}" icon="replication" delta="-3" hint="Replication Dashboard 09:00"></x-import></a>
  </div>

  <div class="kz-grid-3">
    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>Outages by ISP</h2><p>Tickets opened, {{rangeLabel}}</p></div></div>
      <div class="kz-card-bd"><x-import component-from-global-scope="KzNet.BarChart" data="{{byIsp}}"></x-import></div>
    </section>
    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>MTTR by ISP</h2><p>Mean hours, escalation → verified fix</p></div></div>
      <div class="kz-card-bd"><x-import component-from-global-scope="KzNet.BarChart" data="{{mttr}}" unit="h"></x-import></div>
    </section>
    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>Outages by failure type</h2><p>Diagnosis from dual-ping &amp; traceroute</p></div></div>
      <div class="kz-card-bd"><x-import component-from-global-scope="KzNet.BarChart" data="{{byType}}"></x-import></div>
    </section>
  </div>

  <div class="kz-grid-main">
    <section class="kz-card" style="overflow: hidden;">
      <div class="kz-card-hd" style="padding-bottom: 12px;">
        <div><h2>SLA watchlist</h2><p>Tickets waiting on an ISP, most urgent first</p></div>
        <a href="{{L.Board}}" style="font-size: 13px; font-weight: 600;">Open board</a>
      </div>
      <div class="kz-scroll-x">
        <sc-raw-table class="kz-table">
          <sc-raw-thead><sc-raw-tr><sc-raw-th>Ticket</sc-raw-th><sc-raw-th>Branch</sc-raw-th><sc-raw-th>ISP</sc-raw-th><sc-raw-th>Checks</sc-raw-th><sc-raw-th>Stage</sc-raw-th><sc-raw-th>SLA</sc-raw-th></sc-raw-tr></sc-raw-thead>
          <sc-raw-tbody>
            <sc-for list="{{watch}}" as="t" hint-placeholder-count="4">
              <sc-raw-tr>
                <sc-raw-td><a href="{{L.TicketDetail}}" class="kz-tcard-id">{{t.id}}</a></sc-raw-td>
                <sc-raw-td><div class="kz-nowrap" style="font-weight: 600;">{{t.branch}}</div><div class="kz-tcard-meta">{{t.region}} · {{t.failure}}</div></sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.IspBadge" isp="{{t.isp}}"></x-import></sc-raw-td>
                <sc-raw-td><div class="kz-tcard-pills"><sc-for list="{{t.checks}}" as="c" hint-placeholder-count="2"><x-import component-from-global-scope="KzNet.StatusPill" label="{{c.label}}" state="{{c.state}}"></x-import></sc-for></div></sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{t.tone}}">{{t.stage}}</x-import></sc-raw-td>
                <sc-raw-td class="kz-nowrap"><x-import component-from-global-scope="KzNet.SlaTimer" minutes-left="{{t.left}}" total-minutes="{{t.total}}"></x-import></sc-raw-td>
              </sc-raw-tr>
            </sc-for>
          </sc-raw-tbody>
        </sc-raw-table>
      </div>
    </section>
    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>Outages by region</h2><p>Open + resolved, {{rangeLabel}}</p></div></div>
      <div class="kz-card-bd"><x-import component-from-global-scope="KzNet.BarChart" data="{{byRegion}}"></x-import></div>
    </section>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1180}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { range: '7d' }; }
  renderVals() {
    var r = this.state.range;
    var m = r === '24h' ? 0.2 : r === '30d' ? 4.1 : 1;
    var n = function (v) { return Math.max(1, Math.round(v * m)); };
    var self = this;
    var opts = [['24h', 'Today'], ['7d', '7 days'], ['30d', '30 days']];
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      ranges: opts.map(function (o) { return { label: o[1], cls: o[0] === r ? 'on' : '', pick: function () { self.setState({ range: o[0] }); } }; }),
      rangeLabel: r === '24h' ? 'today' : r === '30d' ? 'last 30 days' : 'last 7 days',
      k: { open: 37, review: 4, welcome: 3, followup: 5, repl: 12 },
      services: [
        { name: 'vLLM · Gemma 4 26B', detail: '10.100.109.9:8002 · 412 ms', state: 'ok' },
        { name: 'IMAP / SMTP Mailbox', detail: 'Last poll 14 s ago', state: 'ok' },
        { name: 'PostgreSQL 16', detail: ':5434 · 18 conn', state: 'ok' },
        { name: 'Redis 7', detail: ':6384 · queue depth 9', state: 'degraded' }
      ],
      byIsp: [{ label: 'NOOR', value: n(64), hint: '906 stores' }, { label: 'ORANGE', value: n(21), hint: '181 stores' }, { label: 'WE', value: n(9), hint: '63 stores' }],
      mttr: [{ label: 'NOOR', value: 5.8 }, { label: 'ORANGE', value: 7.2 }, { label: 'WE', value: 9.4 }],
      byType: [{ label: 'Full outage', value: n(41) }, { label: '4G / LL down', value: n(23) }, { label: 'Internal switch', value: n(19) }, { label: 'Cables', value: n(11) }],
      byRegion: [{ label: 'Behera', value: n(31), hint: '350 stores' }, { label: 'Cairo', value: n(22), hint: '223 stores' }, { label: 'New October', value: n(18), hint: '212 stores' }, { label: 'Assyut', value: n(15), hint: '209 stores' }, { label: 'Giza', value: n(8), hint: '156 stores' }],
      watch: [
        { id: 'NET-1058', branch: '2009-Kafr Nasar', region: 'Giza', failure: 'Full outage', isp: 'NOOR', checks: [{ label: 'IP1', state: 'down' }, { label: 'IP2', state: 'skip' }], stage: 'Escalated · Welcome', tone: 'critical', left: -34, total: 120 },
        { id: 'NET-1055', branch: '1254-El Mansheya', region: 'Behera', failure: 'Full outage', isp: 'WE', checks: [{ label: 'IP1', state: 'down' }, { label: 'IP2', state: 'skip' }], stage: 'Escalated · Welcome', tone: 'brand', left: 18, total: 120 },
        { id: 'NET-1057', branch: '1173-Ghmrawy', region: 'Cairo', failure: 'Local loop down (4G)', isp: 'ORANGE', checks: [{ label: 'IP1', state: 'up' }, { label: 'IP2', state: 'down' }, { label: '4G', state: 'hub' }], stage: 'With ISP', tone: 'brand', left: 52, total: 300 },
        { id: 'NET-1046', branch: '1420-Sheikh Zayed 2', region: 'New October', failure: 'Site contact unreachable', isp: 'NOOR', checks: [{ label: 'IP1', state: 'down' }, { label: 'IP2', state: 'skip' }], stage: 'With ISP', tone: 'brand', left: 210, total: 300 }
      ]
    };
  }
}
</script>
```

## 3 · Kanban Board (`/tickets/board`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Kanban Board" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1040px;">
  <div class="kz-page-hd">
    <div>
      <h1>Ticket Board</h1>
      <p>Drag a card to change its status. The AI agent keeps working each ticket unless it is paused.</p>
    </div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <a href="{{L.TicketsList}}" class="kz-btn kz-btn-secondary" style="text-decoration: none;">List view</a>
      <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{openModal}}">+ Create manual ticket</button>
    </div>
  </div>

  <div class="kz-filters">
    <label class="kz-search" style="max-width: 320px;"><span class="kz-muted">Search</span><input type="search" placeholder="Branch, ticket, circuit ID" style="border: 0; background: transparent; outline: none; font: 500 13px var(--font-sans); color: var(--ink); flex: 1; min-width: 0;"></label>
    <sc-for list="{{ispChips}}" as="c" hint-placeholder-count="4">
      <button type="button" class="{{c.cls}}" sc-camel-on-click="{{c.pick}}">{{c.label}}</button>
    </sc-for>
    <label class="kz-chip">Region<sc-raw-select sc-camel-on-change="{{pickRegion}}" style="border: 0; font: 600 12px var(--font-sans); background: transparent;"><option>All</option><option>Behera</option><option>Cairo</option><option>New October</option><option>Assyut</option><option>Giza</option></sc-raw-select></label>
    <label class="kz-chip">Priority<sc-raw-select sc-camel-on-change="{{pickPrio}}" style="border: 0; font: 600 12px var(--font-sans); background: transparent;"><option>All</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></sc-raw-select></label>
    <label class="kz-chip">Trigger<sc-raw-select style="border: 0; font: 600 12px var(--font-sans); background: transparent;"><option>All</option><option>DIRECT_EMAIL</option><option>REPLICATION_DASHBOARD</option></sc-raw-select></label>
    <button type="button" class="{{pausedCls}}" sc-camel-on-click="{{togglePaused}}" aria-pressed="{{pausedOnly}}">AI paused only</button>
    <span class="kz-tcard-meta">{{shownCount}} tickets</span>
  </div>

  <div class="kz-board">
    <sc-for list="{{cols}}" as="col" hint-placeholder-count="8">
      <section class="{{col.cls}}" aria-label="{{col.name}}">
        <div class="kz-col-hd"><span class="kz-col-bar"></span><b>{{col.name}}</b><span>{{col.count}}</span></div>
        <sc-for list="{{col.items}}" as="t" hint-placeholder-count="2">
          <a href="{{L.TicketDetail}}" style="text-decoration: none; color: inherit;">
            <x-import component-from-global-scope="KzNet.TicketCard" ticket="{{t}}"></x-import>
          </a>
        </sc-for>
        <sc-if value="{{col.empty}}" hint-placeholder-val="{{false}}">
          <div style="border: 1.5px dashed var(--border-strong); border-radius: 10px; padding: 16px; text-align: center; font-size: 12px; color: var(--ink-muted);">No tickets</div>
        </sc-if>
      </section>
    </sc-for>
  </div>

  <sc-if value="{{modal}}" hint-placeholder-val="{{false}}">
    <div class="kz-modal-scrim">
      <div role="dialog" aria-modal="true" aria-label="Create manual ticket" class="kz-card" style="width: 100%; max-width: 560px; box-shadow: var(--shadow-raised);">
        <div class="kz-card-hd"><div><h2>Create manual ticket</h2><p>The agent picks it up from Diagnosing unless you pause AI.</p></div></div>
        <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px;">
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Branch SAP code<input value="2009" style="height: 40px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans);"></label>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Priority<sc-raw-select style="height: 40px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); background: var(--surface-000); color: var(--ink);"><option>HIGH</option><option>CRITICAL</option><option>MEDIUM</option><option>LOW</option></sc-raw-select></label>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Site contact phone<input placeholder="010…" style="height: 40px; padding: 0 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans);"></label>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Trigger<sc-raw-select style="height: 40px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); background: var(--surface-000); color: var(--ink);"><option>DIRECT_EMAIL</option><option>REPLICATION_DASHBOARD</option></sc-raw-select></label>
          <div style="grid-column: 1 / -1; display: flex; gap: 8px; align-items: center; padding: 10px 12px; background: var(--surface-100); border-radius: 10px; font-size: 13px;">
            <span style="font-weight: 600;">2009-Kafr Nasar</span><span class="kz-mono kz-muted">IP1 10.20.9.1 · IP2 10.20.9.2</span><x-import component-from-global-scope="KzNet.IspBadge" isp="NOOR"></x-import>
          </div>
          <label style="grid-column: 1 / -1; display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Issue details<textarea rows="3" style="padding: 10px 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); resize: vertical;">Store not syncing since 08:40. Router photo attached by Regional IT.</textarea></label>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{closeModal}}">Cancel</button>
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{closeModal}}">Create &amp; run diagnostics</button>
        </div>
      </div>
    </div>
  </sc-if>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1040}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { isp: 'ALL', modal: false }; }
  renderVals() {
    var self = this, isp = this.state.isp;
    var T = [
      { id: 'NET-1054', priority: 'MEDIUM', branch: '1450-Soliman Metwaly', region: 'Assyut', isp: 'NOOR', note: 'Replication: Not Updated', col: 0 },
      { id: 'NET-1053', priority: 'MEDIUM', branch: '1088-Gamal Salem', region: 'New October', isp: 'ORANGE', note: 'Replication: Not Updated', col: 0 },
      { id: 'NET-1052', priority: 'HIGH', branch: '1312-Damanhour 3', region: 'Behera', failure: 'Router photo check', isp: 'NOOR', note: 'Vision: analysing photo', col: 1 },
      { id: 'NET-1051', priority: 'LOW', branch: '1201-Hadayek El Ahram', region: 'Giza', failure: 'Internal switch', isp: 'NOOR', checks: [['IP1', 'up'], ['IP2', 'down']], note: 'Returned to GITSupport', col: 2 },
      { id: 'NET-1050', priority: 'MEDIUM', branch: '1188-Kom Hamada', region: 'Behera', failure: 'Cables unplugged', isp: 'NOOR', note: 'Awaiting new photo', col: 2 },
      { id: 'NET-1058', priority: 'CRITICAL', branch: '2009-Kafr Nasar', region: 'Giza', failure: 'Full outage', isp: 'NOOR', caseRef: '244010', checks: [['IP1', 'down'], ['IP2', 'skip']], sla: [-34, 120], col: 3 },
      { id: 'NET-1055', priority: 'HIGH', branch: '1254-El Mansheya', region: 'Behera', failure: 'Full outage', isp: 'WE', checks: [['IP1', 'down'], ['IP2', 'skip']], sla: [18, 120], col: 3 },
      { id: 'NET-1057', priority: 'HIGH', branch: '1173-Ghmrawy', region: 'Cairo', failure: 'Local loop down (4G)', isp: 'ORANGE', caseRef: '1-1312322942540', checks: [['IP1', 'up'], ['IP2', 'down'], ['4G', 'hub']], sla: [52, 300], col: 4 },
      { id: 'NET-1046', priority: 'HIGH', branch: '1420-Sheikh Zayed 2', region: 'New October', failure: 'Site contact unreachable', isp: 'NOOR', caseRef: '243860', sla: [210, 300], col: 4 },
      { id: 'NET-1047', priority: 'MEDIUM', branch: '1366-Nasr City 7', region: 'Cairo', failure: 'Full outage', isp: 'NOOR', caseRef: '243881', checks: [['IP1', 'up'], ['IP2', 'up']], note: 'Re-pinging after ISP closure', col: 5 },
      { id: 'NET-1049', priority: 'CRITICAL', branch: '1005-Tosson', region: 'Behera', failure: 'Quota consumed', isp: 'WE', caseRef: '8400809', aiPaused: true, note: 'Engineer notified', col: 6 },
      { id: 'NET-1041', priority: 'HIGH', branch: '1510-Abnoub', region: 'Assyut', failure: 'MSAN migration', isp: 'WE', aiPaused: true, note: 'Engineer notified', col: 6 },
      { id: 'NET-1044', priority: 'LOW', branch: '1099-Kafr El Dawar', region: 'Behera', failure: 'Cables', isp: 'NOOR', checks: [['IP1', 'up'], ['IP2', 'up']], note: 'Closed 08:14', col: 7 },
      { id: 'NET-1040', priority: 'MEDIUM', branch: '1222-Bab El Louq', region: 'Cairo', failure: 'Local loop down (4G)', isp: 'ORANGE', checks: [['IP1', 'up'], ['IP2', 'up']], note: 'Closed 07:02', col: 7 }
    ];
    var st = this.state;
    var shown = T.filter(function (t) {
      return (isp === 'ALL' || t.isp === isp) && (!st.region || st.region === 'All' || t.region === st.region) &&
        (!st.prio || st.prio === 'All' || t.priority === st.prio) && (!st.pausedOnly || t.aiPaused);
    });
    var names = [['Awaiting Regional IT', ''], ['New & Diagnosing', ''], ['Branch / Internal Action', ''], ['Escalated to ISP · 2h', 'isp'], ['With ISP · 4–6h loop', 'isp'], ['Verifying Fix', ''], ['Needs Human Review', 'human'], ['Resolved / Closed', 'done']];
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      ispChips: ['ALL', 'NOOR', 'ORANGE', 'WE'].map(function (k) { return { label: k === 'ALL' ? 'All ISPs' : k, cls: 'kz-chip' + (k === isp ? ' kz-chip-on' : ''), pick: function () { self.setState({ isp: k }); } }; }),
      cols: names.map(function (n, i) {
        var items = shown.filter(function (t) { return t.col === i; });
        return { name: n[0], cls: 'kz-col' + (n[1] ? ' kz-col-' + n[1] : ''), items: items, count: items.length, empty: items.length === 0 };
      }),
      pickRegion: function (e) { self.setState({ region: e.target.value }); },
      pickPrio: function (e) { self.setState({ prio: e.target.value }); },
      pausedOnly: !!st.pausedOnly,
      pausedCls: 'kz-chip' + (st.pausedOnly ? ' kz-chip-on' : ''),
      togglePaused: function () { self.setState({ pausedOnly: !self.state.pausedOnly }); },
      shownCount: shown.length,
      modal: this.state.modal,
      openModal: function () { self.setState({ modal: true }); },
      closeModal: function () { self.setState({ modal: false }); }
    };
  }
}
</script>
```

## 4 · Tickets List & Export (`/tickets`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Tickets List" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1000px;">
  <div class="kz-page-hd">
    <div>
      <h1>Tickets</h1>
      <p>All active and historical incidents · 1,284 tickets since 1 Jan 2026</p>
    </div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <x-import component-from-global-scope="KzNet.Button" variant="secondary" icon="download">Export CSV</x-import>
      <x-import component-from-global-scope="KzNet.Button" variant="primary" icon="download">Export to Excel</x-import>
    </div>
  </div>

  <div class="kz-card" style="padding: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
    <label class="kz-search" style="max-width: 300px;"><span class="kz-muted">Search</span><input type="search" placeholder="NET-, SAP code, case #, L.L ID" style="border: 0; background: transparent; outline: none; font: 500 13px var(--font-sans); color: var(--ink); flex: 1; min-width: 0;"></label>
    <sc-raw-select aria-label="Status" class="kz-chip"><option>Status: All open</option><option>Escalated to ISP</option><option>Needs Human Review</option><option>Resolved / Closed</option></sc-raw-select>
    <sc-raw-select aria-label="ISP" class="kz-chip"><option>ISP: All</option><option>NOOR</option><option>ORANGE</option><option>WE</option></sc-raw-select>
    <sc-raw-select aria-label="Region" class="kz-chip"><option>Region: All</option><option>Behera</option><option>Cairo</option><option>New October</option><option>Assyut</option><option>Giza</option></sc-raw-select>
    <sc-raw-select aria-label="Trigger" class="kz-chip"><option>Trigger: All</option><option>DIRECT_EMAIL</option><option>REPLICATION_DASHBOARD</option><option>UNKNOWN_ESCALATION</option></sc-raw-select>
    <sc-raw-select aria-label="Failure type" class="kz-chip"><option>Failure: All</option><option>FULL_OUTAGE</option><option>LOCAL_LOOP_DOWN_ON_4G</option><option>INTERNAL_LAN_SWITCH</option><option>CABLE_UNPLUGGED</option></sc-raw-select>
    <label class="kz-chip"><span>Opened</span><input type="date" value="2026-10-14" style="border: 0; font: 600 12px var(--font-sans); background: transparent; color: var(--ink);"></label>
    <span style="flex: 1;"></span>
    <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">Clear filters</button>
  </div>

  <section class="kz-card" style="overflow: hidden;">
    <div class="kz-scroll-x">
      <sc-raw-table class="kz-table">
        <sc-raw-thead><sc-raw-tr>
          <sc-for list="{{heads}}" as="hd" hint-placeholder-count="10">
            <sc-raw-th><button type="button" sc-camel-on-click="{{hd.pick}}" style="all: unset; cursor: pointer; display: inline-flex; gap: 4px;">{{hd.label}} <span aria-hidden="true">{{hd.arrow}}</span></button></sc-raw-th>
          </sc-for>
        </sc-raw-tr></sc-raw-thead>
        <sc-raw-tbody>
          <sc-for list="{{rows}}" as="t" hint-placeholder-count="10">
            <sc-raw-tr>
              <sc-raw-td><a href="{{L.TicketDetail}}" class="kz-tcard-id">{{t.id}}</a></sc-raw-td>
              <sc-raw-td><div class="kz-nowrap" style="font-weight: 600;">{{t.branch}}</div><div class="kz-tcard-meta">{{t.region}}</div></sc-raw-td>
              <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{t.ptone}}">{{t.priority}}</x-import></sc-raw-td>
              <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{t.stone}}">{{t.status}}</x-import></sc-raw-td>
              <sc-raw-td><x-import component-from-global-scope="KzNet.IspBadge" isp="{{t.isp}}" case-ref="{{t.caseRef}}"></x-import></sc-raw-td>
              <sc-raw-td class="kz-mono kz-nowrap">{{t.failure}}</sc-raw-td>
              <sc-raw-td class="kz-tcard-meta kz-nowrap">{{t.trigger}}</sc-raw-td>
              <sc-raw-td class="kz-num kz-nowrap">{{t.opened}}</sc-raw-td>
              <sc-raw-td class="kz-num kz-nowrap">{{t.mttr}}</sc-raw-td>
              <sc-raw-td><span class="{{t.aiCls}}">{{t.ai}}</span></sc-raw-td>
            </sc-raw-tr>
          </sc-for>
        </sc-raw-tbody>
      </sc-raw-table>
    </div>
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 16px; border-top: 1px solid var(--border); flex-wrap: wrap; font-size: 13px;">
      <span class="kz-muted">Showing 1–10 of 1,284</span>
      <div style="display: flex; gap: 4px;">
        <button type="button" class="kz-btn kz-btn-secondary kz-btn-sm" disabled="">Previous</button>
        <button type="button" class="kz-btn kz-btn-primary kz-btn-sm">1</button>
        <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">2</button>
        <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">3</button>
        <span style="padding: 4px 6px;">…</span>
        <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">129</button>
        <button type="button" class="kz-btn kz-btn-secondary kz-btn-sm">Next</button>
      </div>
    </div>
  </section>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1000}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { sort: 'opened', dir: -1 }; }
  renderVals() {
    var self = this, s = this.state;
    var P = { CRITICAL: 'critical', HIGH: 'warning', MEDIUM: 'brand', LOW: 'neutral' };
    var S = { 'Escalated to ISP': 'brand', 'With ISP': 'brand', 'Needs Human Review': 'critical', 'Resolved': 'good', 'Closed': 'good', 'Awaiting Regional IT': 'neutral', 'Diagnosing': 'info', 'Internal LAN Issue': 'warning', 'Verifying': 'info' };
    var R = [
      ['NET-1058', '2009-Kafr Nasar', 'Giza', 'CRITICAL', 'Escalated to ISP', 'NOOR', '244010', 'FULL_OUTAGE', 'DIRECT_EMAIL', '21 Oct 09:12', '—', true],
      ['NET-1057', '1173-Ghmrawy', 'Cairo', 'HIGH', 'With ISP', 'ORANGE', '1-1312322942540', 'LOCAL_LOOP_DOWN_ON_4G', 'DIRECT_EMAIL', '21 Oct 07:48', '—', true],
      ['NET-1055', '1254-El Mansheya', 'Behera', 'HIGH', 'Escalated to ISP', 'WE', '', 'FULL_OUTAGE', 'REPLICATION_DASHBOARD', '21 Oct 09:40', '—', true],
      ['NET-1054', '1450-Soliman Metwaly', 'Assyut', 'MEDIUM', 'Awaiting Regional IT', 'NOOR', '', '—', 'REPLICATION_DASHBOARD', '21 Oct 09:02', '—', true],
      ['NET-1052', '1312-Damanhour 3', 'Behera', 'HIGH', 'Diagnosing', 'NOOR', '', '—', 'DIRECT_EMAIL', '21 Oct 10:55', '—', true],
      ['NET-1051', '1201-Hadayek El Ahram', 'Giza', 'LOW', 'Internal LAN Issue', 'NOOR', '', 'INTERNAL_LAN_SWITCH', 'DIRECT_EMAIL', '21 Oct 08:31', '—', true],
      ['NET-1049', '1005-Tosson', 'Behera', 'CRITICAL', 'Needs Human Review', 'WE', '8400809', 'FULL_OUTAGE', 'DIRECT_EMAIL', '20 Oct 16:20', '—', false],
      ['NET-1047', '1366-Nasr City 7', 'Cairo', 'MEDIUM', 'Verifying', 'NOOR', '243881', 'FULL_OUTAGE', 'DIRECT_EMAIL', '20 Oct 22:05', '—', true],
      ['NET-1044', '1099-Kafr El Dawar', 'Behera', 'LOW', 'Closed', 'NOOR', '', 'CABLE_UNPLUGGED', 'DIRECT_EMAIL', '21 Oct 07:40', '0.6h', true],
      ['NET-1040', '1222-Bab El Louq', 'Cairo', 'MEDIUM', 'Resolved', 'ORANGE', '1-1312320077311', 'LOCAL_LOOP_DOWN_ON_4G', 'DIRECT_EMAIL', '20 Oct 18:15', '12.8h', true]
    ].map(function (r) { return { id: r[0], branch: r[1], region: r[2], priority: r[3], ptone: P[r[3]], status: r[4], stone: S[r[4]], isp: r[5], caseRef: r[6] || undefined, failure: r[7], trigger: r[8], opened: r[9], mttr: r[10], ai: r[11] ? 'AI active' : 'AI paused', aiCls: r[11] ? 'kz-ai' : 'kz-ai kz-ai-paused' }; });
    var key = s.sort;
    var rank = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
    R.sort(function (a, b) {
      var x = key === 'priority' ? rank[a.priority] : a[key], y = key === 'priority' ? rank[b.priority] : b[key];
      return (x > y ? 1 : x < y ? -1 : 0) * s.dir;
    });
    var cols = [['id', 'Ticket'], ['branch', 'Branch'], ['priority', 'Priority'], ['status', 'Status'], ['isp', 'ISP · Case #'], ['failure', 'Failure type'], ['trigger', 'Trigger'], ['opened', 'Opened'], ['mttr', 'MTTR'], ['ai', 'AI']];
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      heads: cols.map(function (c) { return { label: c[1], arrow: c[0] === key ? (s.dir > 0 ? '↑' : '↓') : '', pick: function () { self.setState({ sort: c[0], dir: c[0] === key ? -s.dir : 1 }); } }; }),
      rows: R
    };
  }
}
</script>
```

## 5 · Ticket 360° Detail (`/tickets/:id`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Tickets List" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1300px;">
  <nav aria-label="Breadcrumb" style="font-size: 13px; display: flex; gap: 6px; color: var(--ink-muted);"><a href="{{L.TicketsList}}">Tickets</a><span>/</span><span>NET-1057</span></nav>

  <div class="kz-page-hd" style="align-items: flex-start;">
    <div>
      <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 4px;">
        <span class="kz-tcard-id" style="font-size: 14px;">NET-1057</span>
        <x-import component-from-global-scope="KzNet.Badge" tone="warning">HIGH</x-import>
        <x-import component-from-global-scope="KzNet.Badge" tone="brand">With ISP · 4–6h loop</x-import>
        <x-import component-from-global-scope="KzNet.Badge" tone="outline">DIRECT_EMAIL</x-import>
      </div>
      <h1>1173-Ghmrawy · Local loop down, running on 4G</h1>
      <p>Opened 21 Oct 07:48 by CITSupport@kazyon.com · ORANGE case 1-1312322942540</p>
    </div>
  </div>

  <div class="kz-card" style="padding: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
    <label class="kz-chip">Status<sc-raw-select style="border: 0; font: 600 12px var(--font-sans); background: transparent; color: var(--ink);"><option>ESCALATED_TO_ISP</option><option>AWAITING_BRANCH_CONTACT</option><option>VERIFYING</option><option>NEEDS_HUMAN_REVIEW</option><option>RESOLVED</option></sc-raw-select></label>
    <label class="kz-chip">Priority<sc-raw-select style="border: 0; font: 600 12px var(--font-sans); background: transparent; color: var(--ink);"><option>HIGH</option><option>CRITICAL</option><option>MEDIUM</option><option>LOW</option></sc-raw-select></label>
    <button type="button" class="{{aiBtn}}" sc-camel-on-click="{{toggleAi}}" aria-pressed="{{aiPaused}}">{{aiLabel}}</button>
    <span style="flex: 1;"></span>
    <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{rerun}}">▶ Re-run diagnostics now</button>
    <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{chase}}">Force ISP follow-up</button>
    <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{contactRit}}">Contact Regional IT</button>
    <button type="button" class="kz-btn kz-btn-danger" sc-camel-on-click="{{openEsc}}">Escalate to engineer</button>
  </div>

  <sc-if value="{{toast}}" hint-placeholder-val="{{false}}">
    <div role="status" style="padding: 10px 14px; border-radius: 10px; background: var(--info-bg); color: var(--info); font-size: 13px; font-weight: 600;">{{toast}}</div>
  </sc-if>

  <sc-if value="{{esc}}" hint-placeholder-val="{{false}}">
    <div class="kz-modal-scrim">
      <div role="dialog" aria-modal="true" aria-label="Escalate to engineer" class="kz-card" style="width: 100%; max-width: 520px; box-shadow: var(--shadow-raised);">
        <div class="kz-card-hd"><div><h2>Escalate NET-1057 to a human engineer</h2><p>Sets NEEDS_HUMAN_REVIEW, pauses AI and emails the full incident report.</p></div></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 14px;">
          <label class="kz-field">Send report to<sc-raw-select><option>noc-oncall@kazyon.com</option><option>ITInfrastructure@kazyon.com</option></sc-raw-select></label>
          <label class="kz-field">Reason<sc-raw-select><option>OTHER</option><option>QUOTA_CONSUMED</option><option>INTERNAL_BOX_CABLE</option><option>MSAN_MIGRATION</option><option>MAX_RETRIES</option></sc-raw-select></label>
          <label class="kz-field">Note to engineer<textarea rows="3">ORANGE not responding after 2 chasers; branch manager escalating.</textarea></label>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{closeEsc}}">Cancel</button>
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{confirmEsc}}">Escalate &amp; email report</button>
        </div>
      </div>
    </div>
  </sc-if>

  <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">
    <aside style="flex: 1 1 300px; max-width: 360px; display: flex; flex-direction: column; gap: 16px;">
      <section class="kz-card">
        <div class="kz-card-hd"><h2>SLA</h2></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 10px;">
          <x-import component-from-global-scope="KzNet.SlaTimer" label="Follow-up" minutes-left="{{52}}" total-minutes="{{300}}"></x-import>
          <div class="kz-tcard-meta">Welcome mail received 08:21 (33 min after escalation) · 2 chasers sent · next chaser 12:16</div>
        </div>
      </section>
      <section class="kz-card">
        <div class="kz-card-hd"><h2>Branch</h2></div>
        <dl class="kz-card-bd" style="margin: 0; display: grid; grid-template-columns: 120px 1fr; gap: 8px 12px; font-size: 13px;">
          <dt class="kz-muted">SAP code</dt><dd style="margin: 0;" class="kz-mono">1173</dd>
          <dt class="kz-muted">Store</dt><dd style="margin: 0; font-weight: 600;">1173-Ghmrawy</dd>
          <dt class="kz-muted">IP 1 (router)</dt><dd style="margin: 0;" class="kz-mono">10.11.73.1</dd>
          <dt class="kz-muted">IP 2 (switch)</dt><dd style="margin: 0;" class="kz-mono">10.11.73.2</dd>
          <dt class="kz-muted">Region</dt><dd style="margin: 0;">Cairo</dd>
          <dt class="kz-muted">Regional IT</dt><dd style="margin: 0;"><a href="#">CITSupport@kazyon.com</a></dd>
        </dl>
      </section>
      <section class="kz-card">
        <div class="kz-card-hd"><h2>ISP</h2><x-import component-from-global-scope="KzNet.IspBadge" isp="ORANGE"></x-import></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
          <div style="display: grid; grid-template-columns: 120px 1fr; gap: 8px 12px;">
            <span class="kz-muted">Support</span><span>ccc-eg@orange.com</span>
            <span class="kz-muted">L.L ID</span><span class="kz-mono">QUO1-10316406</span>
            <span class="kz-muted">3G ID</span><span class="kz-mono">QUO1-10316407</span>
            <span class="kz-muted">4G hub IP</span><span class="kz-mono">10.247.8.1</span>
          </div>
          <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">ISP ticket ref #<input value="1-1312322942540" class="kz-mono" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px;"></label>
          <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Site contact phone<input value="010 2345 8817" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        </div>
      </section>
    </aside>

    <section class="kz-card" style="flex: 999 1 560px; min-width: 0;">
      <div role="tablist" aria-label="Ticket sections" style="display: flex; gap: 4px; padding: 8px 8px 0; border-bottom: 1px solid var(--border); overflow-x: auto;">
        <sc-for list="{{tabs}}" as="tb" hint-placeholder-count="4">
          <button type="button" role="tab" aria-selected="{{tb.on}}" sc-camel-on-click="{{tb.pick}}" style="{{tb.style}}">{{tb.label}}</button>
        </sc-for>
      </div>

      <sc-if value="{{isTimeline}}" hint-placeholder-val="{{true}}">
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 0;">
          <sc-for list="{{events}}" as="e" hint-placeholder-count="8">
            <div style="display: grid; grid-template-columns: 64px 20px 1fr; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border);">
              <span class="kz-num kz-muted" style="font-size: 12px; padding-top: 2px;">{{e.time}}</span>
              <span style="{{e.dot}}"></span>
              <div><div style="font-size: 13px; font-weight: 600;">{{e.title}}</div><div class="kz-tcard-meta">{{e.actor}} · {{e.detail}}</div></div>
            </div>
          </sc-for>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; margin-top: 16px;">Add internal note<textarea rows="3" placeholder="Visible to engineers only" style="padding: 10px 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); resize: vertical;"></textarea></label>
          <div style="display: flex; justify-content: flex-end; margin-top: 8px;"><x-import component-from-global-scope="KzNet.Button" variant="primary" size="sm">Add note</x-import></div>
        </div>
      </sc-if>

      <sc-if value="{{isTests}}" hint-placeholder-val="{{false}}">
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 16px;">
          <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <div role="img" aria-label="Router photo placeholder" style="flex: 1 1 280px; height: 220px; border-radius: 12px; background: var(--surface-200); border: 1.5px dashed var(--border-strong); display: flex; align-items: center; justify-content: center; color: var(--ink-muted); font-size: 13px; font-weight: 600;">[ROUTER PHOTO — router_1173.jpg]</div>
            <div style="flex: 1 1 260px; display: flex; flex-direction: column; gap: 10px;">
              <h3 style="margin: 0; font-size: 15px;">Gemma 4 vision verdict</h3>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                <x-import component-from-global-scope="KzNet.Badge" tone="good">Cables plugged</x-import>
                <x-import component-from-global-scope="KzNet.Badge" tone="good">Power LED on</x-import>
                <x-import component-from-global-scope="KzNet.Badge" tone="warning">WAN LED off</x-import>
              </div>
              <p style="margin: 0; font-size: 13px; line-height: 20px;">WAN and LAN cables are seated, power is on. The WAN indicator is dark, consistent with a local-loop fault. Confidence 0.91.</p>
              <div><x-import component-from-global-scope="KzNet.Button" variant="secondary" size="sm">Override verdict</x-import></div>
            </div>
          </div>
          <h3 style="margin: 0; font-size: 15px;">Diagnostic runs</h3>
          <sc-for list="{{runs}}" as="r" hint-placeholder-count="2">
            <details class="kz-card" style="padding: 12px 14px;" open="{{r.open}}">
              <summary style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; cursor: pointer; font-size: 13px;">
                <b>{{r.label}}</b><span class="kz-muted">{{r.when}} · {{r.ms}}</span>
                <sc-for list="{{r.checks}}" as="c" hint-placeholder-count="3"><x-import component-from-global-scope="KzNet.StatusPill" label="{{c.label}}" state="{{c.state}}"></x-import></sc-for>
                <x-import component-from-global-scope="KzNet.Badge" tone="{{r.tone}}">{{r.result}}</x-import>
              </summary>
              <pre class="kz-mono" style="margin: 12px 0 0; padding: 12px; background: var(--term-bg); color: var(--term-ink); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; white-space: pre; line-height: 18px;">{{r.log}}</pre>
            </details>
          </sc-for>
        </div>
      </sc-if>

      <sc-if value="{{isMail}}" hint-placeholder-val="{{false}}">
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 12px;">
          <sc-for list="{{mails}}" as="m" hint-placeholder-count="3">
            <article style="{{m.style}}">
              <div style="display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 12px;"><b>{{m.from}}</b><span class="kz-muted">{{m.when}} · {{m.dir}}</span></div>
              <div style="font-size: 13px; font-weight: 600; margin-top: 4px;">{{m.subject}}</div>
              <p style="margin: 6px 0 0; font-size: 13px; line-height: 20px; white-space: pre-line;">{{m.body}}</p>
            </article>
          </sc-for>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">{{replyLabel}}<textarea rows="3" style="padding: 10px 12px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); resize: vertical;"></textarea></label>
          <div style="display: flex; justify-content: flex-end; gap: 8px;"><x-import component-from-global-scope="KzNet.Button" variant="secondary" size="sm">Save draft</x-import><x-import component-from-global-scope="KzNet.Button" variant="primary" size="sm" icon="mail">Send</x-import></div>
        </div>
      </sc-if>
    </section>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1300}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { tab: 'timeline', ai: true }; }
  renderVals() {
    var self = this, tab = this.state.tab;
    var dot = function (c) { return 'width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; background: var(--' + c + '); box-shadow: 0 0 0 3px var(--' + c + '-bg, var(--surface-200));'; };
    var T = [['timeline', 'Updates timeline'], ['tests', 'Test results & vision'], ['branch', 'Branch emails · 4'], ['isp', 'ISP emails · 6']];
    var branchMails = [
      { from: 'CITSupport@kazyon.com', when: '07:46', dir: 'Inbound', subject: '1173 Ghmrawy no connection', body: 'Store 1173 not syncing since 07:15. Router checked, photo attached.\nSite contact: 010 2345 8817', out: false },
      { from: 'NetOps Agent', when: '07:52', dir: 'Outbound', subject: 'RE: 1173 Ghmrawy no connection', body: 'Thanks. Cables look fine. The store is running on 4G backup; we have escalated the local loop to ORANGE and will update you.', out: true },
      { from: 'CITSupport@kazyon.com', when: '10:40', dir: 'Inbound', subject: 'RE: 1173 Ghmrawy no connection', body: 'Any update from Orange? Branch manager asking.', out: false }
    ];
    var ispMails = [
      { from: 'NetOps Agent → ccc-eg@orange.com', when: '07:48', dir: 'Outbound', subject: 'store 1173 # QUO1-10316406', body: 'Dear NOC\nkindly check L.L and 4G connection store 1173\n1173\nQUO1-10316406\nQUO1-10316407\nsite contact : 010 2345 8817', out: true },
      { from: 'ccc-eg@orange.com', when: '08:21', dir: 'Inbound · Welcome', subject: 'ticket number (1-1312322942540 For QID QUO1-10316406 # 1173)', body: 'Dear Customer, your request has been registered and is being handled.', out: false },
      { from: 'NetOps Agent → ccc-eg@orange.com', when: '12:16', dir: 'Scheduled chaser', subject: 'RE: store 1173 # QUO1-10316406', body: 'Dear NOC, kindly share an update on ticket 1-1312322942540. Store still on 4G backup.', out: true }
    ];
    var mails = tab === 'isp' ? ispMails : branchMails;
    var extra = this.state.extra || [];
    var extraRuns = this.state.extraRuns || [];
    var now = function () { var d = new Date(); return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); };
    var addEvent = function (color, title, detail, toast, more) {
      self.setState(Object.assign({ extra: [[now(), color, title, 'ENGINEER', detail]].concat(self.state.extra || []), toast: toast }, more || {}));
    };
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      toast: this.state.toast || false,
      esc: !!this.state.esc,
      openEsc: function () { self.setState({ esc: true }); },
      closeEsc: function () { self.setState({ esc: false }); },
      confirmEsc: function () { addEvent('critical', 'Escalated to human engineer', 'Report emailed to noc-oncall@kazyon.com', 'Escalated. AI paused and report sent to noc-oncall@kazyon.com.', { esc: false, ai: false }); },
      rerun: function () {
        var run = { label: 'MANUAL', when: now(), ms: '6.0 s', open: true, result: 'DEGRADED', tone: 'warning', checks: [{ label: 'IP1', state: 'up' }, { label: 'IP2', state: 'down' }, { label: '4G', state: 'hub' }], log: '$ ping -c 4 10.11.73.1\n0% packet loss, avg 179 ms\n$ ping -c 4 10.11.73.2\n100% packet loss\n$ traceroute -n 10.11.73.1\n 2  10.247.8.1    40.6 ms   ← ORANGE 4G hub\nDIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G' };
        addEvent('info', 'Manual diagnostics run', 'Still on 4G backup', 'Diagnostics finished: still LOCAL_LOOP_DOWN_ON_4G.', { extraRuns: [run].concat(self.state.extraRuns || []), tab: 'tests' });
      },
      chase: function () { addEvent('brand-600', 'Follow-up chaser sent to ORANGE', 'Manual, outside the 4–6h loop', 'Chaser sent to ccc-eg@orange.com.'); },
      contactRit: function () { self.setState({ tab: 'branch', toast: 'Write to CITSupport@kazyon.com below.' }); },
      nav: this.navMap(),
      aiPaused: !this.state.ai,
      aiLabel: this.state.ai ? 'Pause AI' : 'Resume AI',
      aiBtn: this.state.ai ? 'kz-btn kz-btn-secondary' : 'kz-btn kz-btn-primary',
      toggleAi: function () { self.setState({ ai: !self.state.ai }); },
      tabs: T.map(function (t) { var on = t[0] === tab; return { label: t[1], on: on, pick: function () { self.setState({ tab: t[0] }); }, style: 'all: unset; cursor: pointer; padding: 10px 14px; font: 600 13px var(--font-sans); white-space: nowrap; border-bottom: 2px solid ' + (on ? 'var(--brand-600)' : 'transparent') + '; color: ' + (on ? 'var(--brand-text)' : 'var(--ink-muted)') + ';' }; }),
      isTimeline: tab === 'timeline', isTests: tab === 'tests', isMail: tab === 'branch' || tab === 'isp',
      replyLabel: tab === 'isp' ? 'Reply to ORANGE (ISP thread)' : 'Reply to Regional IT (branch thread)',
      mails: mails.map(function (m) { return Object.assign({}, m, { style: 'padding: 12px 14px; border-radius: 12px; border: 1px solid var(--border); background: ' + (m.out ? 'var(--brand-50)' : 'var(--surface-000)') + ';' }); }),
      events: extra.concat([
        ['12:16', 'info', 'Follow-up chaser scheduled', 'SYSTEM', '4–6h loop, chaser #2'],
        ['10:41', 'ink-muted', 'Branch asked for update', 'AI_AGENT', 'Replied with ISP status'],
        ['08:21', 'good', 'ISP Welcome mail received', 'AI_AGENT', 'Saved case 1-1312322942540'],
        ['07:48', 'brand-600', 'Escalated to ORANGE', 'AI_AGENT', 'Template: store 1173 # QUO1-10316406'],
        ['07:48', 'info', 'Traceroute hit 4G hub 10.247.8.1', 'AI_AGENT', 'LOCAL_LOOP_DOWN_ON_4G'],
        ['07:47', 'critical', 'Dual-ping: IP1 UP, IP2 DOWN', 'AI_AGENT', 'ORANGE branch → traceroute'],
        ['07:47', 'good', 'Vision check passed', 'AI_AGENT', 'Cables plugged, power on'],
        ['07:46', 'ink-muted', 'Ticket created from email', 'SYSTEM', 'From CITSupport@kazyon.com']
      ]).map(function (e) { return { time: e[0], dot: dot(e[1]), title: e[2], actor: e[3], detail: e[4] }; }),
      runs: extraRuns.concat([
        { label: 'INITIAL', when: '07:47', ms: '6.2 s', open: true, result: 'DEGRADED', tone: 'warning', checks: [{ label: 'IP1', state: 'up' }, { label: 'IP2', state: 'down' }, { label: '4G', state: 'hub' }],
          log: '$ ping -c 4 10.11.73.1\n4 packets transmitted, 4 received, 0% packet loss, avg 182 ms\n$ ping -c 4 10.11.73.2\n4 packets transmitted, 0 received, 100% packet loss\n$ traceroute -n 10.11.73.1\n 1  10.100.109.1   0.6 ms\n 2  10.247.8.1    41.2 ms   ← ORANGE 4G hub\n 3  10.11.73.1   180.9 ms\nDIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G' },
        { label: 'MANUAL', when: '10:02', ms: '5.9 s', open: false, result: 'DEGRADED', tone: 'warning', checks: [{ label: 'IP1', state: 'up' }, { label: 'IP2', state: 'down' }, { label: '4G', state: 'hub' }],
          log: '$ ping -c 4 10.11.73.1\n0% packet loss, avg 176 ms\n$ ping -c 4 10.11.73.2\n100% packet loss\n$ traceroute -n 10.11.73.1\n 2  10.247.8.1    39.8 ms   ← ORANGE 4G hub\nDIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G' }
      ])
    };
  }
}
</script>
```

## 6 · Replication Dashboard Monitor (`/replication`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Replication Monitor" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1060px;">
  <div class="kz-page-hd">
    <div>
      <h1>Replication Dashboard Monitor</h1>
      <p>Every “Replication Dashboard - &lt;Date&gt;” email the agent ingested. Not Updated stores get a ticket and a Regional IT email.</p>
    </div>
    <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{openUp}}">+ Upload / paste report</button>
  </div>

  <sc-if value="{{up}}" hint-placeholder-val="{{false}}">
    <div class="kz-modal-scrim">
      <div role="dialog" aria-modal="true" aria-label="Upload replication report" class="kz-card" style="width: 100%; max-width: 640px; box-shadow: var(--shadow-raised);">
        <div class="kz-card-hd"><div><h2>Upload or paste a Replication Dashboard</h2><p>For testing. Parsed exactly like the 09:00 email.</p></div>
          <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" aria-label="Close" sc-camel-on-click="{{closeUp}}">✕</button></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 14px;">
          <label class="kz-field">Report email (.eml or .html)<input type="file" accept=".eml,.html,.htm" style="padding-top: 8px;"></label>
          <label class="kz-field">…or paste the HTML table<textarea rows="5" class="kz-mono">&lt;tr&gt;&lt;td&gt;1450&lt;/td&gt;&lt;td&gt;Soliman Metwaly&lt;/td&gt;&lt;td&gt;Assyut&lt;/td&gt;&lt;td&gt;20/10 21:14&lt;/td&gt;&lt;td&gt;20/10/2026&lt;/td&gt;&lt;td&gt;Not Updated&lt;/td&gt;&lt;/tr&gt;</textarea></label>
          <sc-if value="{{parsed}}" hint-placeholder-val="{{false}}">
            <div style="padding: 12px; border-radius: 10px; background: var(--info-bg); color: var(--info); font-size: 13px;"><b>Dry run:</b> 1 row parsed · 1 Not Updated · ticket would be created and assiutregion@kazyon.com emailed.</div>
          </sc-if>
          <label style="display: flex; gap: 8px; align-items: center; font-size: 13px; font-weight: 600;"><input type="checkbox" checked="" style="accent-color: var(--brand-600); width: 16px; height: 16px;"> Dry run only (no tickets, no emails)</label>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{closeUp}}">Cancel</button>
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{parse}}">Parse report</button>
        </div>
      </div>
    </div>
  </sc-if>

  <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">
    <section class="kz-card" style="flex: 1 1 280px; max-width: 340px; overflow: hidden;">
      <div class="kz-card-hd" style="padding-bottom: 12px;"><h2>Reports</h2><span class="kz-tcard-meta">Last 7 days</span></div>
      <sc-for list="{{reports}}" as="r" hint-placeholder-count="6">
        <button type="button" sc-camel-on-click="{{r.pick}}" style="{{r.style}}">
          <span style="display: flex; flex-direction: column; gap: 2px; text-align: left;"><b style="font-size: 13px;">{{r.subject}}</b><span class="kz-tcard-meta">Received {{r.received}} · {{r.total}} stores</span></span>
          <x-import component-from-global-scope="KzNet.Badge" tone="{{r.tone}}">{{r.nu}} not updated</x-import>
        </button>
      </sc-for>
    </section>

    <section class="kz-card" style="flex: 999 1 560px; min-width: 0; overflow: hidden;">
      <div class="kz-card-hd" style="padding-bottom: 12px; flex-wrap: wrap;">
        <div><h2>{{sel.subject}}</h2><p>{{sel.total}} stores parsed · {{sel.nu}} Not Updated · {{sel.notified}} Regional IT emails sent · 0 duplicates skipped</p></div>
        <label style="display: flex; gap: 8px; align-items: center; font-size: 13px; font-weight: 600;"><input type="checkbox" checked="{{onlyNu}}" sc-camel-on-change="{{toggleNu}}" style="accent-color: var(--brand-600); width: 16px; height: 16px;"> Not Updated only</label>
      </div>
      <div class="kz-scroll-x">
        <sc-raw-table class="kz-table">
          <sc-raw-thead><sc-raw-tr><sc-raw-th>ID</sc-raw-th><sc-raw-th>Store name</sc-raw-th><sc-raw-th>Region</sc-raw-th><sc-raw-th>Last trans.</sc-raw-th><sc-raw-th>Buss. date</sc-raw-th><sc-raw-th>Status</sc-raw-th><sc-raw-th>Regional IT</sc-raw-th><sc-raw-th>Ticket</sc-raw-th></sc-raw-tr></sc-raw-thead>
          <sc-raw-tbody>
            <sc-for list="{{rows}}" as="w" hint-placeholder-count="10">
              <sc-raw-tr>
                <sc-raw-td class="kz-mono">{{w.id}}</sc-raw-td>
                <sc-raw-td style="font-weight: 600;" class="kz-nowrap">{{w.name}}</sc-raw-td>
                <sc-raw-td>{{w.region}}</sc-raw-td>
                <sc-raw-td class="kz-num kz-nowrap">{{w.last}}</sc-raw-td>
                <sc-raw-td class="kz-num kz-nowrap">{{w.biz}}</sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{w.tone}}">{{w.status}}</x-import></sc-raw-td>
                <sc-raw-td class="kz-tcard-meta kz-nowrap">{{w.mail}}</sc-raw-td>
                <sc-raw-td><sc-if value="{{w.ticket}}" hint-placeholder-val="{{true}}"><a href="{{L.Board}}" class="kz-tcard-id">{{w.ticket}}</a></sc-if></sc-raw-td>
              </sc-raw-tr>
            </sc-for>
          </sc-raw-tbody>
        </sc-raw-table>
      </div>
    </section>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1060}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { sel: 0, onlyNu: false }; }
  renderVals() {
    var self = this, st = this.state;
    var R = [
      ['Replication Dashboard - 21/10/2026', '21 Oct 09:00', 1150, 12, 12],
      ['Replication Dashboard - 20/10/2026', '20 Oct 09:01', 1150, 15, 15],
      ['Replication Dashboard - 19/10/2026', '19 Oct 09:00', 1149, 9, 9],
      ['Replication Dashboard - 18/10/2026', '18 Oct 09:02', 1149, 21, 18],
      ['Replication Dashboard - 17/10/2026', '17 Oct 09:00', 1148, 7, 7],
      ['Replication Dashboard - 16/10/2026', '16 Oct 09:00', 1148, 11, 11]
    ];
    var reports = R.map(function (r, i) {
      var on = i === st.sel;
      return { subject: r[0], received: r[1], total: r[2].toLocaleString('en-US'), nu: r[3], notified: r[4], tone: r[3] > 14 ? 'critical' : 'warning',
        pick: function () { self.setState({ sel: i }); },
        style: 'all: unset; box-sizing: border-box; cursor: pointer; width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 12px 16px; border-top: 1px solid var(--border); background: ' + (on ? 'var(--brand-100)' : 'transparent') + ';' };
    });
    var W = [
      ['1450', 'Soliman Metwaly', 'Assyut', '20/10 21:14', '20/10/2026', 'Not Updated', 'assiutregion@kazyon.com', 'NET-1054'],
      ['1088', 'Gamal Salem', 'New October', '20/10 22:40', '20/10/2026', 'Not Updated', 'newoctregion@kazyon.com', 'NET-1053'],
      ['1005', 'Tosson', 'Behera', '20/10 16:02', '20/10/2026', 'Not Updated', 'Open ticket exists', 'NET-1049'],
      ['1254', 'El Mansheya', 'Behera', '21/10 06:55', '21/10/2026', 'Not Updated', 'BITSupport@kazyon.com', 'NET-1055'],
      ['2009', 'Kafr Nasar', 'Giza', '21/10 07:58', '21/10/2026', 'Not Updated', 'GITSupport@kazyon.com', 'NET-1058'],
      ['1173', 'Ghmrawy', 'Cairo', '21/10 08:50', '21/10/2026', 'Updated', '—', ''],
      ['1201', 'Hadayek El Ahram', 'Giza', '21/10 08:52', '21/10/2026', 'Updated', '—', ''],
      ['1312', 'Damanhour 3', 'Behera', '21/10 08:47', '21/10/2026', 'Updated', '—', ''],
      ['1366', 'Nasr City 7', 'Cairo', '21/10 08:58', '21/10/2026', 'Updated', '—', ''],
      ['1420', 'Sheikh Zayed 2', 'New October', '21/10 08:41', '21/10/2026', 'Updated', '—', '']
    ].map(function (w) { return { id: w[0], name: w[0] + ' - ' + w[1], region: w[2], last: w[3], biz: w[4], status: w[5], tone: w[5] === 'Updated' ? 'good' : 'critical', mail: w[6], ticket: w[7] }; });
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      up: !!st.up, parsed: !!st.parsed,
      openUp: function () { self.setState({ up: true, parsed: false }); },
      closeUp: function () { self.setState({ up: false }); },
      parse: function () { self.setState({ parsed: true }); },
      reports: reports, sel: reports[st.sel], onlyNu: st.onlyNu,
      toggleNu: function () { self.setState({ onlyNu: !self.state.onlyNu }); },
      rows: st.onlyNu ? W.filter(function (w) { return w.status !== 'Updated'; }) : W
    };
  }
}
</script>
```

## 7 · Human Review Queue (`/escalations`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Human Review" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 980px;">
  <div class="kz-page-hd">
    <div>
      <h1>Human Review &amp; Escalations</h1>
      <p>Items the agent could not handle alone. Each one was emailed to the on-duty engineer with the full incident report.</p>
    </div>
    <span class="kz-tcard-meta">On duty: <b style="color: var(--ink);">noc-oncall@kazyon.com</b></span>
  </div>

  <div class="kz-filters">
    <sc-for list="{{chips}}" as="c" hint-placeholder-count="6">
      <button type="button" class="{{c.cls}}" sc-camel-on-click="{{c.pick}}">{{c.label}} · {{c.n}}</button>
    </sc-for>
  </div>

  <div style="display: flex; flex-direction: column; gap: 12px;">
    <sc-for list="{{items}}" as="it" hint-placeholder-count="4">
      <article class="kz-card" style="padding: 16px; display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">
        <div style="flex: 999 1 520px; min-width: 0; display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <x-import component-from-global-scope="KzNet.Badge" tone="critical">{{it.reason}}</x-import>
            <sc-if value="{{it.ticket}}" hint-placeholder-val="{{true}}"><a href="{{L.TicketDetail}}" class="kz-tcard-id">{{it.ticket}}</a></sc-if>
            <sc-if value="{{it.isp}}" hint-placeholder-val="{{true}}"><x-import component-from-global-scope="KzNet.IspBadge" isp="{{it.isp}}" case-ref="{{it.caseRef}}"></x-import></sc-if>
            <span class="kz-tcard-meta">{{it.when}}</span>
          </div>
          <h3 style="margin: 0; font-size: 16px; line-height: 22px;">{{it.title}}</h3>
          <blockquote style="margin: 0; padding: 10px 12px; background: var(--surface-100); border-radius: 10px; font-size: 13px; line-height: 20px; color: var(--ink);">“{{it.quote}}”<div class="kz-tcard-meta" style="margin-top: 4px;">— {{it.from}}</div></blockquote>
          <p style="margin: 0; font-size: 13px; line-height: 20px;"><b>Agent summary:</b> {{it.summary}}</p>
          <div class="kz-tcard-meta">Report emailed to {{it.engineer}} · AI automation paused on this item</div>
        </div>
        <div style="flex: 1 1 200px; display: flex; flex-direction: column; gap: 8px;">
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{it.done}}">{{it.primary}}</button>
          <a href="{{L.TicketDetail}}" class="kz-btn kz-btn-secondary" style="text-decoration: none;">Reply manually</a>
          <button type="button" class="kz-btn kz-btn-ghost" sc-camel-on-click="{{it.done}}">Resume AI automation</button>
        </div>
      </article>
    </sc-for>
    <sc-if value="{{empty}}" hint-placeholder-val="{{false}}">
      <div class="kz-card" style="padding: 40px; text-align: center;"><h2 style="margin: 0 0 4px; font-size: 18px;">Queue clear</h2><p class="kz-muted" style="margin: 0; font-size: 13px;">Nothing needs a person right now.</p></div>
    </sc-if>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:980}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { reason: 'ALL', done: {} }; }
  renderVals() {
    var self = this, st = this.state;
    var A = [
      { k: 'q1', reason: 'QUOTA_CONSUMED', ticket: 'NET-1049', isp: 'WE', caseRef: '8400809', when: '20 Oct 16:44', title: '1005-Tosson · WE says the 4G quota is consumed', quote: 'Quota is Consumed — kindly refer to your Account Manager.', from: 'psupport@te.eg', summary: 'IP1 down since 16:20, backup SIM out of data. Needs the WE account manager to top up the quota; no technical step the agent can take.', primary: 'Mark handled' },
      { k: 'q2', reason: 'MSAN_MIGRATION', ticket: 'NET-1041', isp: 'WE', caseRef: '8407102', when: '20 Oct 11:05', title: '1510-Abnoub · line affected by WE MSAN migration', quote: 'The site is included in the MSAN migration process, expected 48 hours.', from: 'psupport@te.eg', summary: 'Planned ISP work, not a fault. Decide whether to accept the window or request priority migration.', primary: 'Mark handled' },
      { k: 'q3', reason: 'INTERNAL_BOX_CABLE', ticket: 'NET-1036', isp: 'NOOR', caseRef: '243790', when: '19 Oct 15:30', title: '1277-Itay El Baroud · new internal cable needed', quote: 'Kindly extend a new internal cable between the box and the router.', from: 'noc@noor.net', summary: 'Requires on-site cabling by Kazyon facilities. Regional IT (BITSupport) has not been asked yet.', primary: 'Mark handled' },
      { k: 'q4', reason: 'UNRECOGNIZED_EMAIL', ticket: '', isp: '', caseRef: '', when: '21 Oct 10:12', title: 'Unmatched email: “Invoice dispute – October circuits”', quote: 'Please find attached the October invoice for 181 circuits …', from: 'billing@orange.com', summary: 'Not an incident and no branch code found (confidence 0.22). Likely belongs to procurement.', primary: 'Convert to ticket' },
      { k: 'q5', reason: 'MAX_RETRIES', ticket: 'NET-1031', isp: 'NOOR', caseRef: '', when: '19 Oct 09:40', title: '1399-Mallawi · no Welcome mail after 4 chasers', quote: 'No reply from noc@noor.net since escalation at 01:40.', from: 'NetOps Agent', summary: 'Two-hour welcome SLA missed four times. Call the NOOR NOC directly.', primary: 'Mark handled' }
    ];
    var open = A.filter(function (a) { return !st.done[a.k]; });
    var reasons = ['ALL', 'QUOTA_CONSUMED', 'MSAN_MIGRATION', 'INTERNAL_BOX_CABLE', 'UNRECOGNIZED_EMAIL', 'MAX_RETRIES'];
    var items = open.filter(function (a) { return st.reason === 'ALL' || a.reason === st.reason; }).map(function (a) {
      return Object.assign({}, a, { engineer: 'noc-oncall@kazyon.com', ticket: a.ticket || false, isp: a.isp || false, caseRef: a.caseRef || undefined,
        done: function () { var d = Object.assign({}, self.state.done); d[a.k] = true; self.setState({ done: d }); } });
    });
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      chips: reasons.map(function (r) { return { label: r === 'ALL' ? 'All' : r, n: r === 'ALL' ? open.length : open.filter(function (a) { return a.reason === r; }).length, cls: 'kz-chip' + (r === st.reason ? ' kz-chip-on' : ''), pick: function () { self.setState({ reason: r }); } }; }),
      items: items, empty: items.length === 0
    };
  }
}
</script>
```

## 8 · Mailbox & Email Triage (`/mailbox`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Mailbox &amp; Triage" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1040px;">
  <div class="kz-page-hd">
    <div>
      <h1>Mailbox &amp; Email Triage</h1>
      <p>Every email the service account received or sent today · 186 inbound · 142 outbound · last IMAP poll 14 s ago</p>
    </div>
  </div>

  <label style="display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; padding: 18px; border: 1.5px dashed var(--brand-500); border-radius: 14px; background: var(--brand-50); font-size: 13px; cursor: pointer;">
    <b>Simulate inbound email</b><span class="kz-muted">Drop an .eml file here, or</span><span class="kz-btn kz-btn-secondary kz-btn-sm">Choose file</span>
    <input type="file" accept=".eml" style="position: absolute; width: 1px; height: 1px; opacity: 0;">
  </label>

  <div class="kz-filters">
    <sc-for list="{{chips}}" as="c" hint-placeholder-count="5"><button type="button" class="{{c.cls}}" sc-camel-on-click="{{c.pick}}">{{c.label}} · {{c.n}}</button></sc-for>
  </div>

  <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">
    <section class="kz-card" style="flex: 999 1 560px; min-width: 0; overflow: hidden;">
      <div class="kz-scroll-x">
        <sc-raw-table class="kz-table">
          <sc-raw-thead><sc-raw-tr><sc-raw-th>Time</sc-raw-th><sc-raw-th>Dir.</sc-raw-th><sc-raw-th>From / To</sc-raw-th><sc-raw-th>Subject</sc-raw-th><sc-raw-th>Classified as</sc-raw-th><sc-raw-th>Ticket</sc-raw-th></sc-raw-tr></sc-raw-thead>
          <sc-raw-tbody>
            <sc-for list="{{mails}}" as="m" hint-placeholder-count="9">
              <sc-raw-tr style="{{m.style}}">
                <sc-raw-td class="kz-num kz-nowrap">{{m.time}}</sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{m.dtone}}">{{m.dir}}</x-import></sc-raw-td>
                <sc-raw-td class="kz-nowrap" style="font-weight: 600;">{{m.who}}</sc-raw-td>
                <sc-raw-td><button type="button" sc-camel-on-click="{{m.pick}}" style="all: unset; cursor: pointer; display: block; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{m.subject}}</button></sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{m.ctone}}">{{m.cls}}</x-import></sc-raw-td>
                <sc-raw-td><a href="{{L.TicketDetail}}" class="kz-tcard-id">{{m.ticket}}</a></sc-raw-td>
              </sc-raw-tr>
            </sc-for>
          </sc-raw-tbody>
        </sc-raw-table>
      </div>
    </section>

    <aside class="kz-card" style="flex: 1 1 340px; max-width: 460px; display: flex; flex-direction: column;" aria-label="Email details">
      <div class="kz-card-hd"><h2>Email details</h2><x-import component-from-global-scope="KzNet.Badge" tone="{{sel.ctone}}">{{sel.cls}}</x-import></div>
      <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 12px;">
        <dl style="margin: 0; display: grid; grid-template-columns: 90px 1fr; gap: 6px 10px; font-size: 12px;">
          <dt class="kz-muted">From</dt><dd style="margin: 0;">{{sel.from}}</dd>
          <dt class="kz-muted">To</dt><dd style="margin: 0;">{{sel.to}}</dd>
          <dt class="kz-muted">Subject</dt><dd style="margin: 0; font-weight: 600;">{{sel.subject}}</dd>
          <dt class="kz-muted">Message-ID</dt><dd style="margin: 0;" class="kz-mono">{{sel.mid}}</dd>
          <dt class="kz-muted">Attachments</dt><dd style="margin: 0;">{{sel.att}}</dd>
        </dl>
        <p style="margin: 0; padding: 12px; background: var(--surface-100); border-radius: 10px; font-size: 13px; line-height: 20px; white-space: pre-line;">{{sel.body}}</p>
        <div style="font: 700 11px/16px var(--font-sans); letter-spacing: .06em; text-transform: uppercase; color: var(--ink-muted);">Gemma 4 classification</div>
        <pre class="kz-mono" style="margin: 0; padding: 12px; background: var(--term-bg); color: var(--term-ink); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; line-height: 18px;">{{sel.json}}</pre>
        <sc-if value="{{raw}}" hint-placeholder-val="{{false}}">
          <pre class="kz-mono" style="margin: 0; padding: 12px; background: var(--term-bg); color: var(--term-ink); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; line-height: 18px;">{{sel.headers}}</pre>
        </sc-if>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;"><x-import component-from-global-scope="KzNet.Button" variant="secondary" size="sm">Re-classify</x-import><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" sc-camel-on-click="{{toggleRaw}}" aria-pressed="{{raw}}">{{rawLabel}}</button><a href="{{L.TicketDetail}}" class="kz-btn kz-btn-ghost kz-btn-sm" style="text-decoration: none;">Open ticket</a></div>
      </div>
    </aside>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1040}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { sel: 1 }; }
  renderVals() {
    var self = this;
    var C = { ISP_WELCOME: 'good', ISP_BLOCKER: 'warning', INCIDENT_REPORT: 'brand', REPLICATION_REPORT: 'info', ESCALATION: 'neutral', UNRECOGNIZED: 'critical', CHASER: 'neutral', ISP_CLOSURE: 'good' };
    var M = [
      ['11:20', 'IN', 'noc@noor.net', 'kazyon@noc.noor.net', 'RE: store 1420', 'ISP_BLOCKER', 'NET-1046', 'Dear Kazyon, we tried to call the site at 010 9981 2234 but it was unavailable. Kindly provide an available site contact.', 'None', '{\n  "intent": "SITE_CONTACT_UNREACHABLE",\n  "branch_code": "1420",\n  "isp": "NOOR",\n  "isp_ref": "243860",\n  "confidence": 0.94,\n  "next_action": "ASK_REGIONAL_IT_FOR_PHONE"\n}'],
      ['10:55', 'IN', 'CITSupport@kazyon.com', 'itsupport-agent@kazyon.com', '1312 Damanhour 3 down', 'INCIDENT_REPORT', 'NET-1052', 'Store 1312 not syncing. Router photo attached.\nSite contact: 012 7781 0042', 'router_1312.jpg (1.2 MB)', '{\n  "intent": "BRANCH_INCIDENT",\n  "branch_code": "1312",\n  "site_contact_phone": "01277810042",\n  "has_router_photo": true,\n  "confidence": 0.97,\n  "next_action": "VISION_CHECK"\n}'],
      ['10:12', 'IN', 'billing@orange.com', 'itsupport-agent@kazyon.com', 'Invoice dispute – October circuits', 'UNRECOGNIZED', '—', 'Please find attached the October invoice for 181 circuits.', 'invoice_oct.pdf', '{\n  "intent": "UNKNOWN",\n  "branch_code": null,\n  "confidence": 0.22,\n  "next_action": "HUMAN_REVIEW"\n}'],
      ['09:41', 'OUT', 'psupport@te.eg', 'psupport@te.eg', 'Kazyon #E33209 #6175613 #6181290 #1254', 'ESCALATION', 'NET-1055', 'Dear support\nkindly check LL & 4G connection\nLL order number : 6175613\n4G order number : 6181290\nsite contact 010 5512 7790\nsite work from 9 AM to 12 AM\npower working fine at site', 'None', '{\n  "template": "WE_ESCALATION",\n  "thread": "ISP"\n}'],
      ['09:00', 'IN', 'replication@kazyon.com', 'itsupport-agent@kazyon.com', 'Replication Dashboard - 21/10/2026', 'REPLICATION_REPORT', '5 tickets', 'HTML table · 1,150 rows · 12 Not Updated', 'None', '{\n  "intent": "REPLICATION_REPORT",\n  "rows": 1150,\n  "not_updated": 12,\n  "next_action": "NOTIFY_REGIONAL_IT"\n}'],
      ['08:21', 'IN', 'ccc-eg@orange.com', 'itsupport-agent@kazyon.com', 'ticket number (1-1312322942540 For QID QUO1-10316406 # 1173)', 'ISP_WELCOME', 'NET-1057', 'Your request has been registered and is being handled.', 'None', '{\n  "intent": "ISP_WELCOME",\n  "isp_ref": "1-1312322942540",\n  "branch_code": "1173",\n  "confidence": 0.99\n}'],
      ['08:14', 'IN', 'noc@noor.net', 'itsupport-agent@kazyon.com', 'RE: store 1099', 'ISP_CLOSURE', 'NET-1044', 'Link has been restored.\nNOOR#p v kazyon 10.10.99.1 Success rate is 100 percent', 'None', '{\n  "intent": "ISP_RESOLVED",\n  "next_action": "FINAL_VERIFICATION"\n}'],
      ['07:48', 'OUT', 'ccc-eg@orange.com', 'ccc-eg@orange.com', 'store 1173 # QUO1-10316406', 'ESCALATION', 'NET-1057', 'Dear NOC\nkindly check L.L and 4G connection store 1173', 'None', '{\n  "template": "ORANGE_ESCALATION",\n  "thread": "ISP"\n}']
    ];
    var i = this.state.sel, s = M[i], f = this.state.f || 'ALL';
    var F = { ALL: function () { return true; }, IN: function (m) { return m[1] === 'IN'; }, OUT: function (m) { return m[1] === 'OUT'; }, ISP: function (m) { return /ISP_/.test(m[5]); }, UNRECOGNIZED: function (m) { return m[5] === 'UNRECOGNIZED'; } };
    var L = { ALL: 'All', IN: 'Inbound', OUT: 'Outbound', ISP: 'ISP replies', UNRECOGNIZED: 'Unrecognized' };
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      chips: Object.keys(F).map(function (k) { return { label: L[k], n: M.filter(F[k]).length, cls: 'kz-chip' + (k === f ? ' kz-chip-on' : ''), pick: function () { self.setState({ f: k }); } }; }),
      raw: !!this.state.raw, rawLabel: this.state.raw ? 'Hide raw headers' : 'View raw headers',
      toggleRaw: function () { self.setState({ raw: !self.state.raw }); },
      nav: this.navMap(),
      mails: M.map(function (m, k) { return [m, k]; }).filter(function (p) { return F[f](p[0]); }).map(function (p) { var m = p[0], k = p[1]; return { time: m[0], dir: m[1], dtone: m[1] === 'IN' ? 'info' : 'outline', who: m[2], subject: m[4], cls: m[5], ctone: C[m[5]], ticket: m[6], pick: function () { self.setState({ sel: k }); }, style: 'cursor: pointer;' + (k === i ? ' background: var(--brand-100);' : '') }; }),
      sel: { from: s[1] === 'IN' ? s[2] : 'itsupport-agent@kazyon.com', to: s[1] === 'IN' ? s[3] : s[3] + ', ITInfrastructure@kazyon.com (cc)', subject: s[4], cls: s[5], ctone: C[s[5]], body: s[7], att: s[8], json: s[9], mid: '<' + (8800 + i * 37) + '.kz@kazyon.com>',
        headers: 'Message-ID: <' + (8800 + i * 37) + '.kz@kazyon.com>\nDate: Wed, 21 Oct 2026 ' + s[0] + ':07 +0300\nFrom: ' + (s[1] === 'IN' ? s[2] : 'itsupport-agent@kazyon.com') + '\nTo: ' + s[3] + '\nSubject: ' + s[4] + '\nX-Kz-Thread: ' + (/ISP|ESCALATION/.test(s[5]) ? 'ISP' : 'BRANCH') + '\nAuto-Submitted: no' }
    };
  }
}
</script>
```

## 9 · Network Diagnostics Sandbox (`/diagnostics`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Diagnostics Sandbox" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1040px;">
  <div class="kz-page-hd">
    <div>
      <h1>Network Diagnostics Sandbox</h1>
      <p>Run dual-ping and the 4G hub traceroute on any branch without opening a ticket.</p>
    </div>
  </div>

  <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start;">
    <div style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 16px;">
      <section class="kz-card">
        <div class="kz-card-hd"><h2>Target</h2></div>
        <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: end;">
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">Branch
            <sc-raw-select sc-camel-on-change="{{pickBranch}}" style="height: 40px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 10px; font: 500 14px var(--font-sans); background: var(--surface-000); color: var(--ink);">
              <sc-for list="{{branches}}" as="b" hint-placeholder-count="4"><option value="{{b.code}}">{{b.label}}</option></sc-for>
            </sc-raw-select>
          </label>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">IP 1 (router)<input value="{{b.ip1}}" class="kz-mono" style="height: 40px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 10px;"></label>
          <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600;">IP 2 (switch)<input value="{{b.ip2}}" class="kz-mono" style="height: 40px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 10px;"></label>
          <div style="display: flex; gap: 8px; align-items: center; height: 40px;"><x-import component-from-global-scope="KzNet.IspBadge" isp="{{b.isp}}"></x-import><span class="kz-tcard-meta">Hub {{b.hub}}</span></div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{runAll}}">Run full check</button>
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{runAll}}">Ping IP 1</button>
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{runAll}}">Ping IP 2</button>
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{runAll}}">Traceroute (4G hub check)</button>
        </div>
      </section>

      <section class="kz-card">
        <div class="kz-card-hd" style="flex-wrap: wrap;">
          <div><h2>Result</h2><p>{{res.when}}</p></div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <sc-for list="{{res.checks}}" as="c" hint-placeholder-count="3"><x-import component-from-global-scope="KzNet.StatusPill" label="{{c.label}}" state="{{c.state}}"></x-import></sc-for>
          </div>
        </div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 12px;">
          <div style="{{res.boxStyle}}"><b>{{res.code}}</b> — {{res.meaning}}</div>
          <pre class="kz-mono" style="margin: 0; padding: 14px; min-height: 220px; background: var(--term-bg); color: var(--term-ink); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; line-height: 19px;">{{res.log}}</pre>
        </div>
      </section>
    </div>

    <aside style="flex: 1 1 300px; max-width: 400px; display: flex; flex-direction: column; gap: 16px;">
      <section class="kz-card">
        <div class="kz-card-hd"><h2>Script settings</h2></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 12px; font-size: 13px;">
          <label style="display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 600;">DIAGNOSTIC_TIMEOUT_SEC<input type="number" value="20" style="width: 80px; height: 34px; padding: 0 8px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
          <label style="display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 600;">Ping count<input type="number" value="4" style="width: 80px; height: 34px; padding: 0 8px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
          <label style="display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 600;">Traceroute max hops<input type="number" value="15" style="width: 80px; height: 34px; padding: 0 8px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        </div>
      </section>
      <section class="kz-card">
        <div class="kz-card-hd"><h2>3G / 4G hub IPs</h2></div>
        <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
          <div style="display: flex; justify-content: space-between; align-items: center;"><x-import component-from-global-scope="KzNet.IspBadge" isp="ORANGE"></x-import><span class="kz-mono">10.247.8.1</span></div>
          <div style="display: flex; justify-content: space-between; align-items: center;"><x-import component-from-global-scope="KzNet.IspBadge" isp="WE"></x-import><span class="kz-mono">172.16.70.33 · 172.17.20.33</span></div>
          <div style="display: flex; justify-content: space-between; align-items: center;"><x-import component-from-global-scope="KzNet.IspBadge" isp="NOOR"></x-import><span class="kz-muted">No traceroute (LAN rule)</span></div>
          <a href="{{L.Directory}}" style="font-weight: 600;">Edit in ISP directory</a>
        </div>
      </section>
      <section class="kz-card">
        <div class="kz-card-hd"><h2>Recent sandbox runs</h2></div>
        <ul class="kz-card-bd" style="margin: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 13px;">
          <li style="display: flex; justify-content: space-between;"><span><b>1201</b> · 10:31</span><x-import component-from-global-scope="KzNet.Badge" tone="warning">INTERNAL_LAN_SWITCH</x-import></li>
          <li style="display: flex; justify-content: space-between;"><span><b>2009</b> · 09:15</span><x-import component-from-global-scope="KzNet.Badge" tone="critical">FULL_OUTAGE</x-import></li>
          <li style="display: flex; justify-content: space-between;"><span><b>1366</b> · 08:02</span><x-import component-from-global-scope="KzNet.Badge" tone="good">PASS</x-import></li>
        </ul>
      </section>
    </aside>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1040}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { code: '1173', ran: true, n: 1 }; }
  renderVals() {
    var self = this;
    var B = {
      '1173': { code: '1173', label: '1173-Ghmrawy · Cairo', ip1: '10.11.73.1', ip2: '10.11.73.2', isp: 'ORANGE', hub: '10.247.8.1', result: 'LOCAL_LOOP_DOWN_ON_4G' },
      '2009': { code: '2009', label: '2009-Kafr Nasar · Giza', ip1: '10.20.9.1', ip2: '10.20.9.2', isp: 'NOOR', hub: '—', result: 'FULL_OUTAGE' },
      '1201': { code: '1201', label: '1201-Hadayek El Ahram · Giza', ip1: '10.12.1.1', ip2: '10.12.1.2', isp: 'NOOR', hub: '—', result: 'INTERNAL_LAN_SWITCH' },
      '1366': { code: '1366', label: '1366-Nasr City 7 · Cairo', ip1: '10.13.66.1', ip2: '10.13.66.2', isp: 'NOOR', hub: '—', result: 'PASS' }
    };
    var b = B[this.state.code];
    var R = {
      LOCAL_LOOP_DOWN_ON_4G: { checks: [['IP1', 'up'], ['IP2', 'down'], ['4G', 'hub']], tone: 'info', meaning: 'Router reachable through the 4G backup. Escalate the local loop to the ISP.', log: '$ ping -c 4 ' + b.ip1 + '\n0% packet loss, avg 182 ms\n$ ping -c 4 ' + b.ip2 + '\n100% packet loss\n$ traceroute -n ' + b.ip1 + '\n 1  10.100.109.1   0.6 ms\n 2  10.247.8.1    41.2 ms   ← 4G hub\n 3  ' + b.ip1 + '   180.9 ms' },
      FULL_OUTAGE: { checks: [['IP1', 'down'], ['IP2', 'skip']], tone: 'critical', meaning: 'Router unreachable. The branch is down from the WAN; escalate to the ISP.', log: '$ ping -c 4 ' + b.ip1 + '\n4 packets transmitted, 0 received, 100% packet loss\nIP 2 skipped (IP 1 down)' },
      INTERNAL_LAN_SWITCH: { checks: [['IP1', 'up'], ['IP2', 'down']], tone: 'warning', meaning: 'Router up, switch down on a NOOR line. Return to Regional IT as an internal LAN issue.', log: '$ ping -c 4 ' + b.ip1 + '\n0% packet loss, avg 24 ms\n$ ping -c 4 ' + b.ip2 + '\n100% packet loss\nNOOR branch: no traceroute needed' },
      PASS: { checks: [['IP1', 'up'], ['IP2', 'up']], tone: 'good', meaning: 'Router and switch both reachable. Network healthy.', log: '$ ping -c 4 ' + b.ip1 + '\n0% packet loss, avg 21 ms\n$ ping -c 4 ' + b.ip2 + '\n0% packet loss, avg 23 ms' }
    };
    var r = R[b.result];
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      branches: Object.keys(B).map(function (k) { return B[k]; }),
      b: b,
      pickBranch: function (e) { self.setState({ code: e.target.value }); },
      runAll: function () { self.setState({ n: self.state.n + 1 }); },
      res: {
        when: 'Run #' + this.state.n + ' · ' + b.label + ' · 6.1 s',
        checks: r.checks.map(function (c) { return { label: c[0], state: c[1] }; }),
        code: b.result, meaning: r.meaning, log: r.log,
        boxStyle: 'padding: 10px 12px; border-radius: 10px; font-size: 13px; background: var(--' + r.tone + '-bg); color: var(--' + r.tone + ');'
      }
    };
  }
}
</script>
```

## 10 · Branches & ISP Directory (`/directory`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Branches &amp; ISPs" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1060px;">
  <div class="kz-page-hd">
    <div>
      <h1>Branches &amp; ISP Directory</h1>
      <p>1,150 stores · 5 regions · 3 ISPs · seeded from “Copy of All store ISP (2).xlsx”</p>
    </div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{toggleSeed}}">Import Excel sheet</button>
      <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{openAdd}}">+ Add branch</button>
    </div>
  </div>

  <sc-if value="{{edit}}" hint-placeholder-val="{{false}}">
    <div class="kz-modal-scrim">
      <div role="dialog" aria-modal="true" aria-label="{{editTitle}}" class="kz-card" style="width: 100%; max-width: 720px; box-shadow: var(--shadow-raised); max-height: 92%; overflow-y: auto;">
        <div class="kz-card-hd"><div><h2>{{editTitle}}</h2><p>Columns A–K of the store sheet. IPs fill in from the SAP code; override if the branch differs.</p></div>
          <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" aria-label="Close" sc-camel-on-click="{{closeEdit}}">✕</button></div>
        <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px;">
          <label class="kz-field">SAP code (A)<input value="{{form.code}}" sc-camel-on-change="{{setCode}}" inputmode="numeric" maxlength="4" class="kz-mono"></label>
          <label class="kz-field">Store name (B)<input value="{{form.name}}" sc-camel-on-change="{{noop}}"></label>
          <label class="kz-field">Region (E)<sc-raw-select><option>Behera</option><option>Cairo</option><option>New October</option><option>Assyut</option><option>Giza</option></sc-raw-select></label>
          <label class="kz-field">IP router (C)<input value="{{form.ip1}}" sc-camel-on-change="{{noop}}" class="kz-mono"><small>Derived: 10.&lt;AB&gt;.&lt;CD&gt;.1</small></label>
          <label class="kz-field">IP server switch (D)<input value="{{form.ip2}}" sc-camel-on-change="{{noop}}" class="kz-mono"><small>Derived: 10.&lt;AB&gt;.&lt;CD&gt;.2</small></label>
          <label class="kz-field">Regional IT email (G)<input value="{{form.rit}}" sc-camel-on-change="{{noop}}"></label>
          <label class="kz-field">ISP (H)<sc-raw-select><option>NOOR</option><option>ORANGE</option><option>WE</option></sc-raw-select></label>
          <label class="kz-field">ISP email (F)<input value="{{form.mail}}" sc-camel-on-change="{{noop}}"></label>
          <label class="kz-field">3G / 4G hub IP (I)<input value="{{form.hub}}" sc-camel-on-change="{{noop}}" class="kz-mono"></label>
          <label class="kz-field">L.L ID (J)<input value="{{form.ll}}" sc-camel-on-change="{{noop}}" class="kz-mono"></label>
          <label class="kz-field">3G ID (K)<input value="{{form.g3}}" sc-camel-on-change="{{noop}}" class="kz-mono"></label>
          <label style="display: flex; gap: 8px; align-items: center; font-size: 13px; font-weight: 600; align-self: end; height: 40px;"><input type="checkbox" checked="" style="accent-color: var(--brand-600); width: 16px; height: 16px;"> Branch active</label>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{closeEdit}}">Cancel</button>
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{closeEdit}}">Save branch</button>
        </div>
      </div>
    </div>
  </sc-if>

  <div class="kz-seg" role="tablist" aria-label="Directory" style="align-self: flex-start;">
    <sc-for list="{{tabs}}" as="t" hint-placeholder-count="2"><button type="button" role="tab" aria-selected="{{t.on}}" class="{{t.cls}}" sc-camel-on-click="{{t.pick}}">{{t.label}}</button></sc-for>
  </div>

  <sc-if value="{{seed}}" hint-placeholder-val="{{false}}">
    <section class="kz-card" style="border-color: var(--brand-500);">
      <div class="kz-card-hd" style="flex-wrap: wrap;"><div><h2>Excel bulk seeder · dry run</h2><p>Copy of All store ISP (2).xlsx · columns A–K · nothing is written until you apply</p></div>
        <div style="display: flex; gap: 8px;"><button type="button" class="kz-btn kz-btn-secondary kz-btn-sm" sc-camel-on-click="{{toggleSeed}}">Cancel</button><button type="button" class="kz-btn kz-btn-primary kz-btn-sm" sc-camel-on-click="{{toggleSeed}}">Apply 1,150 rows</button></div></div>
      <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px;">
        <div class="kz-card" style="padding: 12px;"><div class="kz-kpi-label">Unchanged</div><div class="kz-kpi-val" style="font-size: 24px;">1,121</div></div>
        <div class="kz-card" style="padding: 12px;"><div class="kz-kpi-label">Updated</div><div class="kz-kpi-val" style="font-size: 24px;">26</div><div class="kz-tcard-meta">mostly Col F / Col J changes</div></div>
        <div class="kz-card" style="padding: 12px;"><div class="kz-kpi-label">New</div><div class="kz-kpi-val" style="font-size: 24px;">3</div></div>
        <div class="kz-card" style="padding: 12px; background: var(--warning-bg); border-color: var(--warning);"><div class="kz-kpi-label" style="color: var(--warning);">Warnings</div><div class="kz-kpi-val" style="font-size: 24px;">2</div><div class="kz-tcard-meta">“Orang” normalised to ORANGE</div></div>
      </div>
    </section>
  </sc-if>

  <sc-if value="{{isBranches}}" hint-placeholder-val="{{true}}">
    <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
      <label class="kz-search" style="max-width: 320px;"><span class="kz-muted">Search</span><input type="search" placeholder="SAP code, store, IP, L.L ID" style="border: 0; background: transparent; outline: none; font: 500 13px var(--font-sans); color: var(--ink); flex: 1; min-width: 0;"></label>
      <sc-for list="{{regions}}" as="r" hint-placeholder-count="6"><button type="button" class="{{r.cls}}" sc-camel-on-click="{{r.pick}}">{{r.label}}</button></sc-for>
    </div>
    <section class="kz-card" style="overflow: hidden;">
      <div class="kz-scroll-x">
        <sc-raw-table class="kz-table">
          <sc-raw-thead><sc-raw-tr><sc-raw-th>SAP</sc-raw-th><sc-raw-th>Store name</sc-raw-th><sc-raw-th>IP 1</sc-raw-th><sc-raw-th>IP 2</sc-raw-th><sc-raw-th>Region</sc-raw-th><sc-raw-th>Regional IT</sc-raw-th><sc-raw-th>ISP</sc-raw-th><sc-raw-th>ISP email</sc-raw-th><sc-raw-th>3G hub</sc-raw-th><sc-raw-th>L.L ID</sc-raw-th><sc-raw-th>3G ID</sc-raw-th><sc-raw-th></sc-raw-th></sc-raw-tr></sc-raw-thead>
          <sc-raw-tbody>
            <sc-for list="{{rows}}" as="b" hint-placeholder-count="10">
              <sc-raw-tr>
                <sc-raw-td class="kz-mono" style="font-weight: 700;">{{b.code}}</sc-raw-td>
                <sc-raw-td class="kz-nowrap" style="font-weight: 600;">{{b.name}}</sc-raw-td>
                <sc-raw-td class="kz-mono">{{b.ip1}}</sc-raw-td>
                <sc-raw-td class="kz-mono">{{b.ip2}}</sc-raw-td>
                <sc-raw-td>{{b.region}}</sc-raw-td>
                <sc-raw-td class="kz-tcard-meta kz-nowrap">{{b.rit}}</sc-raw-td>
                <sc-raw-td><x-import component-from-global-scope="KzNet.IspBadge" isp="{{b.isp}}"></x-import></sc-raw-td>
                <sc-raw-td class="kz-tcard-meta kz-nowrap">{{b.mail}}</sc-raw-td>
                <sc-raw-td class="kz-mono">{{b.hub}}</sc-raw-td>
                <sc-raw-td class="kz-mono kz-nowrap">{{b.ll}}</sc-raw-td>
                <sc-raw-td class="kz-mono kz-nowrap">{{b.g3}}</sc-raw-td>
                <sc-raw-td><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" sc-camel-on-click="{{b.edit}}" aria-label="Edit {{b.name}}">Edit</button></sc-raw-td>
              </sc-raw-tr>
            </sc-for>
          </sc-raw-tbody>
        </sc-raw-table>
      </div>
      <div style="padding: 12px 16px; border-top: 1px solid var(--border); font-size: 13px;" class="kz-muted">Showing {{rowCount}} of 1,150 · IPs derive from SAP code (10.&lt;AB&gt;.&lt;CD&gt;.1 / .2) unless overridden</div>
    </section>
  </sc-if>

  <sc-if value="{{isIsps}}" hint-placeholder-val="{{false}}">
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
      <sc-for list="{{isps}}" as="p" hint-placeholder-count="3">
        <section class="kz-card">
          <div class="kz-card-hd"><x-import component-from-global-scope="KzNet.IspBadge" isp="{{p.name}}"></x-import><span class="kz-tcard-meta">{{p.stores}} stores</span></div>
          <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
            <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Support email<input value="{{p.mail}}" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
            <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">CC<input value="ITInfrastructure@kazyon.com" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
            <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">4G hub IP(s)<input value="{{p.hub}}" class="kz-mono" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px;"></label>
            <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;">
              <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Welcome SLA (min)<input type="number" value="120" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
              <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Follow-up SLA (min)<input type="number" value="300" style="height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
            </div>
            <div style="font-weight: 600;">Escalation template</div>
            <pre class="kz-mono" style="margin: 0; padding: 10px 12px; background: var(--surface-100); border: 1px solid var(--border); border-radius: 8px; white-space: pre-wrap; line-height: 18px;">{{p.tpl}}</pre>
            <div style="display: flex; justify-content: flex-end;"><x-import component-from-global-scope="KzNet.Button" variant="primary" size="sm">Save</x-import></div>
          </div>
        </section>
      </sc-for>
    </div>
  </sc-if>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1060}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { tab: 'branches', region: 'All', seed: false }; }
  renderVals() {
    var self = this, st = this.state;
    var RIT = { Behera: 'BITSupport@kazyon.com', Cairo: 'CITSupport@kazyon.com', 'New October': 'newoctregion@kazyon.com', Assyut: 'assiutregion@kazyon.com', Giza: 'GITSupport@kazyon.com' };
    var MAIL = { NOOR: 'noc@noor.net', ORANGE: 'ccc-eg@orange.com', WE: 'psupport@te.eg' };
    var ip = function (c, n) { return '10.' + parseInt(c.slice(0, 2), 10) + '.' + parseInt(c.slice(2), 10) + '.' + n; };
    var B = [
      ['1173', 'Ghmrawy', 'Cairo', 'ORANGE', '10.247.8.1', 'QUO1-10316406', 'QUO1-10316407'],
      ['1254', 'El Mansheya', 'Behera', 'WE', '172.16.70.33', '6175613', '6181290'],
      ['2009', 'Kafr Nasar', 'Giza', 'NOOR', '', '', ''],
      ['1450', 'Soliman Metwaly', 'Assyut', 'NOOR', '', '', ''],
      ['1088', 'Gamal Salem', 'New October', 'ORANGE', '10.247.8.1', 'QUO1-10316780', 'QUO1-10316781'],
      ['1005', 'Tosson', 'Behera', 'WE', '172.17.20.33', '6174402', '6180113'],
      ['1201', 'Hadayek El Ahram', 'Giza', 'NOOR', '', '', ''],
      ['1312', 'Damanhour 3', 'Behera', 'NOOR', '', '', ''],
      ['1366', 'Nasr City 7', 'Cairo', 'NOOR', '', '', ''],
      ['1420', 'Sheikh Zayed 2', 'New October', 'NOOR', '', '', ''],
      ['1510', 'Abnoub', 'Assyut', 'WE', '172.16.70.33', '6176021', '6182544']
    ].map(function (b) { return { code: b[0], name: b[0] + '-' + b[1], ip1: ip(b[0], 1), ip2: ip(b[0], 2), region: b[2], rit: RIT[b[2]], isp: b[3], mail: MAIL[b[3]], hub: b[4] || '—', ll: b[5] || '—', g3: b[6] || '—' }; });
    var regions = ['All', 'Behera', 'Cairo', 'New October', 'Assyut', 'Giza'];
    B.forEach(function (b) { b.edit = function () { self.setState({ edit: 'edit', form: b }); }; });
    var form = st.form || { code: '', name: '', ip1: '', ip2: '', rit: '', mail: '', hub: '', ll: '', g3: '' };
    var blank = function (v) { return v === '—' ? '' : v; };
    return {
      edit: !!st.edit, editTitle: st.edit === 'edit' ? 'Edit branch ' + form.code : 'Add branch',
      form: { code: form.code, name: form.name, ip1: form.ip1, ip2: form.ip2, rit: form.rit, mail: form.mail, hub: blank(form.hub), ll: blank(form.ll), g3: blank(form.g3) },
      openAdd: function () { self.setState({ edit: 'add', form: null }); },
      closeEdit: function () { self.setState({ edit: false }); },
      noop: function () {},
      setCode: function (e) {
        var c = e.target.value.replace(/\D/g, '').slice(0, 4);
        var f = Object.assign({}, self.state.form || {}, { code: c });
        if (c.length === 4) { f.ip1 = ip(c, 1); f.ip2 = ip(c, 2); }
        self.setState({ form: f });
      },
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      tabs: [['branches', 'Branches · 1,150'], ['isps', 'ISPs · 3']].map(function (t) { var on = t[0] === st.tab; return { label: t[1], on: on, cls: on ? 'on' : '', pick: function () { self.setState({ tab: t[0] }); } }; }),
      isBranches: st.tab === 'branches', isIsps: st.tab === 'isps', seed: st.seed,
      toggleSeed: function () { self.setState({ seed: !self.state.seed }); },
      regions: regions.map(function (r) { return { label: r, cls: 'kz-chip' + (r === st.region ? ' kz-chip-on' : ''), pick: function () { self.setState({ region: r }); } }; }),
      rows: B.filter(function (b) { return st.region === 'All' || b.region === st.region; }),
      rowCount: B.filter(function (b) { return st.region === 'All' || b.region === st.region; }).length,
      isps: [
        { name: 'NOOR', stores: 906, mail: 'noc@noor.net', hub: '—', tpl: 'Subject: store <SAP_CODE>\n\nDear NOC\nKindly check connection store <SAP_CODE>\nsite contact : <PHONE>' },
        { name: 'ORANGE', stores: 181, mail: 'ccc-eg@orange.com', hub: '10.247.8.1', tpl: 'Subject: store <SAP_CODE> # <LL_ID>\n\nDear NOC\nkindly check L.L and 4G connection store <SAP_CODE>\n<SAP_CODE>\n<LL_ID>\n<3G_ID>\nsite contact : <PHONE>' },
        { name: 'WE', stores: 63, mail: 'psupport@te.eg', hub: '172.16.70.33, 172.17.20.33', tpl: 'Subject: Kazyon #E33209 #<LL_ID> #<3G_ID> #<SAP_CODE>\n\nDear support\nkindly check LL & 4G connection\nLL order number : <LL_ID>\n4G order number : <3G_ID>\nsite contact <PHONE>\nsite work from 9 AM to 12 AM\npower working fine at site' }
      ]
    };
  }
}
</script>
```

## 11 · Users, Roles & RBAC (`/users`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="Users &amp; Roles" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1060px;">
  <div class="kz-page-hd">
    <div>
      <h1>Users, Roles &amp; Permissions</h1>
      <p>Super Admin only · permissions are granted per resource and action (resource:action)</p>
    </div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{openRole}}">+ New role</button>
      <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{openInvite}}">+ Invite user</button>
    </div>
  </div>

  <sc-if value="{{modal}}" hint-placeholder-val="{{false}}">
    <div class="kz-modal-scrim">
      <div role="dialog" aria-modal="true" aria-label="{{modalTitle}}" class="kz-card" style="width: 100%; max-width: 520px; box-shadow: var(--shadow-raised);">
        <div class="kz-card-hd"><div><h2>{{modalTitle}}</h2><p>{{modalSub}}</p></div>
          <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" aria-label="Close" sc-camel-on-click="{{closeModal}}">✕</button></div>
        <sc-if value="{{isInvite}}" hint-placeholder-val="{{true}}">
          <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 14px;">
            <label class="kz-field">Display name<input placeholder="Full name"></label>
            <label class="kz-field">Kazyon email<input type="email" placeholder="name@kazyon.com"></label>
            <label class="kz-field">Role<sc-raw-select><option>HQ Network Engineer</option><option>Viewer / IT Manager</option><option>Super Admin</option></sc-raw-select></label>
            <label class="kz-field">Temporary password<input value="Kz-7Q4m-29xT" class="kz-mono"><small>The user must change it at first sign-in.</small></label>
          </div>
        </sc-if>
        <sc-if value="{{isRole}}" hint-placeholder-val="{{false}}">
          <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 14px;">
            <label class="kz-field">Role name<input placeholder="e.g. Regional IT Liaison"></label>
            <label class="kz-field">Start from<sc-raw-select><option>Viewer / Auditor</option><option>Network Engineer</option><option>Empty (no permissions)</option></sc-raw-select></label>
            <p class="kz-tcard-meta" style="margin: 0;">You can fine-tune each resource:action in the matrix after creating it.</p>
          </div>
        </sc-if>
        <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 0 16px 16px;">
          <button type="button" class="kz-btn kz-btn-secondary" sc-camel-on-click="{{closeModal}}">Cancel</button>
          <button type="button" class="kz-btn kz-btn-primary" sc-camel-on-click="{{closeModal}}">{{modalCta}}</button>
        </div>
      </div>
    </div>
  </sc-if>

  <section class="kz-card" style="overflow: hidden;">
    <div class="kz-card-hd" style="padding-bottom: 12px;"><h2>Users</h2><span class="kz-tcard-meta">6 users · 1 suspended</span></div>
    <div class="kz-scroll-x">
      <sc-raw-table class="kz-table">
        <sc-raw-thead><sc-raw-tr><sc-raw-th>Name</sc-raw-th><sc-raw-th>Email</sc-raw-th><sc-raw-th>Role</sc-raw-th><sc-raw-th>Status</sc-raw-th><sc-raw-th>Last sign-in</sc-raw-th><sc-raw-th></sc-raw-th></sc-raw-tr></sc-raw-thead>
        <sc-raw-tbody>
          <sc-for list="{{users}}" as="u" hint-placeholder-count="6">
            <sc-raw-tr>
              <sc-raw-td><div style="display: flex; gap: 10px; align-items: center;"><span class="kz-avatar" style="width: 28px; height: 28px; font-size: 11px;">{{u.ini}}</span><b class="kz-nowrap">{{u.name}}</b></div></sc-raw-td>
              <sc-raw-td class="kz-tcard-meta kz-nowrap">{{u.email}}</sc-raw-td>
              <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{u.rtone}}">{{u.role}}</x-import></sc-raw-td>
              <sc-raw-td><x-import component-from-global-scope="KzNet.Badge" tone="{{u.stone}}">{{u.status}}</x-import></sc-raw-td>
              <sc-raw-td class="kz-num kz-nowrap">{{u.last}}</sc-raw-td>
              <sc-raw-td class="kz-nowrap"><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">Edit</button><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm">Reset password</button><button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" style="color: var(--critical);">{{u.suspend}}</button></sc-raw-td>
            </sc-raw-tr>
          </sc-for>
        </sc-raw-tbody>
      </sc-raw-table>
    </div>
  </section>

  <section class="kz-card" style="overflow: hidden;">
    <div class="kz-card-hd" style="flex-wrap: wrap; padding-bottom: 12px;">
      <div><h2>Permission matrix</h2><p>Click a cell to grant or revoke. Changes apply on save.</p></div>
      <div class="kz-seg" role="group" aria-label="Role">
        <sc-for list="{{roles}}" as="r" hint-placeholder-count="3"><button type="button" class="{{r.cls}}" sc-camel-on-click="{{r.pick}}">{{r.label}}</button></sc-for>
      </div>
    </div>
    <div class="kz-scroll-x">
      <sc-raw-table class="kz-table">
        <sc-raw-thead><sc-raw-tr><sc-raw-th>Resource</sc-raw-th><sc-for list="{{actions}}" as="a" hint-placeholder-count="5"><sc-raw-th style="text-align: center;">{{a}}</sc-raw-th></sc-for></sc-raw-tr></sc-raw-thead>
        <sc-raw-tbody>
          <sc-for list="{{matrix}}" as="m" hint-placeholder-count="8">
            <sc-raw-tr>
              <sc-raw-td><span class="kz-mono" style="font-weight: 700;">{{m.res}}:*</span><div class="kz-tcard-meta">{{m.desc}}</div></sc-raw-td>
              <sc-for list="{{m.cells}}" as="c" hint-placeholder-count="5">
                <sc-raw-td style="text-align: center;">
                  <sc-if value="{{c.na}}" hint-placeholder-val="{{false}}"><span class="kz-muted" aria-label="Not applicable">—</span></sc-if>
                  <sc-if value="{{c.ok}}" hint-placeholder-val="{{true}}">
                    <button type="button" sc-camel-on-click="{{c.toggle}}" aria-pressed="{{c.on}}" aria-label="{{c.aria}}" style="{{c.style}}">{{c.mark}}</button>
                  </sc-if>
                </sc-raw-td>
              </sc-for>
            </sc-raw-tr>
          </sc-for>
        </sc-raw-tbody>
      </sc-raw-table>
    </div>
    <div style="display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border);">
      <x-import component-from-global-scope="KzNet.Button" variant="secondary" size="sm">Discard</x-import>
      <x-import component-from-global-scope="KzNet.Button" variant="primary" size="sm">Save permissions</x-import>
    </div>
  </section>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1060}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) {
    super(p);
    var full = {}, eng = {}, view = {};
    var R = ['tickets', 'diagnostics', 'emails', 'replication', 'branches', 'isps', 'users', 'settings'];
    var A = ['read', 'create', 'update', 'delete', 'execute'];
    R.forEach(function (r) { A.forEach(function (a) { var k = r + ':' + a; full[k] = true; view[k] = a === 'read' && r !== 'users' && r !== 'settings'; eng[k] = ['users', 'settings'].indexOf(r) < 0 && a !== 'delete'; }); });
    eng['branches:create'] = false; eng['isps:update'] = false;
    this.state = { role: 'engineer', perms: { admin: full, engineer: eng, viewer: view } };
  }
  renderVals() {
    var self = this, st = this.state;
    var R = [['tickets', 'Board, list, detail, manual tickets'], ['diagnostics', 'Ping and traceroute runs'], ['emails', 'Mailbox log, replies, .eml upload'], ['replication', 'Replication reports'], ['branches', '1,150-branch directory'], ['isps', 'ISP emails, hubs, templates'], ['users', 'Users and roles'], ['settings', 'Mailbox, vLLM, SLA, kill-switch']];
    var A = ['read', 'create', 'update', 'delete', 'execute'];
    var NA = { 'diagnostics:delete': 1, 'replication:update': 1, 'users:execute': 1, 'isps:execute': 1, 'branches:execute': 1 };
    var P = st.perms[st.role];
    var locked = st.role === 'admin';
    var inv = st.modal === 'invite';
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      modal: !!st.modal, isInvite: inv, isRole: st.modal === 'role',
      modalTitle: inv ? 'Invite user' : 'New role',
      modalSub: inv ? 'They get an email with a sign-in link.' : 'Roles group permissions; assign them to users.',
      modalCta: inv ? 'Send invite' : 'Create role',
      openInvite: function () { self.setState({ modal: 'invite' }); },
      openRole: function () { self.setState({ modal: 'role' }); },
      closeModal: function () { self.setState({ modal: false }); },
      nav: this.navMap(),
      users: [
        ['JS', 'John Safwat', 'john.safwat@kazyon.com', 'Super Admin', 'Active', 'Today 11:02'],
        ['MA', 'Mona Adel', 'mona.adel@kazyon.com', 'HQ Network Engineer', 'Active', 'Today 10:47'],
        ['KH', 'Karim Hassan', 'karim.hassan@kazyon.com', 'HQ Network Engineer', 'Active', 'Today 08:15'],
        ['NE', 'Nourhan Ezzat', 'nourhan.ezzat@kazyon.com', 'HQ Network Engineer', 'Active', 'Yesterday 22:30'],
        ['AF', 'Ahmed Farouk', 'ahmed.farouk@kazyon.com', 'Viewer / IT Manager', 'Active', '19 Oct 14:02'],
        ['SR', 'Sherif Ramzy', 'sherif.ramzy@kazyon.com', 'HQ Network Engineer', 'Suspended', '2 Sep 09:10']
      ].map(function (u) { return { ini: u[0], name: u[1], email: u[2], role: u[3], rtone: u[3] === 'Super Admin' ? 'brand' : u[3].indexOf('Viewer') === 0 ? 'neutral' : 'info', status: u[4], stone: u[4] === 'Active' ? 'good' : 'critical', last: u[5], suspend: u[4] === 'Active' ? 'Suspend' : 'Reactivate' }; }),
      roles: [['admin', 'Super Admin'], ['engineer', 'Network Engineer'], ['viewer', 'Viewer / Auditor']].map(function (r) { return { label: r[1], cls: r[0] === st.role ? 'on' : '', pick: function () { self.setState({ role: r[0] }); } }; }),
      actions: A,
      matrix: R.map(function (r) {
        return { res: r[0], desc: r[1], cells: A.map(function (a) {
          var k = r[0] + ':' + a, on = !!P[k], na = !!NA[k];
          return { na: na, ok: !na, on: on, mark: on ? '✓' : '', aria: (on ? 'Revoke ' : 'Grant ') + k,
            style: 'width: 28px; height: 28px; border-radius: 6px; cursor: ' + (locked ? 'not-allowed' : 'pointer') + '; font: 700 14px var(--font-sans); border: 1.5px solid ' + (on ? 'var(--brand-600)' : 'var(--border-strong)') + '; background: ' + (on ? 'var(--brand-600)' : 'var(--surface-000)') + '; color: var(--on-brand);',
            toggle: function () { if (locked) return; var p = Object.assign({}, self.state.perms); var cur = Object.assign({}, p[st.role]); cur[k] = !cur[k]; p[st.role] = cur; self.setState({ perms: p }); } };
        }) };
      })
    };
  }
}
</script>
```

## 12 · AI Agent, Mailbox & SLA Settings (`/settings`)

```html
<x-import component-from-global-scope="KzNet.AppShell" active="AI &amp; SLA Settings" hrefs="{{nav}}" theme="{{theme}}" on-toggle-theme="{{toggleTheme}}" style="min-height: 1220px;">
  <div class="kz-page-hd">
    <div>
      <h1>AI Agent, Mailbox &amp; SLA Settings</h1>
      <p>PROD :8084 · changes are logged to the audit trail</p>
    </div>
    <x-import component-from-global-scope="KzNet.Button" variant="primary">Save all changes</x-import>
  </div>

  <section style="{{killBox}}">
    <div style="flex: 999 1 420px;">
      <h2 style="margin: 0; font-size: 18px; line-height: 26px;">Global AI master kill-switch</h2>
      <p style="margin: 4px 0 0; font-size: 13px; line-height: 20px;">{{killText}}</p>
    </div>
    <button type="button" class="{{killBtn}}" sc-camel-on-click="{{toggleKill}}" aria-pressed="{{killed}}">{{killLabel}}</button>
  </section>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr)); gap: 16px;">
    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>Service account mailbox</h2><p>IMAP polling and SMTP sending</p></div><span class="{{connCls}}">{{connText}}</span></div>
      <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; font-size: 13px;">
        <label style="grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Account<input value="itsupport-agent@kazyon.com" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">IMAP host<input value="outlook.office365.com" class="kz-mono" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px;"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">IMAP port<input type="number" value="993" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">SMTP host<input value="smtp.office365.com" class="kz-mono" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px;"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">SMTP port<input type="number" value="587" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Password<input type="password" value="••••••••••••" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Poll every (sec)<input type="number" value="30" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <div style="grid-column: 1 / -1;"><button type="button" class="kz-btn kz-btn-secondary kz-btn-sm" sc-camel-on-click="{{testConn}}">Test connection</button></div>
      </div>
    </section>

    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>vLLM model endpoint</h2><p>Gemma 4 26B A4B NVFP4 · multimodal</p></div><span class="kz-live">412 ms</span></div>
      <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; font-size: 13px;">
        <label style="grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Endpoint<input value="http://10.100.109.9:8002/v1" class="kz-mono" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px;"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Temperature<input type="number" step="0.1" value="0.1" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Max tokens<input type="number" value="2048" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="grid-column: 1 / -1; display: flex; flex-direction: column; gap: 6px; font-weight: 600;">
          <span style="display: flex; justify-content: space-between;">Confidence threshold for auto-action<span class="kz-num" style="color: var(--brand-text);">{{conf}}</span></span>
          <input type="range" min="50" max="99" value="{{confVal}}" sc-camel-on-change="{{setConf}}" style="accent-color: var(--brand-600);">
          <span class="kz-tcard-meta" style="font-weight: 500;">Below this, the email goes to Human Review instead of being acted on.</span>
        </label>
      </div>
    </section>

    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>SLA timers &amp; loop guard</h2><p>Defaults; ISPs can override in the directory</p></div></div>
      <div class="kz-card-bd" style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; font-size: 13px;">
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">ISP Welcome SLA (min)<input type="number" value="120" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Follow-up interval (min)<input type="number" value="300" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">Max chasers before human<input type="number" value="4" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="display: flex; flex-direction: column; gap: 4px; font-weight: 600;">MAX_OUTBOUND_EMAILS_PER_TICKET_HOUR<input type="number" value="6" style="height: 38px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
        <label style="grid-column: 1 / -1; display: flex; gap: 8px; align-items: center; font-weight: 600;"><input type="checkbox" checked="" style="accent-color: var(--brand-600); width: 16px; height: 16px;"> Ignore auto-reply and Auto-Submitted emails</label>
      </div>
    </section>

    <section class="kz-card">
      <div class="kz-card-hd"><div><h2>Human fallback escalation</h2><p>Who receives the full incident report</p></div></div>
      <div class="kz-card-bd" style="display: flex; flex-direction: column; gap: 10px; font-size: 13px;">
        <sc-for list="{{fallback}}" as="f" hint-placeholder-count="2">
          <div style="display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px;">
            <span class="kz-avatar" style="width: 28px; height: 28px; font-size: 11px;">{{f.ini}}</span>
            <div style="flex: 1; min-width: 0;"><b>{{f.email}}</b><div class="kz-tcard-meta">{{f.role}}</div></div>
            <button type="button" class="kz-btn kz-btn-ghost kz-btn-sm" sc-camel-on-click="{{f.remove}}">Remove</button>
          </div>
        </sc-for>
        <div style="display: flex; gap: 8px;">
          <label style="flex: 1; display: flex;"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden;">New fallback email</span><input placeholder="engineer@kazyon.com" style="flex: 1; height: 36px; padding: 0 10px; border: 1px solid var(--border-strong); border-radius: 8px; font: 500 13px var(--font-sans);"></label>
          <button type="button" class="kz-btn kz-btn-secondary kz-btn-sm" style="height: 36px;" sc-camel-on-click="{{addFallback}}">Add</button>
        </div>
      </div>
    </section>
  </div>
</x-import>
</x-dc>
<script type="text/x-dc" data-dc-script="" data-props="{&quot;dark&quot;:{&quot;editor&quot;:&quot;boolean&quot;,&quot;default&quot;:false},&quot;$preview&quot;:{&quot;width&quot;:1440,&quot;height&quot;:1220}}">
class Component extends DCLogic {
  themeName() { return (this.state && this.state.theme) || (this.props.dark ? 'dark' : 'light'); }
  linkMap() {
    var d = this.themeName() === 'dark', L = {};
    var D = { Login: 'DarkLogin', Main: 'DarkDashboard', Board: 'DarkBoard', TicketsList: 'DarkTicketsList', TicketDetail: 'DarkTicket', Replication: 'DarkReplication', Escalations: 'DarkEscalations', Mailbox: 'DarkMailbox', Diagnostics: 'DarkDiagnostics', Directory: 'DarkDirectory', Users: 'DarkUsers', Settings: 'DarkSettings' };
    Object.keys(D).forEach(function (k) { L[k] = (d ? D[k] : k) + '.dc.html'; });
    return L;
  }
  navMap() {
    var L = this.linkMap();
    return { 'Dashboard': L.Main, 'Kanban Board': L.Board, 'Tickets List': L.TicketsList, 'Human Review': L.Escalations, 'Replication Monitor': L.Replication, 'Mailbox & Triage': L.Mailbox, 'Diagnostics Sandbox': L.Diagnostics, 'Branches & ISPs': L.Directory, 'Users & Roles': L.Users, 'AI & SLA Settings': L.Settings };
  }
  constructor(p) { super(p); this.state = { killed: false, conn: 'idle', conf: 80, fb: [['NO', 'noc-oncall@kazyon.com', 'On-duty engineer'], ['IT', 'ITInfrastructure@kazyon.com', 'HQ IT Infrastructure team']] }; }
  renderVals() {
    var self = this, st = this.state;
    var conn = { idle: ['Not tested', 'kz-tcard-meta'], ok: ['IMAP ✓ · SMTP ✓', 'kz-live'] }[st.conn];
    return {
      theme: this.themeName(),
      L: this.linkMap(),
      toggleTheme: function () { self.setState({ theme: self.themeName() === 'dark' ? 'light' : 'dark' }); },
      nav: this.navMap(),
      killed: st.killed,
      killLabel: st.killed ? 'Resume AI agent' : 'Stop all AI automation',
      killBtn: st.killed ? 'kz-btn kz-btn-primary' : 'kz-btn kz-btn-danger',
      killText: st.killed ? 'AI automation is STOPPED for every ticket. Emails are still logged, but nothing is classified, escalated or chased until you resume.' : 'The agent is running on all tickets except those paused individually. Stopping halts triage, diagnostics, ISP emails and chasers immediately.',
      killBox: 'display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between; padding: 16px 20px; border-radius: 14px; border: 1px solid ' + (st.killed ? 'var(--critical)' : 'var(--border)') + '; background: ' + (st.killed ? 'var(--critical-bg)' : 'var(--surface-100)') + ';',
      toggleKill: function () { self.setState({ killed: !self.state.killed }); },
      connText: conn[0], connCls: conn[1],
      testConn: function () { self.setState({ conn: 'ok' }); },
      conf: (st.conf / 100).toFixed(2), confVal: st.conf,
      setConf: function (e) { self.setState({ conf: +e.target.value }); },
      fallback: st.fb.map(function (f, i) { return { ini: f[0], email: f[1], role: f[2], remove: function () { self.setState({ fb: self.state.fb.filter(function (_, j) { return j !== i; }) }); } }; }),
      addFallback: function () { self.setState({ fb: self.state.fb.concat([['NE', 'new.engineer@kazyon.com', 'Added just now']]) }); }
    };
  }
}
</script>
```
