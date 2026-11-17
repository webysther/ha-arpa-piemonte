// Tests of the ARPA Piemonte dashboard strategy: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  LEVEL_STATUS_COLORS,
  colorByState,
  dashboardSuggestion,
  entityName,
  findStations,
  generateDashboard,
  generateView,
  isAtLeast,
  levelGauge,
  municipalitiesOf,
  municipalityEntries,
  numberOf,
  slugify,
  stationCode,
  stationSection,
  textsIn,
  thresholdsOf,
  tile,
  withTexts,
} from "../../custom_components/arpa_piemonte/frontend/arpa-piemonte-dashboard.js";
import { ENTRIES, entityId, homeAssistant, stationDevice, stationEntities } from "./fixtures.mjs";

/** The texts of the integration in Portuguese, some of them. */
const PORTUGUESE = {
  "component.arpa_piemonte.entity.sensor.level.name": "Nível do rio",
  "component.arpa_piemonte.entity.sensor.level_status.name": "Situação do nível",
  "component.arpa_piemonte.entity.sensor.rain_24h.name": "Chuva 24 horas",
};

/** Return a Home Assistant whose frontend loads the texts of the integration in Portuguese. */
function portuguese(hass) {
  return {
    ...hass,
    loadBackendTranslation: async (category, integration) => {
      assert.equal(category, "entity");
      assert.equal(integration, "arpa_piemonte");
      return (key) => PORTUGUESE[key] ?? "";
    },
  };
}

/** Return the station of a Home Assistant by the ID of its device. */
const stationIn = (hass, id) => findStations(hass).find((station) => station.device.id === id);

/** Return the section of a station of the default Home Assistant. */
const sectionOf = (id, hass = homeAssistant()) => stationSection(hass, stationIn(hass, id));

/** Return the cards of a section for an entity. */
const cardsFor = (section, entity) => section.cards.filter((card) => card.entity === entity);

describe("dashboard", () => {
  it("has a tab per municipality, sorted by name, from the entries of the integration", async () => {
    assert.deepEqual((await generateDashboard(homeAssistant())).views, [
      {
        title: "Baceno",
        path: "baceno",
        strategy: { type: "custom:arpa-piemonte", entry_id: "baceno_entry" },
      },
      {
        title: "Pray",
        path: "pray",
        strategy: { type: "custom:arpa-piemonte", entry_id: "pray_entry" },
      },
      {
        title: "Vinadio",
        path: "vinadio",
        strategy: { type: "custom:arpa-piemonte", entry_id: "vinadio_entry" },
      },
    ]);
  });

  it("names a municipality after its first station without its entry", async () => {
    const hass = homeAssistant({ entries: ENTRIES.filter(({ title }) => title !== "Vinadio") });

    const titles = (await generateDashboard(hass)).views.map((view) => view.title);

    assert.deepEqual(titles, ["Baceno", "Colle Lombarda", "Pray"]);
  });

  it("names the municipalities after their stations when the websocket fails or is missing", async () => {
    const failing = { ...homeAssistant(), callWS: async () => Promise.reject(new Error("no")) };
    const missing = { ...homeAssistant(), callWS: undefined };

    for (const hass of [failing, missing]) {
      assert.deepEqual(await municipalityEntries(hass), []);
      const titles = (await generateDashboard(hass)).views.map((view) => view.title);
      assert.deepEqual(titles, ["Baceno Devero", "Colle Lombarda", "Pray Sessera"]);
    }
  });

  it("gives municipalities of the same name different paths", async () => {
    const hass = homeAssistant({
      entries: ENTRIES.map((entry) => ({ ...entry, title: "Mondovì" })),
    });

    const paths = (await generateDashboard(hass)).views.map((view) => view.path);

    assert.deepEqual(paths, ["mondovi", "mondovi-2", "mondovi-3"]);
  });

  it("asks for a station when there is none, in the language of the user", async () => {
    const hass = { ...homeAssistant(), entities: {}, locale: { language: "it" } };

    const [view] = (await generateDashboard(hass)).views;

    assert.equal(view.type, "panel");
    assert.match(view.cards[0].content, /Aggiungi una stazione/);
  });

  it("has a section per station of the municipality, the hydrometers first", () => {
    const view = generateView({ entry_id: "baceno_entry" }, homeAssistant());

    assert.equal(view.type, "sections");
    assert.equal(view.max_columns, 3);
    assert.deepEqual(
      view.sections.map((section) => section.cards[0].heading),
      ["Baceno Devero", "Alpe Devero"],
    );
  });

  it("asks for a station in a view without stations", () => {
    const view = generateView({ entry_id: "gone" }, homeAssistant());

    assert.equal(view.type, "panel");
  });

  it("is suggested with its name and icon", () => {
    assert.deepEqual(dashboardSuggestion("pt-BR"), {
      title: "ARPA Piemonte",
      icon: "mdi:waves-arrow-up",
    });
  });
});

