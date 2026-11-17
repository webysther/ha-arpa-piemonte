// Tests of the ARPA Piemonte card: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CARD,
  DEFAULTS,
  cardLayout,
  checkConfig,
  cleanConfig,
  columnsOf,
  editorData,
  editorSchema,
  stationLayout,
  stationOf,
} from "../../custom_components/arpa_piemonte/frontend/arpa-piemonte-card.js";
import { findStations } from "../../custom_components/arpa_piemonte/frontend/arpa-piemonte-dashboard.js";
import { entityId, homeAssistant } from "./fixtures.mjs";

/** The texts of the integration a frontend in Italian has. */
const ITALIAN = {
  "component.arpa_piemonte.entity.sensor.level.name": "Livello idrometrico",
  "component.arpa_piemonte.entity.sensor.last_measurement.name": "Ultima misura",
  "component.arpa_piemonte.entity.binary_sensor.flood_risk.name": "Rischio di piena",
};

/** Return the station of a Home Assistant by the ID of its device. */
const stationIn = (hass, id) => stationOf(findStations(hass), { device_id: id });

/** Return the native cards of a station, as the card places them. */
const layoutOf = (id, config = {}, hass = homeAssistant()) =>
  stationLayout(hass, stationIn(hass, id), config);

/** Return the cards of a layout, without where they go. */
const cardsOf = (placed) => placed.map(({ card }) => card);

describe("card", () => {
  it("shows the station of its device, or the first one", () => {
    const stations = findStations(homeAssistant());

    assert.equal(stationOf(stations, { device_id: "colle" })?.name, "Colle Lombarda");
    assert.equal(stationOf(stations, {})?.name, "Baceno Devero");
    assert.equal(stationOf(stations, { device_id: "removed" }), undefined);
  });

  it("is made of native cards: a heading, the level, the readings and the charts", () => {
    const placed = layoutOf("pray");

    assert.deepEqual(
      placed.map(({ card, column }) => [
        card.type,
        card.entity?.split("_sessera_")[1] ?? null,
        column,
      ]),
      [
        ["heading", null, "all"],
        ["tile", "level_status", "all"],
        ["gauge", "level", "all"],
        ["tile", "temperature", "cell"],
        ["tile", "rain_1h", "cell"],
        ["tile", "rain_3h", "cell"],
        ["tile", "rain_24h", "cell"],
        // The chart of the temperature has no data yet
        ["picture-entity", "level_chart", "all"],
        ["picture-entity", "rain_chart", "all"],
      ],
    );
  });

  it("heads with the station, its flood risk in the color of its level, and its last measurement", () => {
    const [{ card }] = layoutOf("pray");

    assert.deepEqual(card, {
      type: "heading",
      heading: "Pray Sessera",
      icon: "mdi:waves-arrow-up",
      badges: [
        {
          type: "entity",
          entity: entityId("pray", "binary_sensor", "flood_risk"),
          color: "#90c985",
        },
        { type: "entity", entity: entityId("pray", "sensor", "last_measurement") },
      ],
    });
  });

  it("colors the level status and the flood risk as the level is now", () => {
    const hass = homeAssistant({
      states: {
        [entityId("pray", "sensor", "level_status")]: "guard",
        [entityId("pray", "binary_sensor", "flood_risk")]: "on",
      },
    });

    const [heading, status] = cardsOf(layoutOf("pray", {}, hass));

    assert.equal(heading.badges[0].color, "#f0bf01");
    assert.equal(status.color, "#f0bf01");
  });

  it("leaves the level status without color when it is not known", () => {
    const hass = homeAssistant({
      states: { [entityId("pray", "sensor", "level_status")]: "unavailable" },
    });

    const [heading, status] = cardsOf(layoutOf("pray", {}, hass));

    assert.equal(heading.badges[0].color, undefined);
    assert.equal(status.color, undefined);
  });

  it("shows the source of the readings when it is not Meteo 3R", () => {
    const [{ card }] = layoutOf("colle");

    assert.deepEqual(card.badges, [
      { type: "entity", entity: entityId("colle", "sensor", "last_measurement") },
      { type: "entity", entity: entityId("colle", "sensor", "data_source") },
    ]);
    assert.equal(card.icon, "mdi:weather-partly-rainy");
  });

  it("has the gauge of the level with the thresholds", () => {
    const gauge = cardsOf(layoutOf("pray")).find((card) => card.type === "gauge");

    assert.equal(gauge.max, 4.75);
    assert.equal(gauge.segments.length, 4);
  });

  it("has the tile of the level, without status, for a hydrometer without thresholds", () => {
    const cards = cardsOf(layoutOf("devero"));

    assert.deepEqual(
      cards.map((card) => [card.type, card.entity?.split("_devero_")[1] ?? null]),
      [
        ["heading", null],
        ["tile", "level"],
      ],
    );
  });

  it("asks for a station when there is none", () => {
    const hass = { ...homeAssistant(), entities: {}, locale: { language: "pt-BR" } };

    const [{ card, column }] = cardLayout(hass, findStations(hass), {});

    assert.equal(card.type, "markdown");
    assert.match(card.content, /Adicione uma estação/);
    assert.equal(column, "all");
  });

  it("shows the station of its configuration", () => {
    const hass = homeAssistant();

    const [{ card }] = cardLayout(hass, findStations(hass), { device_id: "colle" });

    assert.equal(card.heading, "Colle Lombarda");
  });
});

