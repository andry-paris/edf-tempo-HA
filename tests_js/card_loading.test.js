"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadCardClasses(language = "fr-FR") {
  const registeredElements = new Map();

  class FakeHTMLElement {
    constructor() {
      this.shadowRoot = null;
      this.style = { setProperty() {} };
    }

    attachShadow() {
      const elements = new Map();
      const listeners = new Map();
      this.shadowRoot = {
        addEventListener(type, listener) { listeners.set(type, listener); },
        dispatchEvent(event) { listeners.get(event.type)?.(event); },
        innerHTML: "",
        querySelector(selector) {
          const id = selector.startsWith("#") ? selector.slice(1) : selector;
          if (!elements.has(id)) {
            elements.set(id, {
              allowCustomEntity: false,
              hass: null,
              id,
              includeDomains: null,
              value: "",
            });
          }
          return elements.get(id);
        },
      };
      return this.shadowRoot;
    }

    getBoundingClientRect() {
      return { width: 1000 };
    }
  }

  const context = vm.createContext({
    console,
    CustomEvent: class CustomEvent {
      constructor(type, options) {
        this.type = type;
        Object.assign(this, options);
      }
    },
    Date,
    HTMLElement: FakeHTMLElement,
    Intl,
    Map,
    navigator: { language },
    Promise,
    ResizeObserver: class ResizeObserver {
      disconnect() {}
      observe() {}
    },
    customElements: {
      define(name, elementClass) {
        registeredElements.set(name, elementClass);
      },
      get(name) {
        return registeredElements.get(name);
      },
    },
    window: {},
  });
  const cardPath = path.join(
    __dirname,
    "..",
    "custom_components",
    "edf_tempo",
    "card.js",
  );
  vm.runInContext(fs.readFileSync(cardPath, "utf8"), context, { filename: cardPath });

  return {
    DailyCard: registeredElements.get("edf-tempo-card"),
    DailyEditor: registeredElements.get("edf-tempo-card-editor"),
    MonthCard: registeredElements.get("edf-tempo-month-card"),
    MonthEditor: registeredElements.get("edf-tempo-month-card-editor"),
    SeasonCalendarEditor: registeredElements.get("edf-tempo-season-calendar-card-editor"),
    SeasonCalendarCard: registeredElements.get("edf-tempo-season-calendar-card"),
    SeasonCard: registeredElements.get("edf-tempo-season-card"),
    SeasonEditor: registeredElements.get("edf-tempo-season-card-editor"),
  };
}

function deferredRequest() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function fakeHass(requests) {
  return {
    connection: {
      sendMessagePromise(message) {
        const request = deferredRequest();
        requests.push({ message, ...request });
        return request.promise;
      },
    },
  };
}

