const state = {
  catalog: [],
  liked: [],
  recommendations: [],
  externalItems: [],
  mode: "catalog",
};

const typeNames = {
  movie: "Фильм",
  game: "Игра",
  book: "Книга",
  board_game: "Настольная игра",
};

const elements = {
  status: document.querySelector("#server-status"),
  catalogGrid: document.querySelector("#catalog-grid"),
  externalGrid: document.querySelector("#external-grid"),
  likedList: document.querySelector("#liked-list"),
  localSearch: document.querySelector("#local-search"),
  catalogType: document.querySelector("#catalog-type"),
  resultType: document.querySelector("#result-type"),
  minRating: document.querySelector("#min-rating"),
  ratingValue: document.querySelector("#rating-value"),
  catalogCount: document.querySelector("#catalog-count"),
  catalogView: document.querySelector("#catalog-view"),
  externalView: document.querySelector("#external-view"),
  externalSource: document.querySelector("#external-source"),
  externalQuery: document.querySelector("#external-query"),
  externalNotice: document.querySelector("#external-notice"),
  externalPoolCount: document.querySelector("#external-pool-count"),
  resultsSection: document.querySelector("#results-section"),
  resultsGrid: document.querySelector("#results-grid"),
  resultsSummary: document.querySelector("#results-summary"),
  template: document.querySelector("#card-template"),
};

function fallbackCover(item) {
  return `/covers/${item.id.replace(/[^a-z0-9_-]/gi, "_")}.png`;
}

function isLiked(item) {
  return state.liked.some((liked) => liked.id === item.id);
}

function addLiked(item) {
  if (isLiked(item)) {
    state.liked = state.liked.filter((liked) => liked.id !== item.id);
  } else {
    state.liked.push(item);
  }
  renderLiked();
  renderCatalog();
  elements.recommendButton.disabled = state.liked.length === 0;
}

function renderLiked() {
  elements.likedList.innerHTML = "";
  if (!state.liked.length) {
    elements.likedList.innerHTML = '<div class="empty-small">Добавьте минимум один понравившийся объект</div>';
    return;
  }
  state.liked.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = "liked-chip";
    const title = document.createElement("span");
    title.textContent = item.title;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.title = "Удалить из предпочтений";
    remove.textContent = "×";
    remove.addEventListener("click", () => addLiked(item));
    chip.append(title, remove);
    elements.likedList.append(chip);
  });
}

function createCard(item, { result = false, external = false } = {}) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  const image = card.querySelector(".cover");
  image.src = item.image_url || fallbackCover(item);
  image.alt = `Обложка: ${item.title}`;
  image.onerror = () => {
    image.onerror = null;
    image.src = fallbackCover(item);
  };
  card.querySelector(".type-badge").textContent = typeNames[item.type] || item.type;
  card.querySelector("h3").textContent = item.title;
  card.querySelector(".year").textContent = item.year || "";
  card.querySelector(".rating").textContent = item.rating ? `Рейтинг ${Number(item.rating).toFixed(1)}/10` : "Рейтинг не указан";
  card.querySelector(".description").textContent = item.description || "Описание отсутствует";

  const tags = card.querySelector(".tags");
  [...(item.genres || []), ...(item.tags || [])].slice(0, 5).forEach((value) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = value;
    tags.append(tag);
  });

  if (item.price !== null && item.price !== undefined) {
    const currency = item.currency === "USD" ? "$" : item.currency === "EUR" ? "€" : "₽";
    card.querySelector(".price").textContent = `${item.price.toFixed(2)} ${currency}${item.discount ? ` · скидка ${item.discount}%` : ""}`;
  }

  const source = card.querySelector(".source-link");
  if (item.source_url) {
    source.href = item.source_url;
  } else {
    source.hidden = true;
  }

  const addButton = card.querySelector(".button-add");
  if (result) {
    addButton.hidden = true;
    const score = card.querySelector(".score-badge");
    score.hidden = false;
    score.textContent = `${item.score}%`;
    const reasons = card.querySelector(".reasons");
    (item.reasons || []).forEach((reason) => {
      const row = document.createElement("li");
      row.textContent = reason;
      reasons.append(row);
    });
  } else {
    addButton.textContent = isLiked(item) ? "Добавлено" : "Мне нравится";
    addButton.classList.toggle("added", isLiked(item));
    addButton.addEventListener("click", () => addLiked(item));
  }

  if (external) card.dataset.external = "true";
  return card;
}