describe("card of a station with a barometer and a radiometer", () => {
  it("shows the pressure and the solar radiation with the readings, and their charts", () => {
    const extra = ["pressure", "solar_radiation", "pressure_chart", "radiation_chart"].map(
      (key) => ({
        entity_id: entityId("colle", key.endsWith("_chart") ? "image" : "sensor", key),
        platform: "arpa_piemonte",
        device_id: "colle",
        translation_key: key,
      }),
    );
    const hass = homeAssistant({
      entities: extra,
      states: { [entityId("colle", "image", "pressure_chart")]: "2026-11-17T02:00:00+00:00" },
    });

    const placed = layoutOf("colle", {}, hass);

    const keys = placed.map(({ card }) => card.entity?.split("_lombarda_")[1]);
    assert.deepEqual(keys.slice(-3), ["pressure", "solar_radiation", "pressure_chart"]);
    assert.equal(placed.at(-3).column, "cell");
    assert.equal(placed.at(-1).column, "all");
  });
});

describe("options of the card", () => {
  it("show the badges without the title, and no heading without either", () => {
    const [{ card }] = layoutOf("pray", { show_title: false });
    assert.equal(card.heading, "");
    assert.equal(card.icon, undefined);
    assert.equal(card.badges.length, 2);

    const none = layoutOf("pray", {
      show_title: false,
      show_flood_risk: false,
      show_last_measurement: false,
    });
    assert.notEqual(none[0].card.type, "heading");
  });

  it("show only the parts chosen", () => {
    const types = (config) => cardsOf(layoutOf("pray", config)).map((card) => card.type);

    assert.deepEqual(types({ show_level: false }), [
      "heading",
      "tile",
      "tile",
      "tile",
      "tile",
      "picture-entity",
      "picture-entity",
    ]);
    assert.deepEqual(types({ show_readings: false, show_charts: false }), [
      "heading",
      "tile",
      "gauge",
    ]);
  });

  it("set the columns of the readings", () => {
    assert.equal(columnsOf({}), "minmax(0, 1fr) minmax(0, 1fr)");
    assert.equal(columnsOf({ columns: 1 }), "minmax(0, 1fr)");
  });

  it("are checked", () => {
    assert.doesNotThrow(() =>
      checkConfig({ type: `custom:${CARD}`, device_id: "pray", columns: 1 }),
    );
    assert.throws(() => checkConfig({ device_id: 3 }), /device_id/);
    assert.throws(() => checkConfig({ show_charts: "yes" }), /show_charts/);
    assert.throws(() => checkConfig({ columns: 3 }), /columns/);
  });
});

describe("visual editor", () => {
  const hass = {
    ...homeAssistant(),
    localize: (key) => ITALIAN[key] ?? "",
    locale: { language: "it" },
  };
  const stations = findStations(hass);

  it("has the station, the heading, the content and the columns, labeled in the language of the user", () => {
    const fields = editorSchema(hass, stations, {});

    assert.deepEqual(
      fields.map((field) => [field.name, field.label]),
      [
        ["device_id", "Stazione"],
        ["heading", "Intestazione"],
        ["content", "Contenuto"],
        ["columns", "Colonne"],
      ],
    );
    assert.deepEqual(fields[1].selector.select.options, [
      { value: "title", label: "Titolo" },
      { value: "flood_risk", label: "Rischio di piena" },
      { value: "last_measurement", label: "Ultima misura" },
    ]);
    assert.deepEqual(fields[2].selector.select.options, [
      { value: "level", label: "Livello idrometrico" },
      { value: "readings", label: "Misure" },
      { value: "charts", label: "Grafici" },
    ]);
  });

  it("offers the stations by name, and keeps one that is gone by its ID", () => {
    const [field] = editorSchema(hass, stations, { device_id: "gone" });

    assert.deepEqual(
      field.selector.select.options.map((option) => option.label),
      ["Baceno Devero", "Pray Sessera", "Alpe Devero", "Colle Lombarda", "gone"],
    );
  });

  it("labels by key what the frontend has no text of", () => {
    const fields = editorSchema({ ...hass, localize: undefined }, stations, {});

    assert.equal(fields[1].selector.select.options[1].label, "flood_risk");
  });

  it("starts from what the card shows", () => {
    assert.deepEqual(editorData(stations, {}), {
      ...DEFAULTS,
      device_id: "devero",
      heading: ["title", "flood_risk", "last_measurement"],
      content: ["level", "readings", "charts"],
      columns: "2",
    });
    const data = editorData(stations, { device_id: "pray", show_charts: false, columns: 1 });
    assert.deepEqual(data.content, ["level", "readings"]);
    assert.equal(data.columns, "1");
    assert.equal(editorData([], {}).device_id, undefined);
  });

  it("keeps in the configuration only what differs from what the card shows anyway", () => {
    const value = {
      ...editorData(stations, { device_id: "pray" }),
      heading: ["title"],
      content: ["level", "charts"],
      columns: "1",
    };

    assert.deepEqual(cleanConfig(value), {
      device_id: "pray",
      show_flood_risk: false,
      show_last_measurement: false,
      show_readings: false,
      columns: 1,
    });
    assert.deepEqual(cleanConfig({ device_id: "pray", columns: "2" }), { device_id: "pray" });
  });
});