test("daily column choice survives editor changes and updates card layout", () => {
  const { DailyCard, DailyEditor } = loadCardClasses();
  const card = new DailyCard();
  const editor = new DailyEditor();
  editor.setConfig({ title: "Tempo" });
  card.setConfig(editor._config);
  assert.equal(card._config.columns, 2);
  assert.match(card.shadowRoot.innerHTML, /grid-template-columns: repeat\(2,/);

  let emitted;
  editor.dispatchEvent = (event) => { emitted = event; };
  editor._handleInput({ target: { id: "columns", value: "1" } });
  assert.equal(emitted.type, "config-changed");
  assert.equal(emitted.detail.config.columns, 1);
  editor.setConfig(emitted.detail.config);
  editor._handleInput({ target: { id: "title", value: "Mon Tempo" } });
  assert.equal(emitted.detail.config.columns, 1);
  card.setConfig(emitted.detail.config);
  assert.match(card.shadowRoot.innerHTML, /grid-template-columns: repeat\(1,/);
  assert.equal(card.getCardSize(), 4);

  editor.setConfig({ ...emitted.detail.config, columns: 2 });
  assert.match(editor.shadowRoot.innerHTML, /id="columns"[^>]*value="2"/);
  card.setConfig(editor._config);
  assert.match(card.shadowRoot.innerHTML, /grid-template-columns: repeat\(2,/);
  assert.equal(card.getCardSize(), 2);
});

test("daily card and editor keep YAML column values within one or two", () => {
  const { DailyCard, DailyEditor } = loadCardClasses();
  for (const [value, expected] of [[undefined, 2], [1, 1], ["2", 2], [0, 1], [3, 2], ["invalid", 2]]) {
    for (const Element of [DailyCard, DailyEditor]) {
      const element = new Element();
      element.setConfig({ columns: value });
      assert.equal(element._config.columns, expected);
    }
  }
});

test("tomorrow timestamps are optional, positioned by the editor and use the HA timezone", () => {
  const { DailyCard, DailyEditor } = loadCardClasses();
  const card = new DailyCard();
  const editor = new DailyEditor();
  editor.setConfig({});
  card.setConfig(editor._config);
  const tomorrow = { state: "red", attributes: {
    date: "2026-09-21", updated_date: "2026-09-20T08:32:00Z",
    fetched_at: "2026-09-20T08:40:00Z",
  } };
  const hass = { locale: { language: "fr" }, config: { time_zone: "Europe/Paris" },
    states: { "sensor.edf_tempo_tomorrow": tomorrow } };
  card.hass = hass;
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<div class="update-info/);
  editor.dispatchEvent = event => card.setConfig(event.detail.config);
  for (const position of ["top", "bottom"]) {
    editor._handleInput({ target: { id: "update_info", value: position } });
    editor._handleInput({ target: { id: "title", value: "Tempo" } });
    const html = card.shadowRoot.innerHTML;
    assert.match(html, /Demain · Mise à jour RTE : 20\/09\/2026.*10:32/);
    assert.match(html, /Dernière récupération réussie : 20\/09\/2026.*10:40/);
    const infoIndex = html.indexOf('<div class="update-info');
    assert.ok(infoIndex > html.indexOf('<div class="title">'));
    if (position === "top") assert.ok(infoIndex < html.indexOf('<div class="grid '));
    if (position === "bottom") assert.ok(infoIndex > html.lastIndexOf('</section>'));
  }
  card.hass = { ...hass, locale: { language: "en" }, config: { time_zone: "UTC" } };
  assert.match(card.shadowRoot.innerHTML, /Tomorrow · RTE update : 20\/09\/2026.*08:32/);
  tomorrow.state = "unavailable";
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /Mise à jour RTE : Non disponible/);
  assert.match(card.shadowRoot.innerHTML, /récupération réussie : Non disponible/);
  assert.doesNotMatch(card.shadowRoot.innerHTML, /20\/09\/2026/);
  tomorrow.state = "unknown";
  tomorrow.attributes.updated_date = null;
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /récupération réussie : 20\/09\/2026.*10:40/);
  tomorrow.attributes.updated_date = null;
  tomorrow.attributes.fetched_at = "invalid";
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /Mise à jour RTE : Non disponible/);
  assert.match(card.shadowRoot.innerHTML, /récupération réussie : Non disponible/);
  editor._handleInput({ target: { id: "update_info", value: "hidden" } });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<div class="update-info/);
});

test("daily editor keeps the open selector intact and saves its first selection", () => {
  const { DailyEditor } = loadCardClasses();
  const editor = new DailyEditor();
  editor.setConfig({});
  editor.hass = { locale: { language: "fr" }, states: {} };
  assert.match(editor.shadowRoot.innerHTML, />Sous le titre</);
  let renders = 0;
  const render = editor._render.bind(editor);
  editor._render = () => { renders++; render(); };
  const events = [];
  editor.dispatchEvent = event => {
    events.push(event);
    editor.setConfig(event.detail.config);
    editor.hass = { locale: { language: "fr" }, states: {} };
  };

  // HA sends new state objects while the native select is open.
  editor.hass = { locale: { language: "fr" }, states: { unrelated: {} } };
  assert.equal(renders, 0);
  const target = { id: "update_info", value: "bottom" };
  editor.shadowRoot.dispatchEvent({ type: "input", target });
  editor.shadowRoot.dispatchEvent({ type: "change", target });
  assert.equal(events.length, 1);
  assert.equal(events[0].detail.config.update_info, "bottom");
  assert.equal(editor._config.update_info, "bottom");
  assert.equal(renders, 0);
  assert.equal(editor.shadowRoot.querySelector("#tomorrow_entity").hass, editor._hass);
});

