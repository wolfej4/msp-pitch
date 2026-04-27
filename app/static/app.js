// ===== State =====
const state = {
  config: null,
  prospects: [],
  services: [],
  categories: [],
  catalogFilter: { text: "", category: "" },
  quickFilter: { text: "", category: "" },
  activeProspectId: null,
  activeProspect: null,
  proposalItems: [],
  messages: [],
};

// ===== Helpers =====
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status}: ${txt}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " error" : "");
  setTimeout(() => el.classList.add("hidden"), 4000);
}

function fmtMoney(n) { return "$" + (n || 0).toFixed(2); }

function fmtPrice(item) {
  const unit = item.price_unit || "flat";
  const cycle = item.billing_cycle || "monthly";
  const unitLabel = unit === "flat" ? "" : ` ${unit.replace(/_/g, " ")}`;
  return `${fmtMoney(item.price || item.default_price || 0)}${unitLabel} / ${cycle.replace(/_/g, "-")}`;
}

function showView(name) {
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
}

// ===== Modal =====
function openModal({ title, body, footer }) {
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = "";
  if (typeof body === "string") $("#modalBody").innerHTML = body;
  else $("#modalBody").appendChild(body);

  $("#modalFooter").innerHTML = "";
  (footer || []).forEach((btn) => {
    const b = document.createElement("button");
    b.textContent = btn.label;
    if (btn.primary) b.classList.add("primary");
    if (btn.danger) b.classList.add("danger");
    b.onclick = btn.onClick;
    $("#modalFooter").appendChild(b);
  });
  $("#modalBackdrop").classList.remove("hidden");
}
function closeModal() { $("#modalBackdrop").classList.add("hidden"); }
$("#modalClose").onclick = closeModal;
$("#modalBackdrop").onclick = (e) => { if (e.target.id === "modalBackdrop") closeModal(); };

// ===== Bootstrap =====
async function bootstrap() {
  state.config = await api("/api/config");
  $("#brandName").textContent = state.config.company_name;
  $("#brandTag").textContent = state.config.company_tagline || "";
  document.title = `${state.config.company_name} — Client Pitch`;
  $("#llmBadge").textContent = `${state.config.llm_provider}: ${state.config.llm_model}`;
  refreshHeaderLogo(state.config.has_logo);

  await loadCategories();
  await loadServices();
  await loadProspects();
}

// ===== Categories =====
async function loadCategories() {
  state.categories = await api("/api/categories");
}

function categoryNames() {
  return state.categories.map((c) => c.name);
}

function buildCategoryOptions(selected, { includeBlank = false, blankLabel = "All categories" } = {}) {
  const opts = [];
  if (includeBlank) opts.push(`<option value="">${escapeHtml(blankLabel)}</option>`);
  // Show known categories from the table
  const names = new Set(categoryNames());
  // Plus any orphan category strings already on services so the user can still see/select them
  for (const s of state.services) if (s.category) names.add(s.category);
  const sorted = Array.from(names).sort((a, b) => a.localeCompare(b));
  for (const name of sorted) {
    const sel = name === selected ? " selected" : "";
    opts.push(`<option value="${escapeAttr(name)}"${sel}>${escapeHtml(name)}</option>`);
  }
  return opts.join("");
}

function refreshHeaderLogo(hasLogo) {
  const img = $("#brandLogo");
  if (hasLogo) {
    img.src = `/api/logo?t=${Date.now()}`;
    img.classList.remove("hidden");
  } else {
    img.removeAttribute("src");
    img.classList.add("hidden");
  }
}

