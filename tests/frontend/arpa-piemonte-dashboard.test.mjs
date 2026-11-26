// Tests of the Arpa Piemonte dashboard strategy: node --test tests/frontend
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  ALERT_COLORS,
  AVALANCHE_COLORS,
  LEVEL_STATUS_COLORS,
  PHASE_COLORS,
  colorByState,
  dashboardSuggestion,
  earthquakeCards,
  entityName,
  findRisks,
  findStations,
  generateDashboard,
  generateView,
  isAtLeast,
  isRisksDevice,
  levelGauge,
  municipalitiesOf,
  municipalityEntries,
  numberOf,
  risksSection,
  slugify,
  stationCode,
  stationSection,
  textsIn,
  thresholdsOf,
  tile,
  withTexts,
} from "../../custom_components/arpa_piemonte/frontend/arpa-piemonte-dashboard.js";
import {
  ENTRIES,
  entityId,
  homeAssistant,
  riskEntityId,
  stationDevice,
  stationEntities,
} from "./fixtures.mjs";

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

/** Return the risks of a Home Assistant by the ID of their device. */
const risksIn = (hass, id) => findRisks(hass).find((risks) => risks.device.id === id);

/** Return the section of the risks of Pray of a Home Assistant. */
const risksOfPray = (hass = homeAssistant()) => risksSection(hass, risksIn(hass, "pray_risks"));

/** Return the entity ID of an entity of the risks of Pray. */
const prayRisk = (key, domain = "sensor") => riskEntityId("pray_risks", domain, key);

/** Return the section of the risks of Vinadio of a Home Assistant: in a micro-region. */
const risksOfVinadio = (hass = homeAssistant()) =>
  risksSection(hass, risksIn(hass, "vinadio_risks"));