test("day selection enforces a non-empty layout and preserves editor preferences", () => {
  const { DailyCard, DailyEditor } = loadCardClasses();
  const editor = new DailyEditor();
  const card = new DailyCard();
  editor.setConfig({ columns: 2, update_info: "bottom" });
  editor.dispatchEvent = event => {
    editor.setConfig(event.detail.config);
    card.setConfig(event.detail.config);
  };
  for (const days of ["today", "tomorrow", "both"]) {
    editor.shadowRoot.dispatchEvent({ type: "change", target: { id: "display_days", value: days } });
    const html = card.shadowRoot.innerHTML;
    const columns = editor.shadowRoot.querySelector("#columns");
    const info = editor.shadowRoot.querySelector("#update_info");
    assert.equal((html.match(/<section class="panel /g) || []).length, days === "both" ? 2 : 1);
    assert.equal(html.includes('<div class="label">Today</div>'), days !== "tomorrow");
    assert.equal(html.includes('<div class="label">Tomorrow</div>'), days !== "today");
    assert.equal(html.includes('<div class="update-info'), days !== "today");
    assert.equal(columns.disabled, days !== "both");
    assert.equal(columns.value, days === "both" ? 2 : 1);
    assert.equal(info.disabled, days === "today");
    assert.equal(info.value, days === "today" ? "hidden" : "bottom");
    assert.equal(card._config.columns, 2);
    assert.match(html, days === "both" ? /repeat\(2, minmax/ : /repeat\(1, minmax/);
  }
  for (const value of [undefined, null, "none", [], false]) {
    card.setConfig({ display_days: value });
    assert.equal(card._config.display_days, "both");
    assert.equal((card.shadowRoot.innerHTML.match(/<section class="panel /g) || []).length, 2);
  }
  card.setConfig({ display_days: "today", columns: 1 });
  assert.equal(card.getCardSize(), 2);
  card.setConfig({ display_days: "both", columns: 1 });
  assert.equal(card.getCardSize(), 4);
});

test("entity-based card editors use Home Assistant sensor pickers", () => {
  const { DailyEditor, SeasonEditor } = loadCardClasses();
  const hass = {
    states: {
      "sensor.edf_tempo_season_summary": {},
      "sensor.edf_tempo_today": {},
      "sensor.edf_tempo_tomorrow": {},
    },
  };

  const dailyEditor = new DailyEditor();
  dailyEditor.setConfig({});
  dailyEditor.hass = hass;

  for (const [fieldId, expectedValue] of [
    ["today_entity", "sensor.edf_tempo_today"],
    ["tomorrow_entity", "sensor.edf_tempo_tomorrow"],
  ]) {
    const picker = dailyEditor.shadowRoot.querySelector(`#${fieldId}`);
    assert.strictEqual(picker.hass, hass);
    assert.equal(picker.value, expectedValue);
    assert.deepEqual(Array.from(picker.includeDomains), ["sensor"]);
    assert.equal(picker.allowCustomEntity, true);
  }
  assert.match(dailyEditor.shadowRoot.innerHTML, /<ha-entity-picker id="today_entity">/);
  assert.match(dailyEditor.shadowRoot.innerHTML, /<ha-entity-picker id="tomorrow_entity">/);

  const seasonEditor = new SeasonEditor();
  seasonEditor.setConfig({});
  seasonEditor.hass = hass;

  const seasonPicker = seasonEditor.shadowRoot.querySelector("#entity");
  assert.strictEqual(seasonPicker.hass, hass);
  assert.equal(seasonPicker.value, "sensor.edf_tempo_season_summary");
  assert.deepEqual(Array.from(seasonPicker.includeDomains), ["sensor"]);
  assert.equal(seasonPicker.allowCustomEntity, true);
  assert.match(seasonEditor.shadowRoot.innerHTML, /<ha-entity-picker id="entity">/);
});

test("calendar card editors do not expose irrelevant entity fields", () => {
  const { MonthEditor, SeasonCalendarEditor } = loadCardClasses();

  const seasonCalendarEditor = new SeasonCalendarEditor();
  seasonCalendarEditor.setConfig({});
  assert.doesNotMatch(seasonCalendarEditor.shadowRoot.innerHTML, /entity-picker/);

  const monthEditor = new MonthEditor();
  monthEditor.setConfig({});
  assert.doesNotMatch(monthEditor.shadowRoot.innerHTML, /entity-picker/);
});

test("card editors expose explicit French labels", () => {
  const { DailyEditor, MonthEditor, SeasonCalendarEditor, SeasonCard, SeasonEditor } =
    loadCardClasses("fr-FR");

  const dailyEditor = new DailyEditor();
  dailyEditor.setConfig({});
  dailyEditor.hass = { locale: { language: "fr" }, states: {} };
  assert.match(dailyEditor.shadowRoot.innerHTML, />Titre</);
  assert.match(dailyEditor.shadowRoot.innerHTML, />Entité d'aujourd'hui</);
  assert.match(dailyEditor.shadowRoot.innerHTML, />Entité de demain</);
  for (const label of ["Jours à afficher", "Aujourd’hui et demain", "Aujourd’hui uniquement", "Demain uniquement"]) {
    assert.ok(dailyEditor.shadowRoot.innerHTML.includes(`>${label}<`));
  }

  const seasonEditor = new SeasonEditor();
  seasonEditor.setConfig({});
  seasonEditor.hass = { locale: { language: "fr" }, states: {} };
  assert.match(seasonEditor.shadowRoot.innerHTML, />Entité de synthèse de la saison</);

  const calendarEditor = new SeasonCalendarEditor();
  calendarEditor.setConfig({});
  calendarEditor.hass = { locale: { language: "fr" } };
  assert.match(calendarEditor.shadowRoot.innerHTML, />Colonnes</);

  const monthEditor = new MonthEditor();
  monthEditor.setConfig({});
  monthEditor.hass = { locale: { language: "fr" } };
  assert.match(monthEditor.shadowRoot.innerHTML, /Cette carte utilise automatiquement/);

  const seasonCard = new SeasonCard();
  seasonCard._hass = { locale: { language: "fr" } };
  const model = seasonCard._buildSeasonModel({
    attributes: {
      season_start: "2025-09-01",
      season_end: "2026-08-31",
      blue_days: 1,
      white_days: 1,
      red_days: 1,
    },
  });
  assert.match(model.seasonLabel, /1 septembre 2025 au 31 août 2026/);
  assert.equal(model.blueRow.label, "Jours bleus");
});

test("card editors and season content are fully localized in English", () => {
  const { DailyEditor, MonthEditor, SeasonCalendarEditor, SeasonCard, SeasonEditor } =
    loadCardClasses("en-GB");
  const englishHass = { locale: { language: "en" }, states: {} };

  const dailyEditor = new DailyEditor();
  dailyEditor.setConfig({});
  dailyEditor.hass = englishHass;
  assert.match(dailyEditor.shadowRoot.innerHTML, />Title</);
  assert.match(dailyEditor.shadowRoot.innerHTML, />Today's entity</);
  assert.match(dailyEditor.shadowRoot.innerHTML, />Tomorrow's entity</);
  for (const label of ["Columns", "Tomorrow: update information", "Hidden", "Below the title", "Below the days"]) {
    assert.ok(dailyEditor.shadowRoot.innerHTML.includes(`>${label}<`));
  }
  for (const label of ["Days to display", "Today and tomorrow", "Today only", "Tomorrow only"]) {
    assert.ok(dailyEditor.shadowRoot.innerHTML.includes(`>${label}<`));
  }
  assert.doesNotMatch(dailyEditor.shadowRoot.innerHTML, />Titre</);

  const seasonEditor = new SeasonEditor();
  seasonEditor.setConfig({});
  seasonEditor.hass = englishHass;
  assert.match(seasonEditor.shadowRoot.innerHTML, />Season summary entity</);

  const calendarEditor = new SeasonCalendarEditor();
  calendarEditor.setConfig({});
  calendarEditor.hass = englishHass;
  assert.match(calendarEditor.shadowRoot.innerHTML, />Columns</);

  const monthEditor = new MonthEditor();
  monthEditor.setConfig({});
  monthEditor.hass = englishHass;
  assert.match(monthEditor.shadowRoot.innerHTML, /This card automatically uses/);

  const seasonCard = new SeasonCard();
  seasonCard._hass = englishHass;
  const model = seasonCard._buildSeasonModel({
    attributes: {
      season_start: "2025-09-01",
      season_end: "2026-08-31",
      blue_days: 1,
      white_days: 1,
      red_days: 1,
    },
  });
  assert.match(model.seasonLabel, /1 September 2025 to 31 August 2026/);
  assert.equal(model.blueRow.label, "Blue days");
  assert.equal(model.whiteRow.label, "White days");
  assert.equal(model.redRow.label, "Red days");
});

test("season calendar loads rapid navigation requests per season", async () => {
  const { SeasonCalendarCard } = loadCardClasses();
  const requests = [];
  const card = new SeasonCalendarCard();
  card._render = () => {};
  card._hass = fakeHass(requests);
  card._currentSeasonStartYear = 2025;
  card._selectedSeasonStartYear = 2025;

  const firstLoad = card._ensureSeasonData(2025);
  card._navigate(-1);
  const secondLoad = card._pendingLoads.get(2024);
  card._navigate(-1);
  const selectedLoad = card._pendingLoads.get(2023);
  const duplicateLoad = card._ensureSeasonData(2024);

  assert.strictEqual(secondLoad, duplicateLoad);
  assert.equal(card._selectedSeasonStartYear, 2023);
  assert.equal(card._pendingLoads.size, 3);
  await Promise.resolve();
  assert.deepEqual(
    requests.map((request) => request.message.season_start_year),
    [2025, 2024, 2023],
  );

  const firstResult = {
    current_season_start_year: 2025,
    min_season_start_year: 2015,
    day_colors: { "2025-09-01": "BLUE" },
  };
  requests[0].resolve(firstResult);
  await firstLoad;
  assert.equal(card._seasonData, null);

  const selectedResult = {
    current_season_start_year: 2025,
    min_season_start_year: 2015,
    day_colors: { "2024-09-01": "RED" },
  };
  requests[1].resolve(selectedResult);
  await secondLoad;
  assert.equal(card._seasonData, null);

  const finalSelectedResult = {
    current_season_start_year: 2025,
    min_season_start_year: 2015,
    day_colors: { "2023-09-01": "WHITE" },
  };
  requests[2].resolve(finalSelectedResult);
  await selectedLoad;

  assert.strictEqual(card._seasonData, finalSelectedResult);
  assert.strictEqual(card._seasonCache.get(2025), firstResult);
  assert.strictEqual(card._seasonCache.get(2024), selectedResult);
  assert.strictEqual(card._seasonCache.get(2023), finalSelectedResult);
  assert.equal(card._pendingLoads.size, 0);
});

test("monthly calendar loads both seasons during rapid boundary navigation", async () => {
  const { MonthCard } = loadCardClasses();
  const requests = [];
  const card = new MonthCard();
  card._render = () => {};
  card._hass = fakeHass(requests);
  card._currentMonth = { year: 2026, monthIndex: 9 };
  card._selectedMonth = { year: 2026, monthIndex: 7 };

  const augustLoad = card._ensureMonthData({ year: 2026, monthIndex: 7 });
  card._navigate(1);
  const septemberLoad = card._pendingLoads.get(2026);
  card._navigate(1);
  const duplicateSeptemberLoad = card._pendingLoads.get(2026);

  assert.strictEqual(septemberLoad, duplicateSeptemberLoad);
  assert.equal(card._selectedMonth.year, 2026);
  assert.equal(card._selectedMonth.monthIndex, 9);
  assert.equal(card._pendingLoads.size, 2);
  await Promise.resolve();
  assert.deepEqual(
    requests.map((request) => request.message.season_start_year),
    [2025, 2026],
  );

  const previousSeason = { day_colors: { "2026-08-31": "WHITE" } };
  requests[0].resolve(previousSeason);
  await augustLoad;
  assert.equal(card._seasonData, null);

  const selectedSeason = { day_colors: { "2026-09-01": "RED" } };
  requests[1].resolve(selectedSeason);
  await septemberLoad;

  assert.strictEqual(card._seasonData, selectedSeason);
  assert.strictEqual(card._seasonCache.get(2025), previousSeason);
  assert.strictEqual(card._seasonCache.get(2026), selectedSeason);
  assert.equal(card._pendingLoads.size, 0);
});