function logoModal() {
  const hasLogo = !!state.config.has_logo;
  const body = document.createElement("div");
  body.innerHTML = `
    ${hasLogo ? `<img class="logo-preview" id="logoPreview" src="/api/logo?t=${Date.now()}" alt="">` : `<img class="logo-preview hidden" id="logoPreview" alt="">`}
    <div class="field">
      <label>Choose an image (PNG, JPG, SVG, or GIF — max 2 MB)</label>
      <input type="file" id="logoFile" accept=".png,.jpg,.jpeg,.svg,.gif,image/png,image/jpeg,image/svg+xml,image/gif">
    </div>
    <div class="muted" style="font-size:12px;">The logo appears in the app header and on every PDF proposal.</div>
  `;
  const fileInput = $("#logoFile", body);
  const preview = $("#logoPreview", body);
  fileInput.onchange = () => {
    const f = fileInput.files && fileInput.files[0];
    if (!f) return;
    preview.src = URL.createObjectURL(f);
    preview.classList.remove("hidden");
  };

  const footer = [{ label: "Cancel", onClick: closeModal }];
  if (hasLogo) {
    footer.push({
      label: "Remove",
      danger: true,
      onClick: async () => {
        if (!confirm("Remove the current logo?")) return;
        const res = await fetch("/api/logo", { method: "DELETE" });
        if (!res.ok) { toast("Failed to remove logo", true); return; }
        state.config.has_logo = false;
        refreshHeaderLogo(false);
        closeModal();
        toast("Logo removed");
      },
    });
  }
  footer.push({
    label: "Upload",
    primary: true,
    onClick: async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) { toast("Pick a file first", true); return; }
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch("/api/logo", { method: "POST", body: fd });
      if (!res.ok) {
        const txt = await res.text();
        toast("Upload failed: " + txt, true);
        return;
      }
      state.config.has_logo = true;
      refreshHeaderLogo(true);
      closeModal();
      toast("Logo updated");
    },
  });

  openModal({ title: "Company Logo", body, footer });
}

// ===== Prospects =====
async function loadProspects() {
  state.prospects = await api("/api/prospects");
  renderProspects();
}

function renderProspects() {
  const list = $("#prospectList");
  if (state.prospects.length === 0) {
    list.innerHTML = '<div class="empty-state">No prospects yet. Click "+ New Prospect" to get started.</div>';
    return;
  }
  list.innerHTML = "";
  for (const p of state.prospects) {
    const card = document.createElement("div");
    card.className = "prospect-card";
    card.innerHTML = `
      <button class="delete-x" data-id="${p.id}" title="Delete">×</button>
      <h3>${escapeHtml(p.company_name)}</h3>
      <div class="meta">${escapeHtml(p.contact_name || "—")}${p.industry ? " · " + escapeHtml(p.industry) : ""}</div>
      <div class="stats">
        <span>Updated ${new Date(p.updated_at).toLocaleDateString()}</span>
      </div>
    `;
    card.onclick = (e) => {
      if (e.target.classList.contains("delete-x")) return;
      openProspect(p.id);
    };
    card.querySelector(".delete-x").onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${p.company_name}" and all its data?`)) return;
      await api(`/api/prospects/${p.id}`, { method: "DELETE" });
      await loadProspects();
      toast("Prospect deleted");
    };
    list.appendChild(card);
  }
}

function newProspectModal() {
  const form = document.createElement("div");
  form.innerHTML = `
    <div class="field"><label>Company Name *</label><input type="text" id="f_company" required></div>
    <div class="field-row">
      <div class="field"><label>Contact Name</label><input type="text" id="f_contact"></div>
      <div class="field"><label>Industry</label><input type="text" id="f_industry" placeholder="Law firm, restaurant, ..."></div>
    </div>
    <div class="field-row">
      <div class="field"><label>Email</label><input type="email" id="f_email"></div>
      <div class="field"><label>Phone</label><input type="tel" id="f_phone"></div>
    </div>
    <div class="field"><label>Headcount</label><input type="text" id="f_headcount" placeholder="e.g. 15 users, 25 endpoints"></div>
    <div class="field"><label>Notes</label><textarea id="f_notes" rows="3"></textarea></div>
  `;
  openModal({
    title: "New Prospect",
    body: form,
    footer: [
      { label: "Cancel", onClick: closeModal },
      {
        label: "Create",
        primary: true,
        onClick: async () => {
          const company = $("#f_company", form).value.trim();
          if (!company) { toast("Company name is required", true); return; }
          const data = {
            company_name: company,
            contact_name: $("#f_contact", form).value.trim(),
            industry: $("#f_industry", form).value.trim(),
            email: $("#f_email", form).value.trim(),
            phone: $("#f_phone", form).value.trim(),
            headcount: $("#f_headcount", form).value.trim(),
            notes: $("#f_notes", form).value.trim(),
          };
          const created = await api("/api/prospects", { method: "POST", body: JSON.stringify(data) });
          closeModal();
          await loadProspects();
          openProspect(created.id);
        },
      },
    ],
  });
}

