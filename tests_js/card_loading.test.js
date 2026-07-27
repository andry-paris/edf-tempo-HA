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
      this.shadowRoot = {
        innerHTML: "",
        querySelector() {
          return null;
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
    MonthCard: registeredElements.get("edf-tempo-month-card"),
    SeasonCalendarCard: registeredElements.get("edf-tempo-season-calendar-card"),
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
