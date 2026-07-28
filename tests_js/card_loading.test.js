"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadCardClasses() {
  const registeredElements = new Map();

  class FakeHTMLElement {
    constructor() {
      this.shadowRoot = null;
      this.style = { setProperty() {} };
    }

    attachShadow() {
      const elements = new Map();
      this.shadowRoot = {
        addEventListener() {},
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
    CustomEvent: class CustomEvent {},
    Date,
    HTMLElement: FakeHTMLElement,
    Intl,
    Map,
    navigator: { language: "fr-FR" },
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
    DailyEditor: registeredElements.get("edf-tempo-card-editor"),
    MonthCard: registeredElements.get("edf-tempo-month-card"),
    MonthEditor: registeredElements.get("edf-tempo-month-card-editor"),
    SeasonCalendarEditor: registeredElements.get("edf-tempo-season-calendar-card-editor"),
    SeasonCalendarCard: registeredElements.get("edf-tempo-season-calendar-card"),
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
    assert.deepEqual(picker.includeDomains, ["sensor"]);
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
  assert.deepEqual(seasonPicker.includeDomains, ["sensor"]);
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