function editProspectModal() {
  const p = state.activeProspect;
  const form = document.createElement("div");
  form.innerHTML = `
    <div class="field"><label>Company Name *</label><input type="text" id="f_company" value="${escapeAttr(p.company_name)}"></div>
    <div class="field-row">
      <div class="field"><label>Contact Name</label><input type="text" id="f_contact" value="${escapeAttr(p.contact_name)}"></div>
      <div class="field"><label>Industry</label><input type="text" id="f_industry" value="${escapeAttr(p.industry)}"></div>
    </div>
    <div class="field-row">
      <div class="field"><label>Email</label><input type="email" id="f_email" value="${escapeAttr(p.email)}"></div>
      <div class="field"><label>Phone</label><input type="tel" id="f_phone" value="${escapeAttr(p.phone)}"></div>
    </div>
    <div class="field"><label>Headcount</label><input type="text" id="f_headcount" value="${escapeAttr(p.headcount)}"></div>
    <div class="field"><label>Notes (also shown as "Discussion Summary" on PDF)</label><textarea id="f_notes" rows="4">${escapeHtml(p.notes)}</textarea></div>
  `;
  openModal({
    title: "Edit Prospect",
    body: form,
    footer: [
      { label: "Cancel", onClick: closeModal },
      {
        label: "Save",
        primary: true,
        onClick: async () => {
          const data = {
            company_name: $("#f_company", form).value.trim(),
            contact_name: $("#f_contact", form).value.trim(),
            industry: $("#f_industry", form).value.trim(),
            email: $("#f_email", form).value.trim(),
            phone: $("#f_phone", form).value.trim(),
            headcount: $("#f_headcount", form).value.trim(),
            notes: $("#f_notes", form).value.trim(),
          };
          await api(`/api/prospects/${p.id}`, { method: "PATCH", body: JSON.stringify(data) });
          closeModal();
          await openProspect(p.id);
          toast("Prospect updated");
        },
      },
    ],
  });
}

async function openProspect(id) {
  state.activeProspectId = id;
  state.activeProspect = await api(`/api/prospects/${id}`);
  $("#activeProspectName").textContent = state.activeProspect.company_name;
  showView("active");
  await Promise.all([loadProposalItems(), loadMessages(), renderCatalogQuick()]);
}

// ===== Messages / Chat =====
async function loadMessages() {
  state.messages = await api(`/api/prospects/${state.activeProspectId}/messages`);
  renderChat();
}

function renderChat() {
  const log = $("#chatLog");
  log.innerHTML = "";
  if (state.messages.length === 0) {
    log.innerHTML = '<div class="empty-state" style="margin: auto;">Start the discovery — ask the AI to suggest questions to ask, recommend services, or help shape your pitch.</div>';
    return;
  }
  for (const m of state.messages) appendMessage(m.role, m.content);
  log.scrollTop = log.scrollHeight;
}