/** Return the entity ID of an entity of the risks of Vinadio. */
const vinadioRisk = (key, domain = "sensor") => riskEntityId("vinadio_risks", domain, key);

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

  it("has the risks of the municipality, then a section per station, the hydrometers first", () => {
    const view = generateView({ entry_id: "baceno_entry" }, homeAssistant());

    assert.equal(view.type, "sections");
    assert.equal(view.max_columns, 3);
    assert.deepEqual(
      view.sections.map((section) => section.cards[0].heading),
      ["Natural risks", "Baceno Devero", "Alpe Devero"],
    );
  });

  it("has a tab for a municipality without stations, with its risks", async () => {
    const hass = homeAssistant();
    hass.entities = Object.fromEntries(
      Object.entries(hass.entities).filter(
        ([, entry]) => !["alpe", "devero"].includes(entry.device_id),
      ),
    );

    const titles = (await generateDashboard(hass)).views.map((view) => view.title);
    const view = generateView({ entry_id: "baceno_entry" }, hass);

    assert.deepEqual(titles, ["Baceno", "Pray", "Vinadio"]);
    assert.deepEqual(
      view.sections.map((section) => section.cards[0].heading),
      ["Natural risks"],
    );
  });

  it("asks for a station in a view without stations", () => {
    const view = generateView({ entry_id: "gone" }, homeAssistant());

    assert.equal(view.type, "panel");
  });

  it("is suggested with its name and icon", () => {
    assert.deepEqual(dashboardSuggestion("pt-BR"), {
      title: "Arpa Piemonte",
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

describe("risks", () => {
  it("are the devices of the risks of the municipalities, not stations", () => {
    const hass = homeAssistant();

    assert.deepEqual(
      findRisks(hass).map((risks) => [risks.name, risks.municipality]),
      [
        ["Pray · Natural risks", "pray_entry"],
        ["Vinadio · Natural risks", "vinadio_entry"],
        ["Baceno · Natural risks", "baceno_entry"],
      ],
    );
    assert.equal(isRisksDevice(hass.devices.pray_risks), true);
    assert.equal(isRisksDevice(hass.devices.pray), false);
    assert.equal(findStations(hass).length, 4);
  });

  it("are named as the user named their device, or by its ID", () => {
    const hass = homeAssistant();
    hass.devices.pray_risks.name_by_user = "Allerta Pray";
    hass.devices.vinadio_risks.name = null;

    assert.equal(risksIn(hass, "pray_risks").name, "Allerta Pray");
    assert.equal(risksIn(hass, "vinadio_risks").name, "vinadio_risks");
  });

  it("name a municipality without its entry nor stations", () => {
    const hass = homeAssistant();

    const municipalities = municipalitiesOf([], [], findRisks(hass));

    assert.deepEqual(
      municipalities.map(({ name, stations }) => [name, stations.length]),
      [
        ["Baceno · Natural risks", 0],
        ["Pray · Natural risks", 0],
        ["Vinadio · Natural risks", 0],
      ],
    );
  });

  it("head with the alert zone, the time of the bulletin and the heat-wave city", () => {
    const [heading] = risksOfPray().cards;

    assert.deepEqual(heading, {
      type: "heading",
      heading: "Natural risks",
      icon: "mdi:shield-alert",
      badges: [
        { type: "entity", entity: prayRisk("alert_zone") },
        { type: "entity", entity: prayRisk("alert_bulletin") },
        { type: "entity", entity: prayRisk("heat_wave_city") },
      ],
    });
  });

  it("head with the micro-region of the avalanches, in a micro-region", () => {
    const [heading] = risksOfVinadio().cards;

    assert.deepEqual(heading.badges.at(-1), {
      type: "entity",
      entity: vinadioRisk("avalanche_region"),
    });
  });

  it("show the highest alert, the danger now and the phase in the colors of Arpa", () => {
    const section = risksOfPray();
    const highest = cardsFor(section, prayRisk("highest_alert"));
    const danger = cardsFor(section, prayRisk("current_danger"));
    const phase = cardsFor(section, prayRisk("operational_phase"));

    assert.deepEqual(
      highest.map((card) => card.color),
      ["#90c985", "#f8f865", "#f0bf01", "#fd6767", undefined],
    );
    assert.deepEqual(highest[0].grid_options, { columns: 12 });
    assert.deepEqual(
      danger.map((card) => card.color),
      [...Object.values(ALERT_COLORS), undefined],
    );
    assert.deepEqual(danger[0].grid_options, { columns: 6 });
    assert.deepEqual(
      phase.map((card) => card.color),
      ["#c7fff0", "#cc99ff", "#7030a0", undefined],
    );
    // No phase, as not evaluated, unknown or unavailable: without color, shown
    assert.deepEqual(phase[3].visibility, [
      {
        condition: "state",
        entity: prayRisk("operational_phase"),
        state_not: Object.keys(PHASE_COLORS),
      },
    ]);
  });

  it("show the level of each risk on each day, named after the risk", () => {
    const section = risksOfPray();
    const headings = section.cards.filter((card) => card.heading_style === "subtitle");
    const hydraulic = cardsFor(section, prayRisk("hydraulic_risk_level_today"));

    assert.deepEqual(
      headings.map((card) => card.heading),
      ["Today", "Tomorrow"],
    );
    assert.deepEqual(
      hydraulic.map((card) => [card.name, card.color]),
      [
        ["Hydraulic", "#90c985"],
        ["Hydraulic", "#f8f865"],
        ["Hydraulic", "#f0bf01"],
        ["Hydraulic", "#fd6767"],
        ["Hydraulic", undefined],
      ],
    );
    assert.deepEqual(hydraulic[0].grid_options, { columns: 6 });
    // Ten levels, four colors each and one without color
    assert.equal(section.cards.filter((card) => /_risk_level_/.test(card.entity ?? "")).length, 50);
  });

  it("hide a day until the bulletin covers it: tomorrow, in the morning", () => {
    const section = risksOfPray();
    const tomorrow = section.cards.find((card) => card.heading === "Tomorrow");
    const [, , , , uncolored] = cardsFor(section, prayRisk("snow_risk_level_tomorrow"));

    assert.deepEqual(tomorrow.visibility, [
      {
        condition: "or",
        conditions: [
          ...["hydrogeological", "hydraulic", "thunderstorm", "snow", "avalanche"].map(
            (risk) => `${risk}_risk_level_tomorrow`,
          ),
          "heat_wave_tomorrow",
        ].map((key) => ({
          condition: "state",
          entity: prayRisk(key),
          state_not: ["unknown"],
        })),
      },
    ]);
    assert.deepEqual(uncolored.visibility, [
      {
        condition: "state",
        entity: prayRisk("snow_risk_level_tomorrow"),
        state_not: ["green", "yellow", "orange", "red", "unknown"],
      },
    ]);
  });

  it("speak the language of the user", () => {
    const hass = homeAssistant({ language: "it" });
    const section = risksOfPray(hass);

    assert.equal(section.cards[0].heading, "Rischi naturali");
    assert.equal(section.cards.find((card) => card.heading_style).heading, "Oggi");
    assert.equal(cardsFor(section, prayRisk("thunderstorm_risk_level_today"))[0].name, "Temporali");
  });

  it("leave out the entities the user disabled, and a day without any", () => {
    const hass = homeAssistant();
    hass.entities = Object.fromEntries(
      Object.entries(hass.entities).filter(
        ([id]) => !/_tomorrow$|highest_alert$|alert_zone$|heat_wave_city$/.test(id),
      ),
    );

    const section = risksOfPray(hass);

    assert.deepEqual(section.cards[0].badges, [
      { type: "entity", entity: prayRisk("alert_bulletin") },
    ]);
    assert.equal(cardsFor(section, prayRisk("highest_alert")).length, 0);
    assert.equal(
      section.cards.some((card) => card.heading === "Tomorrow"),
      false,
    );
  });
});

describe("other risks", () => {
  it("show the heat wave and the avalanche danger of each day, after the bulletin", () => {
    const section = risksOfVinadio();
    const today = section.cards.filter(
      (card) => card.entity?.endsWith("_today") && card.visibility[0].state === "green",
    );
    const heat = cardsFor(section, vinadioRisk("heat_wave_today"));
    const avalanches = cardsFor(section, vinadioRisk("avalanche_danger_today"));

    assert.deepEqual(
      today.map((card) => card.name),
      ["Hydrogeological", "Hydraulic", "Thunderstorms", "Snow", "Avalanches", "Heat wave"],
    );
    assert.deepEqual(
      heat.map((card) => card.color),
      [...Object.values(ALERT_COLORS), undefined],
    );
    assert.deepEqual(
      avalanches.map((card) => [card.name, card.color, card.visibility[0].state]),
      [
        ["Avalanche danger", "#90c985", "low"],
        ["Avalanche danger", "#f8f865", "moderate"],
        ["Avalanche danger", "#f0bf01", "considerable"],
        ["Avalanche danger", "#fd6767", "high"],
        ["Avalanche danger", "#8b0000", "very_high"],
        ["Avalanche danger", undefined, undefined],
      ],
    );
    // No snow, without color; hidden while the bulletin does not cover the day
    assert.deepEqual(avalanches.at(-1).visibility[0].state_not, [
      ...Object.keys(AVALANCHE_COLORS),
      "unknown",
    ]);
  });

  it("show the earthquakes nearby, and a map of them marked with their magnitude", () => {
    const [count, map] = earthquakeCards(
      homeAssistant(),
      risksIn(homeAssistant(), "vinadio_risks"),
    );

    assert.deepEqual(count.entity, vinadioRisk("nearby_earthquakes"));
    assert.deepEqual(count.grid_options, { columns: 12 });
    assert.deepEqual(map, {
      type: "map",
      entities: ["261110081514", "261117064149"].map((event) => ({
        entity: riskEntityId("vinadio_risks", "geo_location", `earthquake_${event}`),
        label_mode: "attribute",
        attribute: "magnitude",
      })),
      default_zoom: 8,
      grid_options: { columns: 12 },
    });
    assert.equal(risksOfVinadio().cards.at(-1).type, "map");
  });

  it("have no map without earthquakes nearby", () => {
    const cards = earthquakeCards(homeAssistant(), risksIn(homeAssistant(), "pray_risks"));

    assert.deepEqual(
      cards.map((card) => card.entity),
      [prayRisk("nearby_earthquakes")],
    );
  });

  it("speak the language of the user", () => {
    const section = risksOfVinadio(homeAssistant({ language: "pt-BR" }));

    assert.equal(cardsFor(section, vinadioRisk("heat_wave_today"))[0].name, "Onda de calor");
    assert.equal(
      cardsFor(section, vinadioRisk("avalanche_danger_today"))[0].name,
      "Perigo de avalanches",
    );
  });

  it("leave out a municipality the alert bulletin does not cover", () => {
    const hass = homeAssistant();
    hass.entities = Object.fromEntries(
      Object.entries(hass.entities).filter(
        ([id, entry]) => entry.device_id !== "pray_risks" || /heat_wave|earthquake/.test(id),
      ),
    );

    const section = risksOfPray(hass);

    assert.deepEqual(
      section.cards.map((card) => card.heading ?? card.entity),
      [
        "Natural risks",
        "Today",
        ...Array(5).fill(prayRisk("heat_wave_today")),
        "Tomorrow",
        ...Array(5).fill(prayRisk("heat_wave_tomorrow")),
        prayRisk("nearby_earthquakes"),
      ],
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

describe("section of a station with a barometer and a radiometer", () => {
  it("shows the pressure and the solar radiation last, and their charts", () => {
    const extra = ["pressure", "solar_radiation", "pressure_chart", "radiation_chart"].map(
      (key) => ({
        entity_id: entityId("colle", key.endsWith("_chart") ? "image" : "sensor", key),
        platform: "arpa_piemonte",
        device_id: "colle",
        translation_key: key,
      }),
    );
    const section = sectionOf("colle", homeAssistant({ entities: extra }));

    const tiles = section.cards.filter((card) => card.type === "tile");
    assert.deepEqual(
      tiles
        .slice(-3)
        .map((card) => [card.entity.split("_lombarda_")[1], card.grid_options.columns]),
      [
        ["snow_depth", 6],
        ["pressure", 6],
        ["solar_radiation", 6],
      ],
    );
    const charts = section.cards.filter((card) => card.type === "picture-entity");
    assert.deepEqual(
      charts.slice(-2).map((card) => card.entity.split("_lombarda_")[1]),
      ["pressure_chart", "radiation_chart"],
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

  it("hide a card colored by state in the states asked", () => {
    const [, uncolored] = colorByState({ type: "tile", entity: "a" }, "a", { on: "red" }, [
      "unknown",
    ]);

    assert.deepEqual(uncolored.visibility, [
      { condition: "state", entity: "a", state_not: ["on", "unknown"] },
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
    assert.equal(textsIn("es-419").station, "Estación");
    assert.equal(textsIn("de-CH").natural_risks, "Naturgefahren");
    assert.equal(textsIn("fr").natural_risks, "Risques naturels");
    assert.equal(textsIn("uk").station, "Станція");
    assert.equal(textsIn("zh-Hans").natural_risks, "自然风险");
    assert.equal(textsIn("ja").station, "Station");
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
