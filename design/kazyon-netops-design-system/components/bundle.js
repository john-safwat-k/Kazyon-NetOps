/* @ds-bundle: {"format":4,"namespace":"KzNet","components":[{"name":"Button"},{"name":"Badge"},{"name":"IspBadge"},{"name":"StatusPill"},{"name":"SlaTimer"},{"name":"KpiCard"},{"name":"TicketCard"},{"name":"HealthBar"},{"name":"BarChart"},{"name":"AppShell"},{"name":"DashboardScreen"},{"name":"KanbanBoard"}]} */
(function () {
  var React = window.React;
  var h = React.createElement;
  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(' '); }

  /* ---------- Icons (24px, 1.75 stroke) ---------- */
  var P = {
    dashboard: 'M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z',
    board: 'M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z',
    list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
    replication: 'M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5',
    alert: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
    mail: 'M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM3 7l9 6 9-6',
    terminal: 'M4 17l6-6-6-6M12 19h8',
    store: 'M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9h18M9 20v-6h6v6',
    users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
    clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
    ticket: 'M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v3a2 2 0 0 0 0 4v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a2 2 0 0 0 0-4zM13 5v2M13 17v2M13 11v2',
    bot: 'M12 8V4H8M4 8h16v12H4zM2 14h2M20 14h2M9 13v2M15 13v2',
    pause: 'M10 4H6v16h4zM18 4h-4v16h4z',
    plus: 'M12 5v14M5 12h14',
    filter: 'M22 3H2l8 9.5V19l4 2v-8.5z',
    download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
    play: 'M6 4l14 8-14 8z',
    bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
    chevron: 'M6 9l6 6 6-6',
    sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
    x: 'M18 6L6 18M6 6l12 12'
  };
  function Icon(props) {
    return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true', width: props.size || 20, height: props.size || 20 },
      h('path', { d: P[props.name] || '' }));
  }

  /* ---------- Atoms ---------- */
  function Button(props) {
    var variant = props.variant || 'secondary';
    var rest = {};
    for (var k in props) if (['variant', 'size', 'icon', 'children', 'className'].indexOf(k) < 0) rest[k] = props[k];
    rest.className = cx('kz-btn', 'kz-btn-' + variant, props.size === 'sm' && 'kz-btn-sm', props.className);
    return h('button', rest, props.icon ? h(Icon, { name: props.icon }) : null, props.children);
  }

  function Badge(props) {
    return h('span', { className: cx('kz-badge', 'kz-badge-' + (props.tone || 'neutral')) }, props.children);
  }

  function IspBadge(props) {
    var isp = (props.isp || 'NOOR').toUpperCase();
    return h('span', { className: cx('kz-isp', 'kz-isp-' + isp) }, h('i', null, isp.charAt(0)), isp,
      props.caseRef ? h('span', { className: 'kz-mono kz-muted', style: { fontWeight: 500, letterSpacing: 0 } }, '#' + props.caseRef) : null);
  }

  function StatusPill(props) {
    var s = props.state || 'up';
    var word = { up: 'UP', down: 'DOWN', hub: 'BACKUP', skip: 'SKIPPED' }[s];
    return h('span', { className: cx('kz-pill', 'kz-pill-' + s), title: props.title }, h('b', null, props.label), ' ', word);
  }

  function fmt(min) {
    var m = Math.abs(Math.round(min)); var hh = Math.floor(m / 60), mm = m % 60;
    return (hh ? hh + 'h ' : '') + (mm < 10 && hh ? '0' : '') + mm + 'm';
  }
  function SlaTimer(props) {
    var total = props.totalMinutes || 120, left = props.minutesLeft;
    var state = left < 0 ? 'over' : left / total < 0.25 ? 'risk' : 'ok';
    var pct = Math.max(0, Math.min(100, (1 - left / total) * 100));
    var txt = left < 0 ? 'Overdue ' + fmt(left) : fmt(left) + ' left';
    return h('span', { className: cx('kz-sla', 'kz-sla-' + state) },
      h(Icon, { name: 'clock', size: 14 }),
      props.label ? h('span', { className: 'kz-muted', style: { fontWeight: 500 } }, props.label) : null,
      h('span', { className: 'kz-sla-track' }, h('span', { className: 'kz-sla-fill', style: { width: pct + '%', display: 'block' } })),
      h('span', { className: 'kz-num' }, txt));
  }

  /* ---------- Molecules ---------- */
  function KpiCard(props) {
    var tone = props.tone || 'default';
    return h('div', { className: cx('kz-card', 'kz-kpi', tone !== 'default' && 'kz-kpi-' + tone) },
      h('div', { className: 'kz-kpi-top' },
        h('span', { className: 'kz-kpi-label' }, props.label),
        h('span', { className: 'kz-kpi-ic' }, h(Icon, { name: props.icon || 'ticket' }))),
      h('div', { className: 'kz-kpi-val' }, props.value),
      h('div', { className: 'kz-kpi-ft' },
        props.delta ? h('span', { className: props.delta.charAt(0) === '+' ? 'kz-delta-up' : 'kz-delta-down' }, props.delta) : null,
        props.hint));
  }

  var PRIO = { CRITICAL: 'critical', HIGH: 'warning', MEDIUM: 'brand', LOW: 'neutral' };
  function TicketCard(props) {
    var t = props.ticket || {};
    return h('div', { className: 'kz-tcard' },
      h('div', { className: 'kz-tcard-top' },
        h('span', { className: 'kz-tcard-id' }, t.id),
        h(Badge, { tone: PRIO[t.priority] || 'neutral' }, t.priority)),
      h('p', { className: 'kz-tcard-title' }, t.branch),
      h('div', { className: 'kz-tcard-meta' }, t.region, t.failure ? ' · ' + t.failure : ''),
      h('div', { className: 'kz-row', style: { gap: 6 } }, h(IspBadge, { isp: t.isp, caseRef: t.caseRef })),
      t.checks ? h('div', { className: 'kz-tcard-pills' }, t.checks.map(function (c, i) { return h(StatusPill, { key: i, label: c[0], state: c[1] }); })) : null,
      h('div', { className: 'kz-tcard-ft' },
        t.sla ? h(SlaTimer, { minutesLeft: t.sla[0], totalMinutes: t.sla[1] }) : h('span', { className: 'kz-tcard-meta' }, t.note || ''),
        h('span', { className: cx('kz-ai', t.aiPaused && 'kz-ai-paused') }, h(Icon, { name: t.aiPaused ? 'pause' : 'bot', size: 14 }), t.aiPaused ? 'AI paused' : 'AI active')));
  }

  function HealthBar(props) {
    return h('div', { className: 'kz-health', role: 'status' }, (props.services || []).map(function (s, i) {
      var st = s.state || 'ok';
      return h('div', { key: i, className: cx('kz-health-item', 'kz-health-' + st) },
        h('span', { className: 'kz-health-dot' }),
        h('div', { style: { minWidth: 0 } }, h('div', { className: 'kz-health-name' }, s.name), h('div', { className: 'kz-health-detail' }, s.detail)),
        h('span', { className: 'kz-health-state' }, { ok: 'Healthy', degraded: 'Degraded', down: 'Down' }[st]));
    }));
  }

  function BarChart(props) {
    var data = props.data || [];
    var max = props.max || Math.max.apply(null, data.map(function (d) { return d.value; })) || 1;
    var st = React.useState(null), tip = st[0], setTip = st[1];
    var ref = React.useRef(null);
    return h('div', { className: 'kz-bars', ref: ref, onMouseLeave: function () { setTip(null); } },
      data.map(function (d, i) {
        return h('div', { key: i, className: 'kz-bar-row', tabIndex: 0, 'aria-label': d.label + ': ' + d.value + (props.unit || ''),
          onMouseMove: function (e) { var r = ref.current.getBoundingClientRect(); setTip({ x: e.clientX - r.left, y: e.currentTarget.offsetTop - 4, d: d }); } },
          h('span', { className: 'kz-bar-label' }, d.label),
          h('span', { className: 'kz-bar-track' }, h('span', { className: 'kz-bar-fill', style: { width: (d.value / max * 100) + '%', display: 'block' } })),
          h('span', { className: 'kz-bar-val' }, d.value + (props.unit || '')));
      }),
      tip ? h('div', { className: 'kz-tip', style: { left: tip.x, top: tip.y } }, h('b', null, tip.d.label), ' · ', tip.d.value + (props.unit || ''), tip.d.hint ? ' · ' + tip.d.hint : '') : null);
  }

  /* ---------- Shell ---------- */
  var NAV = [
    ['Operate', [['dashboard', 'Dashboard'], ['board', 'Kanban Board'], ['list', 'Tickets List'], ['alert', 'Human Review', '4'], ['replication', 'Replication Monitor', '12'], ['mail', 'Mailbox & Triage']]],
    ['Tools', [['terminal', 'Diagnostics Sandbox'], ['store', 'Branches & ISPs']]],
    ['Admin', [['users', 'Users & Roles'], ['settings', 'AI & SLA Settings']]]
  ];
  function AppShell(props) {
    var active = props.active || 'Dashboard';
    var dark = props.theme === 'dark';
    return h('div', { className: 'kz kz-shell', style: props.style, 'data-theme': props.theme || undefined },
      h('aside', { className: 'kz-side' },
        h('div', { className: 'kz-brand' }, h('span', { className: 'kz-logo' }, 'K'), h('div', null, h('b', null, 'Kazyon NetOps'), h('span', null, 'IT Network Support Agent'))),
        NAV.map(function (sec) {
          return h(React.Fragment, { key: sec[0] },
            h('div', { className: 'kz-nav-sec' }, sec[0]),
            sec[1].map(function (n) {
              var href = props.hrefs && props.hrefs[n[1]];
              return h('a', { key: n[1], href: href || '#', 'aria-current': n[1] === active ? 'page' : undefined, className: cx('kz-nav', n[1] === active && 'kz-nav-on'), onClick: href ? undefined : function (e) { e.preventDefault(); } },
                h(Icon, { name: n[0] }), n[1],
                n[2] ? h('span', { className: cx('kz-nav-count', n[0] === 'alert' && 'kz-nav-count-alert') }, n[2]) : null);
            }));
        })),
      h('div', { className: 'kz-main' },
        h('header', { className: 'kz-top' },
          h('div', { className: 'kz-search' }, h(Icon, { name: 'search' }), 'Search branch, ticket, circuit ID…'),
          h('span', { style: { flex: 1 } }),
          h('span', { className: 'kz-live' }, 'Live'),
          h('span', { className: 'kz-env' }, props.env || 'PROD :8084'),
          props.onToggleTheme ? h(Button, { variant: 'ghost', icon: dark ? 'sun' : 'moon', 'aria-label': dark ? 'Switch to light mode' : 'Switch to dark mode', 'aria-pressed': dark, onClick: props.onToggleTheme }) : null,
          h(Button, { variant: 'ghost', icon: 'bell', 'aria-label': 'Notifications' }),
          h('span', { className: 'kz-avatar' }, props.initials || 'JS')),
        h('main', { className: 'kz-page' }, props.children)));
  }

  /* ---------- Sample data ---------- */
  var TICKETS = [
    { id: 'NET-1058', priority: 'CRITICAL', branch: '2009-Kafr Nasar', region: 'Giza', failure: 'Full outage', isp: 'NOOR', caseRef: '244010', checks: [['IP1', 'down'], ['IP2', 'skip']], sla: [-34, 120], status: 'Escalated · Welcome', col: 3 },
    { id: 'NET-1057', priority: 'HIGH', branch: '1173-Ghmrawy', region: 'Cairo', failure: 'Local loop down (4G)', isp: 'ORANGE', caseRef: '1-1312322942540', checks: [['IP1', 'up'], ['IP2', 'down'], ['4G', 'hub']], sla: [52, 300], status: 'With ISP', col: 4 },
    { id: 'NET-1055', priority: 'HIGH', branch: '1254-El Mansheya', region: 'Behera', failure: 'Full outage', isp: 'WE', caseRef: '8407532', checks: [['IP1', 'down'], ['IP2', 'skip']], sla: [18, 120], status: 'Escalated · Welcome', col: 3 },
    { id: 'NET-1054', priority: 'MEDIUM', branch: '1450-Soliman Metwaly', region: 'Assyut', note: 'Replication: Not Updated', isp: 'NOOR', status: 'Awaiting Regional IT', col: 0 },
    { id: 'NET-1053', priority: 'MEDIUM', branch: '1088-Gamal Salem', region: 'New October', note: 'Replication: Not Updated', isp: 'ORANGE', status: 'Awaiting Regional IT', col: 0 },
    { id: 'NET-1052', priority: 'HIGH', branch: '1312-Damanhour 3', region: 'Behera', failure: 'Router photo check', isp: 'NOOR', note: 'Vision: analysing photo', status: 'Diagnosing', col: 1 },
    { id: 'NET-1051', priority: 'LOW', branch: '1201-Hadayek El Ahram', region: 'Giza', failure: 'Internal switch', isp: 'NOOR', checks: [['IP1', 'up'], ['IP2', 'down']], note: 'Returned to GITSupport', status: 'Internal LAN', col: 2 },
    { id: 'NET-1049', priority: 'CRITICAL', branch: '1005-Tosson', region: 'Behera', failure: 'Quota consumed', isp: 'WE', caseRef: '8400809', aiPaused: true, note: 'Engineer notified', status: 'Needs review', col: 6 },
    { id: 'NET-1047', priority: 'MEDIUM', branch: '1366-Nasr City 7', region: 'Cairo', failure: 'Full outage', isp: 'NOOR', caseRef: '243881', checks: [['IP1', 'up'], ['IP2', 'up']], note: 'Re-pinging after ISP closure', status: 'Verifying', col: 5 },
    { id: 'NET-1046', priority: 'HIGH', branch: '1420-Sheikh Zayed 2', region: 'New October', failure: 'Site contact unreachable', isp: 'NOOR', caseRef: '243860', sla: [210, 300], status: 'With ISP', col: 4 },
    { id: 'NET-1044', priority: 'LOW', branch: '1099-Kafr El Dawar', region: 'Behera', failure: 'Cables', isp: 'NOOR', checks: [['IP1', 'up'], ['IP2', 'up']], note: 'Closed 08:14', status: 'Resolved', col: 7 },
    { id: 'NET-1041', priority: 'HIGH', branch: '1510-Abnoub', region: 'Assyut', failure: 'MSAN migration', isp: 'WE', aiPaused: true, note: 'Engineer notified', status: 'Needs review', col: 6 }
  ];

  /* ---------- Dashboard (Page 2) ---------- */
  function DashboardScreen(props) {
    var rs = React.useState('7d'), range = rs[0], setRange = rs[1];
    var watch = TICKETS.filter(function (t) { return t.sla; }).sort(function (a, b) { return a.sla[0] - b.sla[0]; });
    function seg(v, l) { return h('button', { className: range === v ? 'on' : '', onClick: function () { setRange(v); } }, l); }
    return h(AppShell, { active: 'Dashboard', style: props.style },
      h('div', { className: 'kz-page-hd' },
        h('div', null, h('h1', null, 'Executive & SLA Dashboard'), h('p', null, '1,150 branches · NOOR, ORANGE, WE · Updated 11:24 Cairo time')),
        h('div', { className: 'kz-row' },
          h('div', { className: 'kz-seg', role: 'group', 'aria-label': 'Time range' }, seg('24h', 'Today'), seg('7d', '7 days'), seg('30d', '30 days')),
          h(Button, { variant: 'secondary', icon: 'download' }, 'Export'),
          h(Button, { variant: 'primary', icon: 'plus' }, 'New ticket'))),
      h(HealthBar, { services: [
        { name: 'vLLM · Gemma 4 26B', detail: '10.100.109.9:8002 · 412 ms', state: 'ok' },
        { name: 'IMAP / SMTP Mailbox', detail: 'Last poll 14 s ago', state: 'ok' },
        { name: 'PostgreSQL 16', detail: ':5434 · 18 conn', state: 'ok' },
        { name: 'Redis 7', detail: ':6384 · queue depth 9', state: 'degraded' }] }),
      h('div', { className: 'kz-grid-kpi' },
        h(KpiCard, { label: 'Open tickets', value: 37, icon: 'ticket', delta: '+6', hint: 'vs. yesterday' }),
        h(KpiCard, { label: 'Needs human review', value: 4, icon: 'alert', tone: 'critical', hint: 'Quota, MSAN, unknown mail' }),
        h(KpiCard, { label: 'Overdue 2h welcome', value: 3, icon: 'mail', tone: 'warning', hint: 'ISP has not opened a case' }),
        h(KpiCard, { label: 'Overdue 4–6h update', value: 5, icon: 'clock', tone: 'warning', hint: 'Chasers sent automatically' }),
        h(KpiCard, { label: 'Not updated today', value: 12, icon: 'replication', delta: '-3', hint: 'Replication Dashboard 09:00' })),
      h('div', { className: 'kz-grid-3' },
        h('div', { className: 'kz-card' }, h('div', { className: 'kz-card-hd' }, h('div', null, h('h2', null, 'Outages by ISP'), h('p', null, 'Tickets opened, last 7 days'))),
          h('div', { className: 'kz-card-bd' }, h(BarChart, { data: [{ label: 'NOOR', value: 64, hint: '906 stores' }, { label: 'ORANGE', value: 21, hint: '181 stores' }, { label: 'WE', value: 9, hint: '63 stores' }] }))),
        h('div', { className: 'kz-card' }, h('div', { className: 'kz-card-hd' }, h('div', null, h('h2', null, 'MTTR by ISP'), h('p', null, 'Mean hours, escalation → verified fix'))),
          h('div', { className: 'kz-card-bd' }, h(BarChart, { unit: 'h', data: [{ label: 'NOOR', value: 5.8 }, { label: 'ORANGE', value: 7.2 }, { label: 'WE', value: 9.4 }] }))),
        h('div', { className: 'kz-card' }, h('div', { className: 'kz-card-hd' }, h('div', null, h('h2', null, 'Outages by failure type'), h('p', null, 'Diagnosis from dual-ping & traceroute'))),
          h('div', { className: 'kz-card-bd' }, h(BarChart, { data: [{ label: 'Full outage', value: 41 }, { label: '4G / LL down', value: 23 }, { label: 'Internal switch', value: 19 }, { label: 'Cables', value: 11 }] })))),
      h('div', { className: 'kz-grid-main' },
        h('div', { className: 'kz-card', style: { overflow: 'hidden' } },
          h('div', { className: 'kz-card-hd', style: { paddingBottom: 12 } }, h('div', null, h('h2', null, 'SLA watchlist'), h('p', null, 'Tickets waiting on an ISP, most urgent first')), h(Button, { variant: 'ghost', size: 'sm' }, 'Open board')),
          h('table', { className: 'kz-table' },
            h('thead', null, h('tr', null, ['Ticket', 'Branch', 'ISP', 'Checks', 'Stage', 'SLA'].map(function (c) { return h('th', { key: c }, c); }))),
            h('tbody', null, watch.map(function (t) {
              return h('tr', { key: t.id },
                h('td', null, h('span', { className: 'kz-tcard-id' }, t.id)),
                h('td', null, h('div', { className: 'kz-nowrap', style: { fontWeight: 600 } }, t.branch), h('div', { className: 'kz-tcard-meta' }, t.region + ' · ' + t.failure)),
                h('td', null, h(IspBadge, { isp: t.isp })),
                h('td', null, h('div', { className: 'kz-tcard-pills' }, (t.checks || []).map(function (c, i) { return h(StatusPill, { key: i, label: c[0], state: c[1] }); }))),
                h('td', null, h(Badge, { tone: t.sla[0] < 0 ? 'critical' : 'brand' }, t.status)),
                h('td', { className: 'kz-nowrap' }, h(SlaTimer, { minutesLeft: t.sla[0], totalMinutes: t.sla[1] })));
            })))),
        h('div', { className: 'kz-card' },
          h('div', { className: 'kz-card-hd' }, h('div', null, h('h2', null, 'Outages by region'), h('p', null, 'Open + resolved, last 7 days'))),
          h('div', { className: 'kz-card-bd' }, h(BarChart, { data: [{ label: 'Behera', value: 31, hint: '350 stores' }, { label: 'Cairo', value: 22, hint: '223 stores' }, { label: 'New October', value: 18, hint: '212 stores' }, { label: 'Assyut', value: 15, hint: '209 stores' }, { label: 'Giza', value: 8, hint: '156 stores' }] })))));
  }

  /* ---------- Kanban (Page 3) ---------- */
  var COLS = [['Awaiting Regional IT', ''], ['New & Diagnosing', ''], ['Branch / Internal Action', ''], ['Escalated to ISP · 2h', 'isp'], ['With ISP · 4–6h loop', 'isp'], ['Verifying Fix', ''], ['Needs Human Review', 'human'], ['Resolved / Closed', 'done']];
  function KanbanBoard(props) {
    return h(AppShell, { active: 'Kanban Board', style: props.style },
      h('div', { className: 'kz-page-hd' },
        h('div', null, h('h1', null, 'Ticket Board'), h('p', null, 'Drag a card to change its status. The AI agent keeps working unless paused.')),
        h('div', { className: 'kz-row' }, h(Button, { variant: 'secondary', icon: 'download' }, 'Export'), h(Button, { variant: 'primary', icon: 'plus' }, 'Create manual ticket'))),
      h('div', { className: 'kz-filters' },
        h('span', { className: 'kz-chip kz-chip-on' }, h(Icon, { name: 'filter' }), 'All ISPs'),
        h('span', { className: 'kz-chip' }, 'Region', h(Icon, { name: 'chevron' })),
        h('span', { className: 'kz-chip' }, 'Trigger', h(Icon, { name: 'chevron' })),
        h('span', { className: 'kz-chip' }, 'Priority', h(Icon, { name: 'chevron' })),
        h('span', { className: 'kz-chip' }, 'AI paused only')),
      h('div', { className: 'kz-board' }, COLS.map(function (c, i) {
        var items = TICKETS.filter(function (t) { return t.col === i; });
        return h('section', { key: i, className: cx('kz-col', c[1] && 'kz-col-' + c[1]) },
          h('div', { className: 'kz-col-hd' }, h('span', { className: 'kz-col-bar' }), h('b', null, c[0]), h('span', null, items.length)),
          items.map(function (t) { return h(TicketCard, { key: t.id, ticket: t }); }));
      })));
  }

  window.KzNet = Object.assign(window.KzNet || {}, {
    Icon: Icon, Button: Button, Badge: Badge, IspBadge: IspBadge, StatusPill: StatusPill, SlaTimer: SlaTimer,
    KpiCard: KpiCard, TicketCard: TicketCard, HealthBar: HealthBar, BarChart: BarChart,
    AppShell: AppShell, DashboardScreen: DashboardScreen, KanbanBoard: KanbanBoard, sampleTickets: TICKETS
  });
})();