function appendMessage(role, content) {
  const log = $("#chatLog");
  // remove empty state if present
  const empty = log.querySelector(".empty-state");
  if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.innerHTML = renderMarkdown(content);
  // make bolded service names clickable to add to proposal
  $$("strong", div).forEach((s) => {
    const name = s.textContent.trim();
    const svc = state.services.find((sv) => sv.name.toLowerCase() === name.toLowerCase());
    if (svc) {
      s.title = `Click to add "${svc.name}" to proposal`;
      s.onclick = () => addServiceToProposal(svc.id);
    }
  });
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function renderMarkdown(text) {
  // very minimal: bold, lists, paragraphs. Avoid heavy deps.
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // bullet lists (simple)
  html = html.replace(/(^|\n)- (.+?)(?=\n|$)/g, "$1<li>$2</li>");
  html = html.replace(/(<li>.*<\/li>)(\n|$)/gs, (m) => `<ul>${m.replace(/\n/g, "")}</ul>`);
  // paragraphs
  html = html.split(/\n\n+/).map((p) => p.startsWith("<ul>") ? p : `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
  return html;
}

async function sendChat(message) {
  appendMessage("user", message);
  const assistantDiv = appendMessage("assistant", "");
  const cursor = '<span class="streaming-cursor">▍</span>';
  assistantDiv.innerHTML = cursor;
  $("#chatSubmitBtn").disabled = true;

  let fullText = "";
  try {
    const res = await fetch(`/api/prospects/${state.activeProspectId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error(await res.text());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      assistantDiv.innerHTML = renderMarkdown(fullText) + cursor;
      $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
    }
    assistantDiv.innerHTML = renderMarkdown(fullText);
    // wire bolded service names
    $$("strong", assistantDiv).forEach((s) => {
      const name = s.textContent.trim();
      const svc = state.services.find((sv) => sv.name.toLowerCase() === name.toLowerCase());
      if (svc) {
        s.title = `Click to add "${svc.name}" to proposal`;
        s.onclick = () => addServiceToProposal(svc.id);
      }
    });
  } catch (e) {
    assistantDiv.innerHTML = `<em style="color:var(--danger)">Error: ${escapeHtml(e.message)}</em>`;
    toast("Chat failed: " + e.message, true);
  } finally {
    $("#chatSubmitBtn").disabled = false;
  }
}

$("#chatForm").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#chatInput");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  await sendChat(msg);
};

$("#btnClearChat").onclick = async () => {
  if (!confirm("Clear conversation history for this prospect?")) return;
  await api(`/api/prospects/${state.activeProspectId}/messages`, { method: "DELETE" });
  state.messages = [];
  renderChat();
};

// ===== Services / Catalog =====
async function loadServices() {
  state.services = await api("/api/services");
  renderCatalog();
}

function renderCatalog() {
  // Refresh the category filter dropdown so it always reflects current categories.
  const catSel = $("#catalogCategoryFilter");
  if (catSel) {
    catSel.innerHTML = buildCategoryOptions(state.catalogFilter.category, {
      includeBlank: true,
    });
  }

  const list = $("#catalogList");
  list.innerHTML = "";
  if (state.services.length === 0) {
    list.innerHTML = '<div class="empty-state">No services yet.</div>';
    return;
  }

  const text = state.catalogFilter.text.toLowerCase();
  const cat = state.catalogFilter.category;
  const filtered = state.services.filter((s) => {
    if (cat && s.category !== cat) return false;
    if (!text) return true;
    return (
      s.name.toLowerCase().includes(text) ||
      (s.category || "").toLowerCase().includes(text) ||
      (s.description || "").toLowerCase().includes(text)
    );
  });

  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state">No services match your filters.</div>';
    return;
  }

  for (const s of filtered) {
    const card = document.createElement("div");
    card.className = "catalog-card";
    card.innerHTML = `
      <div class="row1">
        <div>
          <div class="cat">${escapeHtml(s.category)}</div>
          <div class="name">${escapeHtml(s.name)}</div>
        </div>
        <div class="price">${fmtPrice(s)}</div>
      </div>
      <div class="desc">${escapeHtml(s.description)}</div>
      <div class="actions">
        <button data-action="edit" data-id="${s.id}">Edit</button>
        <button data-action="delete" data-id="${s.id}" class="danger">Delete</button>
      </div>
    `;
    card.querySelector('[data-action="edit"]').onclick = () => serviceModal(s);
    card.querySelector('[data-action="delete"]').onclick = async () => {
      if (!confirm(`Delete service "${s.name}"?`)) return;
      await api(`/api/services/${s.id}`, { method: "DELETE" });
      await loadServices();
      toast("Service deleted");
    };
    list.appendChild(card);
  }
}

function renderCatalogQuick() {
  const catSel = $("#catalogQuickCategory");
  if (catSel) {
    catSel.innerHTML = buildCategoryOptions(state.quickFilter.category, {
      includeBlank: true,
    });
  }

  const wrap = $("#catalogQuickList");
  wrap.innerHTML = "";
  const text = state.quickFilter.text.toLowerCase();
  const cat = state.quickFilter.category;
  const filtered = state.services.filter((s) => {
    if (cat && s.category !== cat) return false;
    if (!text) return true;
    return s.name.toLowerCase().includes(text) || (s.category || "").toLowerCase().includes(text);
  });
  if (filtered.length === 0) {
    wrap.innerHTML = '<div class="empty-state" style="padding:20px;">No matching services.</div>';
    return;
  }
  for (const s of filtered) {
    const item = document.createElement("div");
    item.className = "catalog-quick-item";
    item.innerHTML = `
      <div>
        <div class="cat-tag">${escapeHtml(s.category)}</div>
        <div class="name">${escapeHtml(s.name)}</div>
      </div>
      <div class="price">${fmtPrice(s)}</div>
    `;
    item.onclick = () => addServiceToProposal(s.id);
    wrap.appendChild(item);
  }
}