describe("stations", () => {
  it("are the devices of the visible entities of the integration", () => {
    const hass = homeAssistant({
      entities: [
        { entity_id: "sensor.hidden", platform: "arpa_piemonte", device_id: "pray", hidden: true },
        { entity_id: "sensor.loose", platform: "arpa_piemonte", device_id: null },
        { entity_id: "sensor.elsewhere", platform: "arpa_piemonte", device_id: "nowhere" },
      ],
    });

    assert.deepEqual(
      findStations(hass).map((station) => station.name),
      ["Baceno Devero", "Pray Sessera", "Alpe Devero", "Colle Lombarda"],
    );
  });

  it("leave out devices of the integration that are not stations", () => {
    const hass = homeAssistant({
      entities: [
        { entity_id: "sensor.risk", platform: "arpa_piemonte", device_id: "municipality" },
      ],
    });
    hass.devices.municipality = {
      id: "municipality",
      identifiers: [["arpa_piemonte", "ISTAT_096050"]],
    };

    assert.equal(findStations(hass).length, 4);
    assert.equal(stationCode(hass.devices.municipality), undefined);
  });

  it("know their code, municipality and entities, and the name the user gave them", () => {
    const hass = homeAssistant();
    hass.devices.pray.name_by_user = "Sessera a Pray";
    const pray = stationIn(hass, "pray");

    assert.equal(pray.code, "188");
    assert.equal(pray.name, "Sessera a Pray");
    assert.equal(pray.municipality, "pray_entry");
    assert.equal(pray.isHydrometer, true);
    assert.equal(pray.entity("sensor", "level"), "sensor.arpa_piemonte_pray_sessera_level");
    assert.equal(pray.entity("sensor", "wind_speed"), undefined);
  });

  it("are named by their code without a name", () => {
    const device = { ...stationDevice("pray"), name: null };
    const hass = { ...homeAssistant(), devices: { pray: device } };

    assert.equal(stationIn(hass, "pray").name, "188");
  });

  it("are grouped by municipality", () => {
    const municipalities = municipalitiesOf(findStations(homeAssistant()), ENTRIES);

    assert.deepEqual(
      municipalities.map(({ name, stations }) => [name, stations.map((station) => station.code)]),
      [
        ["Baceno", ["S4059", "154"]],
        ["Pray", ["188"]],
        ["Vinadio", ["001"]],
      ],
    );
  });

  it("without the entry of their municipality are grouped together", () => {
    const hass = homeAssistant();
    hass.devices.pray.config_entries = [];
    hass.devices.colle.config_entries = [];

    const views = generateView({}, hass);

    assert.deepEqual(
      views.sections.map((section) => section.cards[0].heading),
      ["Pray Sessera", "Colle Lombarda"],
    );
  });
});

