(function () {
  "use strict";

  const state = {
    index: null,          // data/index.json contents
    slug: null,           // currently loaded category slug
    categoryData: null,   // full data/{slug}.json contents for the loaded category
    activeFilters: {},    // { facetKey: Set(values) } for enum facets, { facetKey: [min,max] } for range
    sortKey: "es_pn",
    sortDir: 1,
    query: "",
  };

  const els = {
    tree: document.getElementById("category-tree"),
    filters: document.getElementById("filter-pane"),
    tbody: document.getElementById("results-tbody"),
    summary: document.getElementById("results-summary"),
    asOf: document.getElementById("as-of"),
    searchInput: document.getElementById("search-input"),
    tableWrap: document.getElementById("table-wrap"),
  };

  const COLUMNS = [
    { key: "es_pn", label: "ES P/N" },
    { key: "mfr", label: "Mfr / MPN" },
    { key: "pkg_case", label: "Package" },
    { key: "stock_total", label: "Stock" },
    { key: "price", label: "Price" },
  ];

  async function fetchJSON(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  }

  function fmtDate(iso) {
    if (!iso) return "unknown";
    return iso.slice(0, 10);
  }

  function fmtPrice(p) {
    if (p == null) return "—";
    return "฿" + p.toFixed(2);
  }

  function stockClass(qty) {
    if (!qty) return "out";
    if (qty < 100) return "low";
    return "ok";
  }

  // ---------- Boot ----------

  async function init() {
    state.index = await fetchJSON("data/index.json");
    els.asOf.textContent = `Catalogue as of ${fmtDate(state.index.generated_from_last_seen)}`;
    renderCategoryTree();

    const firstSlug = state.index.categories[0] && state.index.categories[0].slug;
    if (firstSlug) await selectCategory(firstSlug);

    els.searchInput.addEventListener("input", debounce(onSearchInput, 180));
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  // ---------- Category tree ----------

  function renderCategoryTree() {
    els.tree.innerHTML = "";
    for (const cat of state.index.categories) {
      const btn = document.createElement("button");
      btn.className = "tree-item" + (cat.slug === state.slug ? " active" : "");
      btn.innerHTML = `<span>${escapeHTML(cat.category.split(" > ").slice(1).join(" > ") || cat.category)}</span><span class="count mono">${cat.count}</span>`;
      btn.title = cat.category;
      btn.addEventListener("click", () => selectCategory(cat.slug));
      els.tree.appendChild(btn);
    }
  }

  async function selectCategory(slug) {
    state.slug = slug;
    state.activeFilters = {};
    renderCategoryTree();

    els.tbody.innerHTML = "";
    els.summary.textContent = "";
    els.filters.innerHTML = '<div class="loading-state">Loading…</div>';

    state.categoryData = await fetchJSON(`data/${slug}.json`);
    renderFilters();
    renderResults();
  }

  // ---------- Filters ----------

  function renderFilters() {
    const facets = state.categoryData.facets;
    const keys = Object.keys(facets);
    if (keys.length === 0) {
      els.filters.innerHTML = '<div class="pane-label">Filter</div><div class="empty-state">No filterable specs for this category.</div>';
      return;
    }

    const frag = document.createDocumentFragment();

    const label = document.createElement("div");
    label.className = "pane-label";
    label.style.display = "flex";
    label.style.justifyContent = "space-between";
    label.style.alignItems = "center";
    label.innerHTML = `<span>Filter</span>`;
    const clearBtn = document.createElement("button");
    clearBtn.className = "clear-filters";
    clearBtn.textContent = "Clear";
    clearBtn.style.textTransform = "none";
    clearBtn.style.letterSpacing = "normal";
    clearBtn.style.fontFamily = "'Inter', sans-serif";
    clearBtn.addEventListener("click", () => {
      state.activeFilters = {};
      renderFilters();
      renderResults();
    });
    label.appendChild(clearBtn);
    frag.appendChild(label);

    for (const key of keys) {
      const facet = facets[key];
      const group = document.createElement("div");
      group.className = "facet-group";
      const title = document.createElement("div");
      title.className = "facet-title";
      title.textContent = key;
      group.appendChild(title);

      if (facet.type === "enum") {
        group.appendChild(renderEnumFacet(key, facet));
      } else {
        group.appendChild(renderRangeFacet(key, facet));
      }
      frag.appendChild(group);
    }

    els.filters.innerHTML = "";
    els.filters.appendChild(frag);
  }

  function countForEnumValue(key, value) {
    // count matches under all *other* active filters, so options that would
    // zero out the result set are visibly greyed rather than just vanishing
    const otherFilters = { ...state.activeFilters };
    const current = otherFilters[key] ? new Set(otherFilters[key]) : new Set();
    delete otherFilters[key];
    return filterParts(state.categoryData.parts, otherFilters, state.query).filter(
      (p) => (p.specs[key] || "") === value
    ).length;
  }

  function renderEnumFacet(key, facet) {
    const wrap = document.createElement("div");
    const activeSet = state.activeFilters[key] instanceof Set ? state.activeFilters[key] : new Set();
    for (const value of facet.values) {
      const n = countForEnumValue(key, value);
      const opt = document.createElement("label");
      opt.className = "facet-opt" + (n === 0 && !activeSet.has(value) ? " zero" : "");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = activeSet.has(value);
      cb.addEventListener("change", () => {
        const set = state.activeFilters[key] instanceof Set ? state.activeFilters[key] : new Set();
        if (cb.checked) set.add(value);
        else set.delete(value);
        if (set.size === 0) delete state.activeFilters[key];
        else state.activeFilters[key] = set;
        renderFilters();
        renderResults();
      });
      opt.appendChild(cb);
      const span = document.createElement("span");
      span.textContent = value;
      opt.appendChild(span);
      const countSpan = document.createElement("span");
      countSpan.className = "n";
      countSpan.textContent = n;
      opt.appendChild(countSpan);
      wrap.appendChild(opt);
    }
    return wrap;
  }

  function renderRangeFacet(key, facet) {
    const wrap = document.createElement("div");
    wrap.className = "facet-range-inputs";
    const current = state.activeFilters[key] || [facet.min, facet.max];

    const minInput = document.createElement("input");
    minInput.type = "number";
    minInput.value = trimNum(current[0]);
    minInput.placeholder = trimNum(facet.min);

    const dash = document.createElement("span");
    dash.textContent = "–";
    dash.className = "facet-range-unit";

    const maxInput = document.createElement("input");
    maxInput.type = "number";
    maxInput.value = trimNum(current[1]);
    maxInput.placeholder = trimNum(facet.max);

    const unit = document.createElement("span");
    unit.className = "facet-range-unit";
    unit.textContent = facet.unit || "";

    function apply() {
      const lo = minInput.value === "" ? facet.min : parseFloat(minInput.value);
      const hi = maxInput.value === "" ? facet.max : parseFloat(maxInput.value);
      if (lo <= facet.min && hi >= facet.max) delete state.activeFilters[key];
      else state.activeFilters[key] = [lo, hi];
      renderResults();
    }
    minInput.addEventListener("change", apply);
    maxInput.addEventListener("change", apply);

    wrap.appendChild(minInput);
    wrap.appendChild(dash);
    wrap.appendChild(maxInput);
    wrap.appendChild(unit);
    return wrap;
  }

  function trimNum(n) {
    if (n == null) return "";
    const s = n.toPrecision(6).replace(/\.?0+$/, "");
    return s;
  }

  // ---------- Search parsing ----------

  // Recognize tokens shaped like a spec value (e.g. "100nF", "0402", "±5%")
  // and treat them as a soft text match rather than trying to resolve them
  // against facet keys we don't know the user meant -- keeps this simple
  // and avoids false-positive filtering on ambiguous tokens.
  function onSearchInput(e) {
    state.query = e.target.value.trim();
    renderResults();
  }

  // Scraped text uses proper unit symbols ("100μF", "47KΩ") that nobody
  // types on a keyboard -- normalize both sides to ASCII so a query typed
  // as "100uF" or "47kohm" still matches.
  function normalizeUnits(s) {
    return s
      .toLowerCase()
      .replace(/[µμ]/g, "u")
      .replace(/Ω/gi, "ohm")
      .replace(/±/g, "");
  }

  function textMatches(part, query) {
    if (!query) return true;
    const haystack = normalizeUnits(
      [part.es_pn, part.mpn, part.mfr, part.description, part.pkg_case, part.category_path]
        .filter(Boolean)
        .join(" ")
    );
    return normalizeUnits(query)
      .split(/\s+/)
      .every((token) => haystack.includes(token));
  }

  // ---------- Filtering / sorting ----------

  function filterParts(parts, filters, query) {
    return parts.filter((p) => {
      if (!textMatches(p, query)) return false;
      for (const key of Object.keys(filters)) {
        const f = filters[key];
        if (f instanceof Set) {
          if (!f.has(p.specs[key] || "")) return false;
        } else {
          const parsed = p.specs_parsed[key];
          const val = parsed ? parsed.value : NaN;
          if (Number.isNaN(val) || val < f[0] || val > f[1]) return false;
        }
      }
      return true;
    });
  }

  function sortParts(parts) {
    const { sortKey, sortDir } = state;
    return [...parts].sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (typeof av === "string") av = av.toLowerCase();
      if (typeof bv === "string") bv = bv.toLowerCase();
      if (av == null) av = sortDir > 0 ? Infinity : -Infinity;
      if (bv == null) bv = sortDir > 0 ? Infinity : -Infinity;
      if (av < bv) return -sortDir;
      if (av > bv) return sortDir;
      return 0;
    });
  }

  function renderResults() {
    if (!state.categoryData) return;
    const filtered = filterParts(state.categoryData.parts, state.activeFilters, state.query);
    const sorted = sortParts(filtered);

    els.summary.innerHTML = `<b>${filtered.length}</b> of ${state.categoryData.parts.length} results — ${escapeHTML(state.categoryData.category)}`;

    if (sorted.length === 0) {
      els.tbody.innerHTML = "";
      els.tableWrap.querySelector(".empty-state")?.remove();
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No parts match these filters.";
      els.tableWrap.appendChild(empty);
      return;
    }
    els.tableWrap.querySelector(".empty-state")?.remove();

    const frag = document.createDocumentFragment();
    for (const p of sorted.slice(0, 500)) {
      frag.appendChild(renderRow(p));
    }
    els.tbody.innerHTML = "";
    els.tbody.appendChild(frag);
  }

  function renderRow(p) {
    const tr = document.createElement("tr");
    const cls = stockClass(p.stock_total);
    tr.innerHTML = `
      <td><span class="pn">${escapeHTML(p.es_pn)}</span></td>
      <td>${escapeHTML(p.mpn || "—")}<span class="mfr">${escapeHTML(p.mfr || "")}</span></td>
      <td class="mono-num">${escapeHTML(p.pkg_case || "—")}</td>
      <td><span class="stock-pill ${cls}">${p.stock_total.toLocaleString()}</span></td>
      <td class="mono-num">${fmtPrice(p.price)}</td>
    `;
    return tr;
  }

  function escapeHTML(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  // ---------- Sort header wiring ----------

  function wireSortHeaders() {
    document.querySelectorAll("th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (state.sortKey === key) state.sortDir *= -1;
        else {
          state.sortKey = key;
          state.sortDir = 1;
        }
        document.querySelectorAll("th[data-sort]").forEach((h) => h.classList.remove("sorted"));
        th.classList.add("sorted");
        renderResults();
      });
    });
  }

  wireSortHeaders();
  init().catch((err) => {
    els.summary.textContent = "Failed to load parts data.";
    console.error(err);
  });
})();