$("#catalogFilter").addEventListener("input", (e) => {
  state.quickFilter.text = e.target.value;
  renderCatalogQuick();
});
$("#catalogQuickCategory").addEventListener("change", (e) => {
  state.quickFilter.category = e.target.value;
  renderCatalogQuick();
});
$("#catalogTextFilter").addEventListener("input", (e) => {
  state.catalogFilter.text = e.target.value;
  renderCatalog();
});
$("#catalogCategoryFilter").addEventListener("change", (e) => {
  state.catalogFilter.category = e.target.value;
  renderCatalog();
});

function serviceModal(svc = null) {
  const isNew = !svc;
  const s = svc || { name: "", category: "General", description: "", default_price: 0, price_unit: "flat", billing_cycle: "monthly", is_active: 1 };
  const form = document.createElement("div");
  form.innerHTML = `
    <div class="field-row">
      <div class="field"><label>Name *</label><input type="text" id="s_name" value="${escapeAttr(s.name)}"></div>
      <div class="field">
        <label>Category</label>
        <select id="s_cat">${buildCategoryOptions(s.category)}</select>
      </div>
    </div>
    <div class="field"><label>Description</label><textarea id="s_desc" rows="3">${escapeHtml(s.description)}</textarea></div>
    <div class="field-row">
      <div class="field"><label>Default Price</label><input type="number" step="0.01" id="s_price" value="${s.default_price}"></div>
      <div class="field"><label>Price Unit</label>
        <select id="s_unit">
          <option value="flat" ${s.price_unit==="flat"?"selected":""}>Flat</option>
          <option value="per_user" ${s.price_unit==="per_user"?"selected":""}>Per User</option>
          <option value="per_device" ${s.price_unit==="per_device"?"selected":""}>Per Device</option>
          <option value="per_endpoint" ${s.price_unit==="per_endpoint"?"selected":""}>Per Endpoint</option>
        </select>
      </div>
    </div>
    <div class="field"><label>Billing Cycle</label>
      <select id="s_cycle">
        <option value="monthly" ${s.billing_cycle==="monthly"?"selected":""}>Monthly</option>
        <option value="annual" ${s.billing_cycle==="annual"?"selected":""}>Annual</option>
        <option value="one_time" ${s.billing_cycle==="one_time"?"selected":""}>One-time</option>
      </select>
    </div>
  `;
  openModal({
    title: isNew ? "New Service" : "Edit Service",
    body: form,
    footer: [
      { label: "Cancel", onClick: closeModal },
      {
        label: isNew ? "Create" : "Save",
        primary: true,
        onClick: async () => {
          const data = {
            name: $("#s_name", form).value.trim(),
            category: $("#s_cat", form).value.trim() || "General",
            description: $("#s_desc", form).value.trim(),
            default_price: parseFloat($("#s_price", form).value) || 0,
            price_unit: $("#s_unit", form).value,
            billing_cycle: $("#s_cycle", form).value,
          };
          if (!data.name) { toast("Name is required", true); return; }
          if (isNew) await api("/api/services", { method: "POST", body: JSON.stringify(data) });
          else await api(`/api/services/${svc.id}`, { method: "PATCH", body: JSON.stringify(data) });
          closeModal();
          await loadServices();
          if (state.activeProspectId) renderCatalogQuick();
          toast(isNew ? "Service added" : "Service saved");
        },
      },
    ],
  });
}

$("#btnNewService").onclick = () => serviceModal(null);