describe("section of a hydrometer", () => {
  const level = entityId("pray", "sensor", "level");
  const status = entityId("pray", "sensor", "level_status");
  const floodRisk = entityId("pray", "binary_sensor", "flood_risk");

  it("heads with the station, its flood risk in the color of its level, and its last measurement", () => {
    const [heading] = sectionOf("pray").cards;

    assert.equal(heading.type, "heading");
    assert.equal(heading.heading, "Pray Sessera");
    assert.equal(heading.icon, "mdi:waves-arrow-up");
    const risks = heading.badges.filter((badge) => badge.entity === floodRisk);
    assert.deepEqual(
      Object.fromEntries(
        risks
          .filter((badge) => badge.color)
          .map((badge) => [badge.visibility[0].state, badge.color]),
      ),
      LEVEL_STATUS_COLORS,
    );
    assert.deepEqual(risks.at(-1).visibility, [
      { condition: "state", entity: status, state_not: Object.keys(LEVEL_STATUS_COLORS) },
    ]);
    assert.ok(
      heading.badges.some(
        (badge) => badge.entity === entityId("pray", "sensor", "last_measurement"),
      ),
    );
  });

  it("shows the source of the readings only when it is not Meteo 3R", () => {
    const [heading] = sectionOf("pray").cards;
    const source = entityId("pray", "sensor", "data_source");

    assert.deepEqual(
      heading.badges.find((badge) => badge.entity === source),
      {
        type: "entity",
        entity: source,
        visibility: [
          {
            condition: "state",
            entity: source,
            state_not: ["meteo3r", "unknown", "unavailable"],
          },
        ],
      },
    );
  });

  it("colors the level status with the colors of the alert maps", () => {
    const tiles = cardsFor(sectionOf("pray"), status);

    assert.deepEqual(
      tiles.map((card) => [card.visibility[0].state ?? "other", card.color ?? null]),
      [
        ["normal", "#90c985"],
        ["pre_alarm", "#f8f865"],
        ["guard", "#f0bf01"],
        ["danger", "#fd6767"],
        ["other", null],
      ],
    );
    assert.deepEqual(tiles[0].grid_options, { columns: 12 });
  });

  it("has a gauge of the level, with a band above each threshold, up to the highest and a quarter", () => {
    const [gauge] = cardsFor(sectionOf("pray"), level);

    assert.deepEqual(gauge, {
      type: "gauge",
      entity: level,
      min: 0,
      max: 4.75,
      needle: true,
      segments: [
        { from: 0, color: "#90c985" },
        { from: 2.3, color: "#f8f865" },
        { from: 3, color: "#f0bf01" },
        { from: 3.8, color: "#fd6767" },
      ],
      grid_options: { columns: 12 },
    });
  });

  it("raises the top of the gauge to a level above it, and lowers its bottom below 0", () => {
    const hass = homeAssistant({ states: { [level]: "5.2" } });
    assert.equal(levelGauge(hass, stationIn(hass, "pray")).max, 5.2);

    const low = homeAssistant({ states: { [level]: "-0.35" } });
    const gauge = levelGauge(low, stationIn(low, "pray"));
    assert.equal(gauge.min, -1);
    assert.deepEqual(gauge.segments[0], { from: -1, color: "#90c985" });
  });

  it("has bands only for the thresholds with a value", () => {
    const hass = homeAssistant({
      states: { [entityId("pray", "sensor", "guard_threshold")]: "unavailable" },
    });

    const gauge = levelGauge(hass, stationIn(hass, "pray"));

    assert.deepEqual(
      gauge.segments.map((segment) => segment.from),
      [0, 2.3, 3.8],
    );
    assert.equal(gauge.max, 4.75);
  });

  it("names the gauge in the language of the user", async () => {
    const hass = await withTexts(portuguese(homeAssistant()));

    assert.equal(levelGauge(hass, stationIn(hass, "pray")).name, "Nível do rio");
  });

  it("shows the charts that the station has, while they have data", () => {
    const pictures = sectionOf("pray").cards.filter((card) => card.type === "picture-entity");

    assert.deepEqual(
      pictures.map((card) => card.entity),
      ["level_chart", "rain_chart", "temperature_chart"].map((key) =>
        entityId("pray", "image", key),
      ),
    );
    assert.deepEqual(pictures[0], {
      type: "picture-entity",
      entity: entityId("pray", "image", "level_chart"),
      show_name: false,
      show_state: false,
      grid_options: { columns: 12 },
      visibility: [
        {
          condition: "state",
          entity: entityId("pray", "image", "level_chart"),
          state_not: ["unknown", "unavailable"],
        },
      ],
    });
  });

  it("shows the readings, the three rains on a row", () => {
    const tiles = sectionOf("pray").cards.filter(
      (card) => card.type === "tile" && card.entity !== status,
    );

    assert.deepEqual(
      tiles.map((card) => [card.entity.split("_sessera_")[1], card.grid_options.columns]),
      [
        ["temperature", 6],
        ["rain_1h", 4],
        ["rain_3h", 4],
        ["rain_24h", 4],
      ],
    );
  });
});

describe("section of a hydrometer without thresholds", () => {
  it("has the tile of the level, without gauge nor status", () => {
    const section = sectionOf("devero");
    const level = entityId("devero", "sensor", "level");

    assert.deepEqual(cardsFor(section, level), [
      { type: "tile", entity: level, name: { type: "entity" }, grid_options: { columns: 12 } },
    ]);
    assert.deepEqual(cardsFor(section, entityId("devero", "sensor", "level_status")), []);
    assert.ok(!section.cards.some((card) => card.type === "gauge"));
    assert.ok(!section.cards[0].badges.some((badge) => badge.entity.endsWith("_flood_risk")));
  });
});

