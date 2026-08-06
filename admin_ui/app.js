(() => {
  "use strict";

  const state = { admin: null, csrf: null, page: 1, query: "", status: "", detailItem: null };
  const $ = (id) => document.getElementById(id);
  const modal = () => bootstrap.Modal.getOrCreateInstance($("action-modal"));

  const labels = {
    dashboard: "Рабочий стол",
    "performer-moderation": "Модерация исполнителей",
    "orders-attention": "Заказы требуют внимания",
    cases: "Жалобы и споры",
    finance: "Финансовые задачи",
    deletions: "Удаление аккаунтов",
    performers: "Исполнители",
    invitations: "Приглашения",
    orders: "Все заказы",
    customers: "Заказчики",
    services: "Услуги и правила",
    settings: "Бизнес-настройки",
    files: "Файлы",
    audit: "Аудит действий",
    notifications: "Уведомления",
    payments: "Платежи",
    refunds: "Возвраты",
    support: "Поддержка",
    complaints: "Жалобы",
    disputes: "Споры",
    deletions: "Удаление аккаунтов",
  };

  const secondaryResources = {
    customers: { fields: ["id", "full_name", "phone", "status", "telegram_username", "created_at"] },
    performers: { fields: ["id", "full_name", "telegram_id", "status", "is_accepting_orders", "updated_at"] },
    invitations: { fields: ["id", "telegram_id", "status", "expires_at", "accepted_performer_id"] },
    orders: { fields: ["id", "service_name", "status", "customer_id", "selected_performer_id", "start_at", "total_amount", "requires_admin_attention"] },
    services: { fields: ["id", "code", "name", "is_active", "schedule_policy", "price_type"] },
    settings: { fields: ["id", "key", "value_type", "value", "updated_at"] },
    files: { fields: ["id", "original_name", "mime_type", "size_bytes", "status", "created_at"] },
    audit: { fields: ["id", "action", "entity_type", "entity_id", "reason", "created_at"] },
    notifications: { fields: ["id", "type", "entity_type", "entity_id", "status", "attempts", "admin_retry_count", "last_error", "read_at", "created_at"] },
    violations: { fields: ["id", "account_type", "violation_type", "action", "status", "reason", "created_at"] },
    support: { fields: ["id", "type", "direction", "status", "order_id", "created_at"] },
    complaints: { fields: ["id", "category", "direction", "status", "order_id", "created_at"] },
    disputes: { fields: ["id", "status", "order_id", "customer_id", "created_at"] },
    deletions: { fields: ["id", "status", "customer_id", "performer_id", "created_at"] },
    cities: { fields: ["id", "name", "slug", "timezone", "is_active"] },
    districts: { fields: ["id", "city_id", "name", "is_active"] },
    "service-categories": { fields: ["id", "code", "name", "care_object_type", "max_objects_per_order", "is_active"] },
    "service-options": { fields: ["id", "service_id", "code", "name", "value_type", "is_required", "is_active"] },
    multipliers: { fields: ["id", "category_id", "objects_count", "multiplier", "is_active"] },
    "legal-documents": { fields: ["id", "document_type", "version", "content_url", "is_active", "published_at"] },
  };
  const detailResources = new Set([...Object.keys(secondaryResources), "payments", "refunds", "reports", "support", "complaints", "disputes", "deletions"]);

  const groups = [
    ["Рабочее место", [["dashboard", "Рабочий стол"], ["performer-moderation", "Модерация исполнителей"], ["orders-attention", "Проблемные заказы"], ["cases", "Жалобы и споры"], ["finance", "Финансы"], ["deletions", "Удаления"]]],
    ["Управление", [["performers", "Исполнители"], ["invitations", "Приглашения"], ["orders", "Все заказы"], ["services", "Услуги и правила"], ["settings", "Настройки бизнеса"], ["cities", "Города и районы"], ["service-categories", "Категории и опции"], ["multipliers", "Коэффициенты"], ["legal-documents", "Юридические документы"]]],
    ["Система", [["customers", "Поиск заказчиков"], ["support", "Поддержка"], ["complaints", "Жалобы"], ["disputes", "Споры"], ["deletions", "Удаления аккаунтов"], ["files", "Файлы"], ["audit", "Аудит действий"], ["notifications", "Уведомления"], ["violations", "Нарушения"]]],
  ];

  const queueMeta = {
    "performer-moderation": { icon: "👤", description: "Профили и услуги, ожидающие решения" },
    "orders-attention": { icon: "📦", description: "Заказы, которые backend передал оператору" },
    cases: { icon: "⚖️", description: "Открытые обращения, жалобы и споры" },
    finance: { icon: "₽", description: "Платежи, возвраты и выплаты с риском" },
    deletions: { icon: "🗑️", description: "Запросы на удаление с блокирующими условиями" },
  };

  function esc(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
  }
  function value(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "boolean") return value ? "Да" : "Нет";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }
  function fieldLabel(key) {
    return String(key).replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }
  function statusBadge(status) {
    const normalized = String(status || "unknown").toLowerCase();
    const tone = ["open", "failed", "blocked", "profile_pending", "invited", "pending"].includes(normalized) ? "danger" : ["in_progress", "waiting_payment", "ready"].includes(normalized) ? "warning" : ["completed", "succeeded", "active", "approved", "resolved"].includes(normalized) ? "success" : "secondary";
    return `<span class="badge text-bg-${tone}">${esc(status || "—")}</span>`;
  }
  function showLogin() { state.admin = null; state.csrf = null; $("app-view").classList.add("d-none"); $("login-view").classList.remove("d-none"); }
  function showApp() { $("login-view").classList.add("d-none"); $("app-view").classList.remove("d-none"); $("admin-name").textContent = state.admin.full_name || state.admin.email; renderNav(); }
  function flash(message, type = "success") { const box = $("flash"); box.className = `alert alert-${type}`; box.textContent = message; box.classList.remove("d-none"); window.setTimeout(() => box.classList.add("d-none"), 5000); }

  async function api(path, options = {}) {
    const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
    const response = await fetch(`/admin/ui${path}`, { credentials: "same-origin", ...options, headers });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (response.status === 401) { showLogin(); throw new Error("Сессия истекла"); }
    if (!response.ok) throw new Error(data?.error?.message || data?.detail || "Операция не выполнена");
    return data;
  }
  function csrfHeaders() { return { "X-CSRF-Token": state.csrf }; }
  function route() { const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean); return { key: parts[0] || "dashboard", id: parts[1] || null }; }
  function navigate(hash) { location.hash = hash; }

  function renderNav() {
    const nav = $("nav-items"); nav.innerHTML = "";
    const current = route().key;
    for (const [group, items] of groups) {
      const heading = document.createElement("div"); heading.className = "nav-heading"; heading.textContent = group; nav.append(heading);
      for (const [key, title] of items) {
        const link = document.createElement("a"); link.className = `nav-link ${current === key ? "active" : ""}`; link.href = `#/${key}`; link.textContent = title;
        if (current === key) link.setAttribute("aria-current", "page");
        link.onclick = () => bootstrap.Offcanvas.getInstance($("sidebar"))?.hide();
        nav.append(link);
      }
    }
  }

  async function renderRoute() {
    renderNav();
    const current = route();
    if (current.key === "dashboard") return renderDashboard();
    if (queueMeta[current.key]) return current.id ? renderDetail("orders", current.id) : renderQueue(current.key);
    if (secondaryResources[current.key]) return current.id ? renderDetail(current.key, current.id) : renderSecondaryList(current.key);
    if (detailResources.has(current.key) && current.id) return renderDetail(current.key, current.id);
    return renderDashboard();
  }

  function pageHeader(title, subtitle, actions = "") {
    return `<div class="page-header"><div><div class="eyebrow">OPERATIONS</div><h1 class="h3 mb-1">${esc(title)}</h1><p class="text-secondary mb-0">${esc(subtitle)}</p></div><div class="d-flex gap-2">${actions}</div></div>`;
  }

  async function renderDashboard() {
    $("page-content").innerHTML = `${pageHeader("Рабочий стол", "Главные задачи администратора на сейчас", '<button id="refresh-dashboard" class="btn btn-outline-secondary">Обновить</button>')}<div id="dashboard-error" class="alert alert-danger d-none"></div><div id="metrics" class="row g-3 mb-4"></div><div id="queue-grid" class="row g-3"></div>`;
    $("refresh-dashboard").onclick = renderDashboard;
    try {
      const data = await api("/dashboard");
      const metricOrder = [["performer_moderation", "Модерация исполнителей", "performer-moderation"], ["orders_attention", "Проблемные заказы", "orders-attention"], ["open_disputes", "Открытые споры", "cases"], ["open_complaints", "Открытые жалобы", "cases"], ["finance", "Финансовые задачи", "finance"], ["unread_notifications", "Непрочитанные уведомления", "notifications"], ["deletions", "Удаления", "deletions"]];
      $("metrics").innerHTML = metricOrder.map(([key, title, target]) => `<a class="col-sm-6 col-xl-2 text-decoration-none" href="#/${target}"><div class="metric-card card h-100"><div class="card-body"><div class="metric-label">${esc(title)}</div><div class="metric-value">${esc(data.metrics[key] ?? 0)}</div><div class="small text-primary">Открыть очередь →</div></div></div></a>`).join("");
      $("queue-grid").innerHTML = Object.entries(queueMeta).map(([key, meta]) => renderQueuePreview(key, meta, data.queues[key] || { items: [], total: 0 })).join("");
      bindQueueLinks();
    } catch (error) { $("dashboard-error").textContent = error.message; $("dashboard-error").classList.remove("d-none"); }
  }

  function renderQueuePreview(key, meta, queue) {
    const items = queue.items || [];
    return `<div class="col-12 col-xl-6"><section class="queue-panel card h-100"><div class="card-body"><div class="d-flex justify-content-between align-items-start mb-3"><div><span class="queue-icon">${meta.icon}</span><h2 class="h5 d-inline ms-2">${esc(queueTitle(key))}</h2><p class="text-secondary small mb-0 mt-1">${esc(meta.description)}</p></div><a class="btn btn-sm btn-outline-primary" href="#/${key}">Все (${esc(queue.total ?? items.length)})</a></div>${items.length ? `<div class="queue-items">${items.slice(0, 5).map((item) => renderQueueItem(item)).join("")}</div>` : '<div class="empty-state compact">Очередь пуста</div>'}</div></section></div>`;
  }
  function queueTitle(key) { return queueMeta[key] ? ({ "performer-moderation": "Модерация исполнителей", "orders-attention": "Проблемные заказы", cases: "Жалобы и споры", finance: "Финансовые задачи", deletions: "Удаления аккаунтов" }[key]) : key; }
  function renderQueueItem(item) { return `<a class="queue-item" href="#/${esc(item.resource)}/${esc(item.id)}"><div class="queue-item-main"><strong>${esc(item.title)}</strong><span class="small text-secondary">${esc(item.subtitle || item.resource)}</span></div><div class="text-end">${statusBadge(item.status)}<div class="small text-secondary mt-1">Открыть →</div></div></a>`; }
  function bindQueueLinks() { $("queue-grid").querySelectorAll("a").forEach((link) => { link.onclick = () => { renderNav(); }; }); }

  async function renderQueue(queue) {
    $("page-content").innerHTML = `${pageHeader(queueTitle(queue), queueMeta[queue].description, '<button id="refresh-queue" class="btn btn-outline-secondary">Обновить</button>')}<div id="queue-error" class="alert alert-danger d-none"></div><div id="queue-list" class="queue-list"></div>`;
    $("refresh-queue").onclick = () => renderQueue(queue);
    try { const data = await api(`/work-queues/${queue}?limit=100`); $("queue-list").innerHTML = data.items.length ? data.items.map((item) => `<div class="queue-row card mb-2"><div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-3">${renderQueueItem(item)}<a class="btn btn-primary btn-sm" href="#/${item.resource}/${item.id}">Разобрать</a></div></div>`).join("") : '<div class="empty-state">Нет задач — всё спокойно</div>'; } catch (error) { $("queue-error").textContent = error.message; $("queue-error").classList.remove("d-none"); }
  }

  async function renderSecondaryList(key) {
    const resource = secondaryResources[key];
    const createButton = key === "invitations" ? '<button id="create-invitation" class="btn btn-primary">Пригласить исполнителя</button>' : "";
    $("page-content").innerHTML = `${pageHeader(labels[key], "Вспомогательный поиск и управление", createButton)}<form id="filters" class="toolbar card card-body mb-3"><div class="row g-2"><div class="col-md-6"><input id="query" class="form-control" placeholder="Поиск по имени, ID или тексту"></div><div class="col-md-3"><input id="status" class="form-control" placeholder="Статус"></div><div class="col-md-3 d-flex gap-2"><button class="btn btn-outline-primary" type="submit">Найти</button><button id="refresh" class="btn btn-outline-secondary" type="button">Обновить</button></div></div></form><div id="list-error" class="alert alert-danger d-none"></div><div class="card"><div class="table-responsive"><table class="table table-hover mb-0"><thead id="table-head"></thead><tbody id="table-body"></tbody></table></div><div class="card-footer d-flex justify-content-between"><span id="count" class="text-secondary small"></span><div><button id="prev" class="btn btn-sm btn-outline-secondary me-2">Назад</button><button id="next" class="btn btn-sm btn-outline-secondary">Далее</button></div></div></div>`;
    $("filters").onsubmit = (event) => { event.preventDefault(); state.query = $("query").value; state.status = $("status").value; state.page = 1; loadSecondaryList(key); };
    $("refresh").onclick = () => loadSecondaryList(key);
    $("prev").onclick = () => { if (state.page > 1) { state.page -= 1; loadSecondaryList(key); } };
    $("next").onclick = () => { state.page += 1; loadSecondaryList(key); };
    if (key === "invitations") $("create-invitation").onclick = openInvitationForm;
    await loadSecondaryList(key);
  }
  async function loadSecondaryList(key) {
    try {
      const page = await api(`/${key}?page=${state.page}&page_size=25&query=${encodeURIComponent(state.query)}&status=${encodeURIComponent(state.status)}`); const fields = secondaryResources[key].fields;
      $("table-head").innerHTML = `<tr>${fields.map((field) => `<th>${esc(fieldLabel(field))}</th>`).join("")}<th></th></tr>`;
      $("table-body").innerHTML = page.items.length ? page.items.map((item) => `<tr>${fields.map((field) => `<td>${field === "status" || field === "payout_status" ? statusBadge(item[field]) : esc(value(item[field]))}</td>`).join("")}<td class="text-end">${key === "notifications" ? `<button class="btn btn-sm btn-outline-primary mark-read" data-id="${esc(item.id)}">Прочитано</button>${["failed", "dead"].includes(item.status) ? `<button class="btn btn-sm btn-outline-warning retry-notification ms-1" data-id="${esc(item.id)}">Повторить</button>` : ""}` : `<a class="btn btn-sm btn-outline-primary" href="#/${key}/${item.id}">Открыть</a>`}</td></tr>`).join("") : `<tr><td colspan="${fields.length + 1}"><div class="empty-state compact">Нет данных</div></td></tr>`;
      $("table-body").querySelectorAll(".mark-read").forEach((button) => { button.onclick = async () => { try { await api("/notifications/read", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ ids: [button.dataset.id] }) }); await loadSecondaryList(key); } catch (error) { flash(error.message, "danger"); } }; });
      $("table-body").querySelectorAll(".retry-notification").forEach((button) => { button.onclick = async () => { try { await api(`/notifications/${button.dataset.id}/retry`, { method: "POST", headers: csrfHeaders() }); flash("Уведомление поставлено в очередь"); await loadSecondaryList(key); } catch (error) { flash(error.message, "danger"); } }; });
      $("count").textContent = `Показано ${page.items.length} из ${page.total}`; $("next").disabled = state.page * page.page_size >= page.total; $("prev").disabled = state.page === 1;
    } catch (error) { $("list-error").textContent = error.message; $("list-error").classList.remove("d-none"); }
  }

  async function renderDetail(key, id) {
    $("page-content").innerHTML = `${pageHeader(labels[key] || key, `Карточка ${id}`, `<a class="btn btn-outline-secondary" href="#/${key}">← Назад</a>`)}<div id="detail-error" class="alert alert-danger d-none"></div><div id="detail-card"></div><div id="related" class="row g-3 mt-1"></div>`;
    try { const data = await api(`/${key}/${id}`); state.detailItem = data.item; renderObjectCard(key, id, data.item); renderRelated(key, data.related || {}, id); } catch (error) { $("detail-error").textContent = error.message; $("detail-error").classList.remove("d-none"); }
  }
  function renderObjectCard(key, id, item) {
    const actions = renderActions(key, id, item);
    const entries = Object.entries(item).filter(([field]) => !["id", "password_hash", "storage_key"].includes(field));
    $("detail-card").innerHTML = `<section class="detail-card card"><div class="card-body"><div class="d-flex justify-content-between align-items-start gap-3 mb-4"><div><div class="eyebrow">${esc(labels[key] || key)}</div><h2 class="h4 mb-1">${esc(item.full_name || item.service_name || item.text?.slice(0, 100) || id)}</h2><div class="text-secondary small">ID: ${esc(id)}</div></div><div class="d-flex flex-wrap gap-2">${item.status ? statusBadge(item.status) : ""}${actions}</div></div><div class="row g-3">${entries.map(([field, fieldValue]) => `<div class="col-sm-6 col-xl-4"><div class="detail-label">${esc(fieldLabel(field))}</div><div class="detail-value text-break">${field === "status" || field === "payout_status" ? statusBadge(fieldValue) : esc(value(fieldValue))}</div></div>`).join("")}</div></div></section>`;
  }
  function renderRelated(parentKey, related, entityId) {
    const sections = [];
    if (parentKey === "performers") {
      sections.push(renderPerformerServices(related.services || [], entityId));
    }
    sections.push(...Object.entries(related)
      .filter(([name, rows]) => rows.length && !(parentKey === "performers" && name === "services"))
      .map(([name, rows]) => `<div class="col-12"><section class="card"><div class="card-header bg-white"><strong>${esc(fieldLabel(name))}</strong><span class="text-secondary small ms-2">${rows.length}</span></div><div class="table-responsive"><table class="table table-sm table-hover mb-0"><tbody>${rows.map((row) => `<tr>${Object.entries(row).filter(([field]) => field !== "id").slice(0, 7).map(([field, fieldValue]) => `<td><span class="text-secondary">${esc(fieldLabel(field))}:</span> ${field === "status" ? statusBadge(fieldValue) : esc(value(fieldValue))}</td>`).join("")}<td class="text-end">${relatedAction(parentKey, name, row)}</td></tr>`).join("")}</tbody></table></div></section></div>`));
    $("related").innerHTML = sections.filter(Boolean).join("");
    $("related").querySelectorAll("[data-related-action]").forEach((button) => { button.onclick = () => runAction(button.dataset.relatedAction, button.dataset.id, JSON.parse(button.dataset.item || "{}")); });
    $("related").querySelectorAll("[data-file-id]").forEach((button) => { button.onclick = async () => { try { const result = await api(`/files/${button.dataset.fileId}/download-url`); window.open(result.url, "_blank", "noopener"); } catch (error) { flash(error.message, "danger"); } }; });
    const addService = $("add-performer-service");
    if (addService) addService.onclick = () => openAddPerformerServiceForm(addService.dataset.performerId, related.services || []);
  }
  async function openAddPerformerServiceForm(performerId, assignedRows) {
    try {
      const page = await api("/services?page=1&page_size=100");
      const assigned = new Set(assignedRows.map((row) => row.service_id));
      const options = page.items.filter((item) => item.is_active && !assigned.has(item.id)).map((item) => ({ value: item.id, label: `${item.name} (${item.code})` }));
      if (!options.length) { flash("Нет доступных услуг для добавления", "warning"); return; }
      openForm("Добавить услугу исполнителю", [
        { name: "service_id", label: "Услуга", type: "select", options, required: true },
        { name: "admin_max_objects", label: "Лимит объектов", type: "number", value: "1", required: true },
        { name: "constraints", label: "Ограничения JSON", type: "textarea", value: "{}", required: true },
        { name: "comment", label: "Причина добавления", type: "textarea", required: true },
      ], async (form) => api(`/performers/${performerId}/services`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ service_id: form.service_id, admin_max_objects: Number(form.admin_max_objects), constraints: JSON.parse(form.constraints), comment: form.comment }) }));
    } catch (error) { flash(error.message, "danger"); }
  }
  function renderPerformerServices(rows, performerId) {
    const body = rows.length
      ? rows.map((row) => `<tr><td><div class="fw-semibold">${esc(row.service_name || row.service_code || row.service_id)}</div><div class="small text-secondary">${esc(row.service_code || row.service_id)}</div></td><td>${row.is_approved ? statusBadge(row.is_enabled ? "active" : "disabled") : statusBadge("pending")}</td><td>${esc(value(row.admin_max_objects))}</td><td>${esc(value(row.performer_max_objects))}</td><td class="text-break">${esc(value(row.constraints))}</td><td class="text-end text-nowrap">${performerServiceActions(row)}</td></tr>`).join("")
      : '<tr><td colspan="6" class="text-secondary">У исполнителя нет назначенных услуг.</td></tr>';
    const addButton = performerId ? `<button id="add-performer-service" data-performer-id="${esc(performerId)}" class="btn btn-sm btn-primary">Добавить услугу</button>` : "";
    return `<div class="col-12"><section class="card"><div class="card-header bg-white d-flex justify-content-between align-items-center"><strong>Услуги исполнителя</strong><div class="d-flex gap-2 align-items-center">${addButton}<span class="text-secondary small">${rows.length}</span></div></div><div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0"><thead><tr><th>Услуга</th><th>Статус</th><th>Лимит админа</th><th>Лимит исполнителя</th><th>Ограничения</th><th></th></tr></thead><tbody>${body}</tbody></table></div></section></div>`;
  }
  function performerServiceActions(row, performerId) {
    const actionData = `data-id="${esc(row.id)}" data-performer-id="${esc(performerId)}" data-service-id="${esc(row.service_id)}" data-item='${esc(JSON.stringify(row))}'`;
    if (!row.is_approved) return `<button class="btn btn-sm btn-outline-success" data-related-action="approve-service" ${actionData}>Одобрить</button>`;
    const toggle = row.is_enabled ? "disable-service" : "enable-service";
    const toggleLabel = row.is_enabled ? "Деактивировать" : "Активировать";
    return `<div class="d-flex gap-1 justify-content-end"><button class="btn btn-sm btn-outline-${row.is_enabled ? "warning" : "success"}" data-related-action="${toggle}" ${actionData}>${toggleLabel}</button><button class="btn btn-sm btn-outline-secondary" data-related-action="service-limits" ${actionData}>Лимит</button><button class="btn btn-sm btn-outline-danger" data-related-action="revoke-service" ${actionData}>Отозвать</button></div>`;
  }
  function relatedAction(parentKey, name, row) {
    if (parentKey === "performers" && name === "services") return performerServiceActions(row, row.performer_id);
    if (["order", "customer", "performer"].includes(name) && row.id) return `<a class="btn btn-sm btn-outline-primary" href="#/${name === "order" ? "orders" : name === "customer" ? "customers" : "performers"}/${esc(row.id)}">Открыть</a>`;
    if (["payments", "refunds", "reports"].includes(name) && row.id) return `<a class="btn btn-sm btn-outline-primary" href="#/${name}/${esc(row.id)}">Открыть</a>`;
    if (name === "files" && row.id) return `<button class="btn btn-sm btn-outline-primary" data-file-id="${esc(row.id)}">Открыть файл</button>`;
    return "";
  }

  function renderActions(key, id, item) {
    const actions = [];
    if (key === "performers" && ["invited", "profile_pending"].includes(item.status)) actions.push(["activate", "Активировать", "success"], ["reject", "Отклонить", "danger"]);
    if (key === "performers" && item.status === "active") actions.push([item.is_accepting_orders ? "pause" : "resume", item.is_accepting_orders ? "Поставить на паузу" : "Возобновить заказы", "outline-primary"], ["profile", "Профиль", "outline-secondary"], ["schedule", "Расписание", "outline-secondary"], ["calendar", "Исключение календаря", "outline-secondary"], ["block", "Заблокировать", "outline-danger"]);
    if (key === "performers" && item.status === "blocked") actions.push(["unblock", "Разблокировать", "outline-success"], ["profile", "Профиль", "outline-secondary"], ["schedule", "Расписание", "outline-secondary"], ["calendar", "Исключение календаря", "outline-secondary"]);
    if (key === "customers" && item.status === "active") actions.push(["block-customer", "Заблокировать", "outline-danger"]);
    if (key === "customers" && item.status === "blocked") actions.push(["unblock-customer", "Разблокировать", "outline-success"]);
    if (["performers", "customers"].includes(key)) actions.push(["violation", "Зафиксировать нарушение", "outline-danger"]);
    if (key === "orders" && !["cancelled", "completed", "expired"].includes(item.status)) actions.push(["cancel", "Отменить", "outline-danger"], ["force-close", "Закрыть вручную", "danger"]);
    if (key === "orders" && ["confirmed"].includes(item.status)) actions.push(["start-order", "Подтвердить начало", "outline-primary"]);
    if (key === "orders" && ["in_progress", "waiting_report", "report_submitted"].includes(item.status)) actions.push(["finish-order", "Подтвердить завершение", "outline-primary"]);
    if (key === "orders" && item.status === "searching") actions.push([item.selected_performer_id ? "reassign" : "assign", item.selected_performer_id ? "Сменить исполнителя" : "Назначить исполнителя", "outline-primary"]);
    if (key === "orders" && item.payout_status === "ready") actions.push(["payout", "Отметить выплату", "outline-success"]);
    if (key === "orders" && item.payout_status === "ready") actions.push(["block-payout", "Заблокировать выплату", "outline-danger"]);
    if (key === "orders" && item.payout_status === "blocked") actions.push(["allow-payout", "Разрешить выплату", "outline-success"]);
    if (key === "payments") actions.push(["retry", "Проверить платёж", "outline-warning"], ["refund", "Создать возврат", "outline-danger"]);
    if (key === "notifications" && ["failed", "dead"].includes(item.status)) actions.push(["retry-notification", "Повторить отправку", "outline-warning"]);
    if (["support", "complaints", "disputes"].includes(key) && !["resolved", "closed"].includes(item.status)) actions.push(["support", "Обновить кейс", "outline-primary"]);
    if (key === "deletions" && !["resolved", "completed"].includes(item.status)) actions.push(["resolve", "Завершить удаление", "outline-success"]);
    if (key === "files" && item.status !== "deleted") actions.push(["hide", "Скрыть файл", "outline-danger"]);
    if (key === "services") actions.push(["catalog-service", "Изменить услугу", "outline-primary"]);
    if (key === "settings") actions.push(["setting", "Изменить", "outline-primary"]);
    if (key === "violations" && item.status === "open") actions.push(["resolve-violation", "Закрыть нарушение", "outline-success"]);
    if (["cities", "districts", "service-categories", "service-options", "multipliers", "legal-documents"].includes(key)) actions.push(["catalog-edit", "Изменить", "outline-primary"]);
    if (key === "deletions" && ["open", "in_progress"].includes(item.status)) actions.push(["anonymize-deletion", "Подтвердить удаление", "danger"]);
    return actions.map(([action, title, color]) => `<button class="btn btn-sm btn-${color}" data-action="${action}" data-id="${esc(id)}">${title}</button>`).join("") + `<span id="detail-action-hook"></span>`;
  }

  const actionDefinitions = {
    cancel: ["Отменить заказ", [{ name: "comment", label: "Причина решения", type: "textarea", required: true }]],
    "force-close": ["Принудительно закрыть заказ", [{ name: "comment", label: "Причина решения", type: "textarea", required: true }]],
    assign: ["Назначить исполнителя", [{ name: "performer_id", label: "ID исполнителя", required: true }, { name: "comment", label: "Причина назначения", type: "textarea", required: true }]],
    reassign: ["Сменить исполнителя до оплаты", [{ name: "performer_id", label: "ID нового исполнителя", required: true }, { name: "comment", label: "Причина смены", type: "textarea", required: true }]],
    "start-order": ["Подтвердить начало заказа", [{ name: "performer_id", label: "ID исполнителя", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "finish-order": ["Подтвердить завершение заказа", [{ name: "performer_id", label: "ID исполнителя", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    payout: ["Разрешить выплату", [{ name: "reference", label: "Номер/ссылка подтверждения", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "block-payout": ["Заблокировать выплату", [{ name: "reason", label: "Причина", type: "textarea", required: true }]],
    "allow-payout": ["Разрешить выплату", [{ name: "reason", label: "Причина решения", type: "textarea", required: true }]],
    reject: ["Отклонить исполнителя", [{ name: "reason", label: "Нарушение/причина", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    pause: ["Поставить исполнителя на паузу", [{ name: "comment", label: "Причина", type: "textarea", required: true }]],
    resume: ["Возобновить приём заказов", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    block: ["Заблокировать исполнителя", [{ name: "reason", label: "Причина/нарушение", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "block-customer": ["Заблокировать заказчика", [{ name: "reason", label: "Причина/нарушение", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "unblock-customer": ["Разблокировать заказчика", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    unblock: ["Разблокировать исполнителя", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    profile: ["Изменить профиль исполнителя", [{ name: "phone", label: "Телефон", required: true }, { name: "contact_method", label: "Способ связи", value: "telegram", required: true }, { name: "comment", label: "Причина изменения", type: "textarea", required: true }]],
    schedule: ["Настроить расписание", [{ name: "schedule_type", label: "Тип (every_day/weekdays/weekends/custom)", value: "every_day", required: true }, { name: "work_days", label: "Дни для custom (0–6 через запятую)" }, { name: "work_start_time", label: "Начало", type: "time", value: "09:00", required: true }, { name: "work_end_time", label: "Окончание", type: "time", value: "18:00", required: true }]],
    calendar: ["Добавить исключение календаря", [{ name: "override_type", label: "Тип (unavailable/available)", value: "unavailable", required: true }, { name: "starts_at", label: "Начало", type: "datetime-local", required: true }, { name: "ends_at", label: "Окончание", type: "datetime-local", required: true }, { name: "comment", label: "Комментарий" }]],
    violation: ["Зафиксировать нарушение", [{ name: "violation_type", label: "Тип нарушения", required: true }, { name: "action", label: "Действие (warning/block)", value: "warning", required: true }, { name: "reason", label: "Причина", type: "textarea", required: true }]],
    "enable-service": ["Включить услугу исполнителя", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "disable-service": ["Выключить услугу исполнителя", [{ name: "comment", label: "Причина", type: "textarea", required: true }]],
    "service-limits": ["Изменить лимит услуги", [{ name: "performer_max_objects", label: "Лимит объектов", type: "number", required: true }, { name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "catalog-service": ["Изменить услугу", [{ name: "name", label: "Название", required: true }, { name: "base_price", label: "Базовая цена", type: "number", step: "0.01", required: true }, { name: "description", label: "Описание", type: "textarea", required: true }, { name: "is_active", label: "Активна (true/false)", required: true }, { name: "comment", label: "Причина изменения", type: "textarea", required: true }]],
    refund: ["Создать возврат", [{ name: "amount", label: "Сумма (пусто — полностью)", type: "number", step: "0.01" }, { name: "reason", label: "Причина", type: "textarea", required: true }]],
    support: ["Обновить обращение", [{ name: "status", label: "Новый статус", type: "select", options: ["open", "in_progress", "waiting_user", "resolved", "closed", "rejected"], required: true, value: "in_progress" }, { name: "comment", label: "Комментарий администратора", type: "textarea", required: true }]],
    resolve: ["Завершить удаление", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "resolve-violation": ["Закрыть нарушение", [{ name: "comment", label: "Комментарий", type: "textarea", required: true }]],
    "anonymize-deletion": ["Подтвердить обезличивание аккаунта", [{ name: "comment", label: "Причина решения", type: "textarea", required: true }]],
    "catalog-edit": ["Изменить справочник", [{ name: "changes", label: "Изменения JSON", type: "textarea", value: "{}", required: true }, { name: "comment", label: "Причина изменения", type: "textarea", required: true }]],
    setting: ["Изменить настройку", [{ name: "value", label: "Новое значение JSON", type: "textarea", required: true }]],
    "approve-service": ["Одобрить услугу", [{ name: "admin_max_objects", label: "Лимит объектов", type: "number", required: true }, { name: "constraints", label: "Ограничения JSON", type: "textarea", value: "{}", required: true }]],
  };
  function formMarkup(fields) { return fields.map((field) => `<div class="mb-3"><label class="form-label" for="action-${field.name}">${esc(field.label)}</label>${field.type === "textarea" ? `<textarea class="form-control" name="${field.name}" id="action-${field.name}" ${field.required ? "required" : ""}>${esc(field.value || "")}</textarea>` : field.type === "select" ? `<select class="form-select" name="${field.name}" id="action-${field.name}" ${field.required ? "required" : ""}>${field.options.map((option) => { const optionValue = typeof option === "string" ? option : option.value; const optionLabel = typeof option === "string" ? option : option.label; return `<option value="${esc(optionValue)}" ${optionValue === field.value ? "selected" : ""}>${esc(optionLabel)}</option>`; }).join("")}</select>` : `<input class="form-control" name="${field.name}" id="action-${field.name}" type="${field.type || "text"}" value="${esc(field.value || "")}" ${field.step ? `step="${field.step}"` : ""} ${field.required ? "required" : ""}>`}</div>`).join(""); }
  function openForm(title, fields, submit) { $("action-title").textContent = title; $("action-fields").innerHTML = formMarkup(fields); const form = $("action-form"); form.onsubmit = async (event) => { event.preventDefault(); const submitButton = form.querySelector("[type=submit]"); submitButton.disabled = true; try { await submit(Object.fromEntries(new FormData(form))); modal().hide(); flash("Операция выполнена"); await renderRoute(); } catch (error) { flash(error.message, "danger"); } finally { submitButton.disabled = false; } }; modal().show(); }

  function runAction(action, id, item = state.detailItem || {}) {
    if (action === "retry") return api(`/payments/${id}/retry-check`, { method: "POST", headers: csrfHeaders() }).then(() => { flash("Платёж проверен"); renderRoute(); }).catch((error) => flash(error.message, "danger"));
    if (action === "retry-notification") return api(`/notifications/${id}/retry`, { method: "POST", headers: csrfHeaders() }).then(() => { flash("Уведомление поставлено в очередь"); renderRoute(); }).catch((error) => flash(error.message, "danger"));
    if (action === "hide") return api(`/files/${id}/hide`, { method: "POST", headers: csrfHeaders() }).then(() => { flash("Файл скрыт"); renderRoute(); }).catch((error) => flash(error.message, "danger"));
    if (action === "activate") return api(`/performers/${id}/activate`, { method: "POST", headers: csrfHeaders() }).then(() => { flash("Исполнитель активирован"); renderRoute(); }).catch((error) => flash(error.message, "danger"));
    if (action === "revoke-service") return api(`/performers/${item.performer_id}/services/${item.service_id}/revoke`, { method: "POST", headers: csrfHeaders() }).then(() => { flash("Услуга отозвана"); renderRoute(); }).catch((error) => flash(error.message, "danger"));
    const definition = actionDefinitions[action];
    if (!definition) return;
    const fields = definition[1].map((field) => ({ ...field, value: field.name === "value" && typeof item.value === "object" ? JSON.stringify(item.value, null, 2) : item[field.name] ?? (field.name === "admin_max_objects" ? item.admin_max_objects : field.value) }));
    if (action === "support") fields[0].options = route().key === "disputes" ? ["open", "in_progress", "waiting_user", "closed"] : route().key === "complaints" ? ["open", "in_progress", "waiting_user", "resolved", "closed", "rejected"] : ["open", "in_progress", "waiting_user", "resolved", "closed"];
    openForm(definition[0], fields, async (form) => {
      let path; let method = "POST"; let body = form;
      if (["cancel", "force-close"].includes(action)) path = `/orders/${id}/${action}`;
      if (action === "assign") { path = `/orders/${id}/assign-performer`; body = { performer_id: form.performer_id, comment: form.comment }; }
      if (action === "reassign") { path = `/orders/${id}/reassign-performer`; body = { performer_id: form.performer_id, comment: form.comment }; }
      if (["start-order", "finish-order"].includes(action)) { path = `/orders/${id}/${action === "start-order" ? "start" : "finish"}`; body = { performer_id: form.performer_id, comment: form.comment }; }
      if (action === "payout") path = `/orders/${id}/manual-payout`;
      if (["block-payout", "allow-payout"].includes(action)) path = `/orders/${id}/payout/${action === "block-payout" ? "block" : "allow"}`;
      if (action === "reject") path = `/performers/${id}/reject`;
      if (["pause", "resume", "block", "unblock", "profile"].includes(action)) path = `/performers/${id}/${action}`;
      if (action === "block-customer") path = `/customers/${id}/block`;
      if (action === "unblock-customer") path = `/customers/${id}/unblock`;
      if (["enable-service", "disable-service"].includes(action)) path = `/performers/${item.performer_id}/services/${item.service_id}/${action === "enable-service" ? "enable" : "disable"}`;
      if (action === "service-limits") { path = `/performers/${item.performer_id}/services/${item.service_id}/limits`; method = "PATCH"; body = { performer_max_objects: Number(form.performer_max_objects), comment: form.comment }; }
      if (action === "catalog-service") { path = `/catalog/services/${id}`; method = "PATCH"; body = { name: form.name, base_price: form.base_price, description: form.description, is_active: form.is_active === "true", comment: form.comment }; }
      if (action === "refund") path = `/payments/${id}/refund`;
      if (action === "support") { path = `/support/${route().key}/${id}`; method = "PATCH"; }
      if (action === "resolve") path = `/deletions/${id}/resolve`;
      if (action === "setting") { path = `/settings/${item.key}`; method = "PATCH"; body = { value: JSON.parse(form.value) }; }
      if (action === "approve-service") { path = `/performers/${item.performer_id}/services/${item.service_id}/approve`; body = { admin_max_objects: Number(form.admin_max_objects), constraints: JSON.parse(form.constraints) }; }
      if (action === "refund") body = { amount: form.amount || null, reason: form.reason };
      if (["pause", "resume", "unblock", "enable-service", "disable-service"].includes(action)) body = { comment: form.comment };
      if (action === "block") body = { reason: form.reason, comment: form.comment };
      if (action === "block-customer") body = { reason: form.reason, comment: form.comment };
      if (action === "unblock-customer") body = { comment: form.comment };
      if (action === "profile") { method = "PATCH"; body = { phone: form.phone, contact_method: form.contact_method, comment: form.comment }; }
      if (action === "schedule") { path = `/performers/${id}/schedule`; method = "PUT"; body = { schedule_type: form.schedule_type, work_days: form.work_days ? form.work_days.split(",").map((day) => Number(day.trim())) : null, work_start_time: form.work_start_time, work_end_time: form.work_end_time }; }
      if (action === "calendar") { path = `/performers/${id}/calendar-overrides`; body = { override_type: form.override_type, starts_at: new Date(form.starts_at).toISOString(), ends_at: new Date(form.ends_at).toISOString(), comment: form.comment || null }; }
      if (action === "violation") { path = "/violations"; body = { account_type: route().key === "performers" ? "performer" : "customer", performer_id: route().key === "performers" ? id : null, customer_id: route().key === "customers" ? id : null, violation_type: form.violation_type, action: form.action, reason: form.reason }; }
      if (action === "resolve-violation") { path = `/violations/${id}/resolve`; }
      if (action === "anonymize-deletion") { path = `/deletions/${id}/anonymize`; }
      if (action === "catalog-edit") { path = `/catalog/${route().key}/${id}`; method = "PATCH"; body = { changes: JSON.parse(form.changes), comment: form.comment }; }
      return api(path, { method, headers: csrfHeaders(), body: JSON.stringify(body) });
    });
  }

  function openInvitationForm() { openForm("Пригласить исполнителя", [{ name: "telegram_id", label: "Telegram ID", type: "number", required: true }, { name: "expires_at", label: "Срок действия", type: "datetime-local" }], async (form) => api("/invitations", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ telegram_id: Number(form.telegram_id), expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null }) })); }

  $("page-content").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action], [data-related-action]");
    if (!button) return;
    if (button.dataset.relatedAction) {
      const item = JSON.parse(button.dataset.item || "{}");
      item.performer_id = button.dataset.performerId || item.performer_id;
      item.service_id = button.dataset.serviceId || item.service_id;
      runAction(button.dataset.relatedAction, button.dataset.id, item);
      return;
    }
    runAction(button.dataset.action, button.dataset.id);
  });
  $("login-form").onsubmit = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); try { const response = await fetch("/admin/login", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) }); const data = await response.json(); if (!response.ok) throw new Error(data?.error?.message || "Неверный логин или пароль"); state.admin = data.admin; state.csrf = data.csrf_token; showApp(); navigate("#/dashboard"); await renderRoute(); } catch (error) { $("login-error").textContent = error.message; $("login-error").classList.remove("d-none"); } };
  $("logout").onclick = async () => { try { await fetch("/admin/logout", { method: "POST", credentials: "same-origin", headers: csrfHeaders() }); } finally { showLogin(); } };
  window.onhashchange = () => state.admin && renderRoute();
  (async () => { try { const response = await fetch("/admin/session", { credentials: "same-origin" }); if (!response.ok) throw new Error("Unauthenticated"); const session = await response.json(); state.admin = session.admin; state.csrf = session.csrf_token; showApp(); await renderRoute(); } catch { showLogin(); } })();
})();