// ===== Manage Categories =====
function manageCategoriesModal() {
  const body = document.createElement("div");

  const render = () => {
    const counts = {};
    for (const s of state.services) counts[s.category] = (counts[s.category] || 0) + 1;
    const rows = state.categories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(
        (c) => `
        <div class="cat-row" data-id="${c.id}">
          <input type="text" class="cat-name" value="${escapeAttr(c.name)}">
          <span class="cat-count muted">${counts[c.name] || 0} service${counts[c.name] === 1 ? "" : "s"}</span>
          <button class="small" data-action="rename">Save</button>
          <button class="small danger" data-action="delete">Delete</button>
        </div>`
      )
      .join("");
    body.innerHTML = `
      <div class="cat-list">${rows || '<div class="muted" style="padding:8px;">No categories yet.</div>'}</div>
      <div class="field" style="margin-top:14px; display:flex; gap:8px; align-items:flex-end;">
        <div style="flex:1;"><label>Add category</label><input type="text" id="newCatName" placeholder="e.g. Compliance"></div>
        <button class="primary small" id="btnAddCat">Add</button>
      </div>
      <div class="muted" style="font-size:11px; margin-top:6px;">
        Renaming a category renames it on every service that uses it. Deleting a category reassigns its services to "General".
      </div>
    `;

    $("#btnAddCat", body).onclick = async () => {
      const name = $("#newCatName", body).value.trim();
      if (!name) { toast("Name is required", true); return; }
      try {
        await api("/api/categories", { method: "POST", body: JSON.stringify({ name }) });
        await loadCategories();
        render();
        toast("Category added");
      } catch (e) {
        toast(e.message, true);
      }
    };

    $$(".cat-row", body).forEach((row) => {
      const id = row.dataset.id;
      const input = $(".cat-name", row);
      $('[data-action="rename"]', row).onclick = async () => {
        const name = input.value.trim();
        if (!name) { toast("Name is required", true); return; }
        try {
          await api(`/api/categories/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
          await Promise.all([loadCategories(), loadServices()]);
          render();
          if (state.activeProspectId) renderCatalogQuick();
          toast("Category renamed");
        } catch (e) {
          toast(e.message, true);
        }
      };
      $('[data-action="delete"]', row).onclick = async () => {
        const cat = state.categories.find((c) => String(c.id) === String(id));
        if (!cat) return;
        const used = (counts[cat.name] || 0);
        const msg = used
          ? `Delete "${cat.name}"? ${used} service${used === 1 ? "" : "s"} will be reassigned to "General".`
          : `Delete "${cat.name}"?`;
        if (!confirm(msg)) return;
        await api(`/api/categories/${id}`, { method: "DELETE" });
        await Promise.all([loadCategories(), loadServices()]);
        render();
        if (state.activeProspectId) renderCatalogQuick();
        toast("Category deleted");
      };
    });
  };

  render();

  openModal({
    title: "Manage Categories",
    body,
    footer: [{ label: "Done", primary: true, onClick: closeModal }],
  });
}

$("#btnManageCategories").onclick = manageCategoriesModal;

// ===== Proposal items =====
async function loadProposalItems() {
  state.proposalItems = await api(`/api/prospects/${state.activeProspectId}/items`);
  renderProposal();
}

function renderProposal() {
  const wrap = $("#proposalItems");
  wrap.innerHTML = "";
  $("#proposalCount").textContent = `${state.proposalItems.length} item${state.proposalItems.length === 1 ? "" : "s"}`;

  if (state.proposalItems.length === 0) {
    wrap.innerHTML = '<div class="empty-state" style="padding:20px;">Click services from the catalog below or ask the AI to suggest some.</div>';
    renderTotals();
    return;
  }

  for (const it of state.proposalItems) {
    const div = document.createElement("div");
    div.className = "proposal-item";
    div.innerHTML = `
      <div class="name">${escapeHtml(it.name)} <button class="remove" title="Remove">×</button></div>
      <div class="controls">
        <input type="number" step="0.5" value="${it.quantity}" data-field="quantity" title="Quantity">
        <input type="number" step="0.01" value="${it.price}" data-field="price" title="Price">
        <select data-field="billing_cycle">
          <option value="monthly" ${it.billing_cycle==="monthly"?"selected":""}>monthly</option>
          <option value="annual" ${it.billing_cycle==="annual"?"selected":""}>annual</option>
          <option value="one_time" ${it.billing_cycle==="one_time"?"selected":""}>one-time</option>
        </select>
        <span class="total">${fmtMoney(it.quantity * it.price)}</span>
      </div>
    `;
    div.querySelector(".remove").onclick = async () => {
      await api(`/api/prospects/${state.activeProspectId}/items/${it.id}`, { method: "DELETE" });
      await loadProposalItems();
    };
    div.querySelectorAll("[data-field]").forEach((input) => {
      input.onchange = async () => {
        const data = {};
        data[input.dataset.field] = input.type === "number" ? parseFloat(input.value) : input.value;
        await api(`/api/prospects/${state.activeProspectId}/items/${it.id}`, {
          method: "PATCH", body: JSON.stringify(data),
        });
        await loadProposalItems();
      };
    });
    wrap.appendChild(div);
  }
  renderTotals();
}

function renderTotals() {
  const wrap = $("#proposalTotals");
  const totals = { monthly: 0, annual: 0, one_time: 0 };
  for (const it of state.proposalItems) {
    totals[it.billing_cycle] = (totals[it.billing_cycle] || 0) + it.quantity * it.price;
  }
  const grand = totals.monthly * 12 + totals.annual + totals.one_time;
  wrap.innerHTML = `
    <div class="row"><span class="label">Recurring (monthly)</span><span class="value">${fmtMoney(totals.monthly)}</span></div>
    <div class="row"><span class="label">Recurring (annual)</span><span class="value">${fmtMoney(totals.annual)}</span></div>
    <div class="row"><span class="label">One-time</span><span class="value">${fmtMoney(totals.one_time)}</span></div>
    <div class="row grand"><span class="label">Est. first-year total</span><span class="value">${fmtMoney(grand)}</span></div>
  `;
}

async function addServiceToProposal(serviceId) {
  await api(`/api/prospects/${state.activeProspectId}/items/from-service/${serviceId}`, { method: "POST" });
  await loadProposalItems();
  toast("Added to proposal");
}

// ===== PDF / Email =====
$("#btnDownloadPdf").onclick = () => {
  if (!state.activeProspectId) return;
  window.location.href = `/api/prospects/${state.activeProspectId}/proposal.pdf`;
};

$("#btnEmailPdf").onclick = () => {
  if (!state.config.smtp_configured) {
    toast("SMTP isn't configured. Set SMTP_HOST / SMTP_FROM in .env, then restart.", true);
    return;
  }
  const p = state.activeProspect;
  const form = document.createElement("div");
  form.innerHTML = `
    <div class="field"><label>To *</label><input type="email" id="e_to" value="${escapeAttr(p.email)}"></div>
    <div class="field"><label>Subject</label><input type="text" id="e_subject" placeholder="(default will be used if blank)"></div>
    <div class="field"><label>Message</label><textarea id="e_body" rows="5" placeholder="(default will be used if blank)"></textarea></div>
  `;
  openModal({
    title: "Email Proposal",
    body: form,
    footer: [
      { label: "Cancel", onClick: closeModal },
      {
        label: "Send",
        primary: true,
        onClick: async () => {
          const to = $("#e_to", form).value.trim();
          if (!to) { toast("Recipient email required", true); return; }
          try {
            await api(`/api/prospects/${state.activeProspectId}/email`, {
              method: "POST",
              body: JSON.stringify({
                to,
                subject: $("#e_subject", form).value.trim() || null,
                body: $("#e_body", form).value.trim() || null,
              }),
            });
            closeModal();
            toast("Proposal sent to " + to);
          } catch (e) {
            toast("Email failed: " + e.message, true);
          }
        },
      },
    ],
  });
};

// ===== Nav wiring =====
$$(".nav-btn").forEach((b) => {
  b.onclick = () => showView(b.dataset.view);
});
$("#btnNewProspect").onclick = newProspectModal;
$("#btnBackToList").onclick = () => { state.activeProspectId = null; showView("prospects"); loadProspects(); };
$("#btnEditProspect").onclick = editProspectModal;
$("#btnLogoSettings").onclick = logoModal;

// ===== Utils =====
function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s || ""); }

bootstrap().catch((e) => {
  console.error(e);
  toast("Failed to initialize: " + e.message, true);
});