describe("section of a weather station", () => {
  it("heads with a weather icon, and shows the wind two by two and the snow", () => {
    const section = sectionOf("colle");

    assert.equal(section.cards[0].icon, "mdi:weather-partly-rainy");
    assert.deepEqual(
      section.cards
        .filter((card) => card.type === "tile")
        .map((card) => card.entity.split("_lombarda_")[1]),
      [
        "temperature",
        "humidity",
        "rain_1h",
        "rain_3h",
        "rain_24h",
        "wind_speed",
        "wind_direction",
        "gust_speed",
        "gust_direction",
        "snow_depth",
      ],
    );
    assert.ok(!section.cards.some((card) => card.type === "gauge"));
  });
});

describe("names", () => {
  it("are those of the integration in the language of the user", async () => {
    const hass = await withTexts(portuguese(homeAssistant()));
    const rain = entityId("pray", "sensor", "rain_24h");

    assert.equal(entityName(hass, rain), "Chuva 24 horas");
    assert.deepEqual(tile(hass, rain), { type: "tile", entity: rain, name: "Chuva 24 horas" });
  });

  it("are left to Home Assistant without the texts: the entity alone from 2025.11", async () => {
    const rain = entityId("pray", "sensor", "rain_24h");

    assert.equal(await withTexts(homeAssistant()).then((hass) => hass.localize), undefined);
    assert.deepEqual(tile(homeAssistant(), rain).name, { type: "entity" });
    assert.equal(tile(homeAssistant({ version: "2025.4.0" }), rain).name, undefined);
  });
});

describe("helpers", () => {
  it("color a card by the state of an entity", () => {
    const cards = colorByState({ type: "tile", entity: "a" }, "b", { on: "red" });

    assert.deepEqual(cards, [
      {
        type: "tile",
        entity: "a",
        color: "red",
        visibility: [{ condition: "state", entity: "b", state: "on" }],
      },
      {
        type: "tile",
        entity: "a",
        visibility: [{ condition: "state", entity: "b", state_not: ["on"] }],
      },
    ]);
  });

  it("read numbers from states, none without one", () => {
    const hass = homeAssistant({ states: { "sensor.empty": "" } });

    assert.equal(numberOf(hass, entityId("pray", "sensor", "level")), 0.86);
    assert.equal(numberOf(hass, entityId("devero", "sensor", "level_status")), undefined);
    assert.equal(numberOf(hass, "sensor.empty"), undefined);
    assert.equal(numberOf(hass, "sensor.missing"), undefined);
    assert.equal(
      numberOf({ ...hass, states: undefined }, entityId("pray", "sensor", "level")),
      undefined,
    );
    assert.equal(numberOf(hass, undefined), undefined);
  });

  it("read the thresholds of a station from the lowest", () => {
    const hass = homeAssistant();

    assert.deepEqual(
      thresholdsOf(hass, stationIn(hass, "pray")).map(({ value }) => value),
      [2.3, 3, 3.8],
    );
    assert.deepEqual(thresholdsOf(hass, stationIn(hass, "devero")), []);
  });

  it("compare versions of Home Assistant", () => {
    const hass = (version) => ({ ...homeAssistant(), config: { version } });

    assert.equal(isAtLeast(hass("2025.11.0"), [2025, 11]), true);
    assert.equal(isAtLeast(hass("2026.1.0"), [2025, 11]), true);
    assert.equal(isAtLeast(hass("2025.10.3"), [2025, 11]), false);
    assert.equal(isAtLeast(hass("2024.12.0"), [2025, 11]), false);
  });

  it("make paths of names", () => {
    assert.equal(slugify("Mondovì"), "mondovi");
    assert.equal(slugify("Castiglione d'Asti"), "castiglione-d-asti");
    assert.equal(slugify("···"), "arpa-piemonte");
  });

  it("speak the language of the user, its base language, or English", () => {
    assert.equal(textsIn("it-CH").station, "Stazione");
    assert.equal(textsIn("pt").station, "Estação");
    assert.equal(textsIn("pt-BR").station, "Estação");
    assert.equal(textsIn("de").station, "Station");
    assert.equal(textsIn(undefined).station, "Station");
  });

  it("find the entities of a station by translation key, not by entity ID", () => {
    const entries = stationEntities("pray").map((entry) =>
      entry.translation_key === "level" ? { ...entry, entity_id: "sensor.my_river" } : entry,
    );
    const hass = {
      ...homeAssistant(),
      entities: Object.fromEntries(entries.map((e) => [e.entity_id, e])),
    };

    assert.equal(stationIn(hass, "pray").entity("sensor", "level"), "sensor.my_river");
  });
});