function renderCatalog() {
  const query = elements.localSearch.value.trim().toLowerCase();
  const type = elements.catalogType.value;
  const filtered = state.catalog.filter((item) => {
    const typeMatch = type === "all" || item.type === type;
    const text = [item.title, ...(item.genres || []), ...(item.tags || [])].join(" ").toLowerCase();
    return typeMatch && (!query || text.includes(query));
  });
  elements.catalogGrid.innerHTML = "";
  filtered.forEach((item) => elements.catalogGrid.append(createCard(item)));
  elements.catalogCount.textContent = `Найдено объектов: ${filtered.length}`;
}

async function loadCatalog() {
  const response = await fetch("/api/catalog");
  state.catalog = await response.json();
  renderCatalog();
}

async function calculateRecommendations() {
  if (!state.liked.length) {
    alert("Сначала добавьте хотя бы один понравившийся объект.");
    return;
  }
  const response = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      liked_items: state.liked,
      candidate_items: state.externalItems,
      type: elements.resultType.value,
      min_rating: Number(elements.minRating.value),
      limit: 8,
    }),
  });
  state.recommendations = await response.json();
  elements.resultsGrid.innerHTML = "";
  state.recommendations.forEach((item) => elements.resultsGrid.append(createCard(item, { result: true })));
  elements.resultsSummary.textContent = `Подобрано: ${state.recommendations.length}. Предпочтений: ${state.liked.length}; внешних кандидатов: ${state.externalItems.length}.`;
  elements.resultsSection.hidden = false;
  elements.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function searchExternal() {
  const query = elements.externalQuery.value.trim();
  if (!query) return;
  elements.externalGrid.innerHTML = '<div class="loading">Получение данных...</div>';
  elements.externalNotice.classList.remove("error");
  try {
    const params = new URLSearchParams({ source: elements.externalSource.value, q: query });
    const response = await fetch(`/api/source?${params}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Ошибка запроса");
    const merged = new Map(state.externalItems.map((item) => [item.id, item]));
    payload.forEach((item) => merged.set(item.id, item));
    state.externalItems = [...merged.values()];
    elements.externalGrid.innerHTML = "";
    payload.forEach((item) => elements.externalGrid.append(createCard(item, { external: true })));
    elements.externalNotice.textContent = `Получено: ${payload.length}. Эти объекты добавлены в общий пул рекомендаций.`;
    elements.externalPoolCount.textContent = `Внешних кандидатов в текущей сессии: ${state.externalItems.length}`;
  } catch (error) {
    elements.externalGrid.innerHTML = "";
    elements.externalNotice.textContent = `${error.message}. Используйте учебный каталог.`;
    elements.externalNotice.classList.add("error");
  }
}

async function exportResults() {
  if (!state.recommendations.length) return;
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: state.recommendations }),
  });
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "recommendations.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    elements.status.textContent = `Сервер работает · ${payload.items} объектов`;
    elements.status.className = "status ok";
  } catch {
    elements.status.textContent = "Сервер недоступен";
    elements.status.className = "status error";
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    state.mode = tab.dataset.mode;
    elements.catalogView.hidden = state.mode !== "catalog";
    elements.externalView.hidden = state.mode !== "external";
  });
});

elements.localSearch.addEventListener("input", renderCatalog);
elements.catalogType.addEventListener("change", renderCatalog);
elements.minRating.addEventListener("input", () => {
  elements.ratingValue.textContent = Number(elements.minRating.value).toFixed(1);
});
document.querySelector("#recommend-button").addEventListener("click", calculateRecommendations);
elements.recommendButton = document.querySelector("#recommend-button");
elements.recommendButton.disabled = true;
document.querySelector("#clear-liked").addEventListener("click", () => {
  state.liked = [];
  renderLiked();
  renderCatalog();
  elements.resultsSection.hidden = true;
  elements.recommendButton.disabled = true;
});
document.querySelector("#external-search").addEventListener("click", searchExternal);
elements.externalQuery.addEventListener("keydown", (event) => {
  if (event.key === "Enter") searchExternal();
});
document.querySelector("#export-button").addEventListener("click", exportResults);

Promise.all([checkHealth(), loadCatalog()]).catch((error) => {
  elements.status.textContent = error.message;
  elements.status.className = "status error";
});
