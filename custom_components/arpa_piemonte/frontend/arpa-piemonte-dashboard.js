// @ts-check
/**
 * The ARPA Piemonte dashboard: the readings of every station of the ARPA
 * Piemonte integration, built from the native cards of Home Assistant.
 *
 * It is a dashboard strategy: Home Assistant runs it when the dashboard opens
 * and, from Home Assistant 2026.7, again when entities or devices are added or
 * removed. From 2026.5, users add it from Settings → Dashboards → Add
 * dashboard; before, with `strategy: type: custom:arpa-piemonte` in the raw
 * configuration of a dashboard. The integration serves this file and has the frontend load it
 * (custom_components/arpa_piemonte/dashboard.py).
 *
 * A tab per municipality: the section of its natural risks at the top, then a
 * section per station. The entities are found by their translation key and
 * their device, never by their entity ID, which users can rename.
 */

/**
 * @typedef {object} EntityEntry The registry entry of an entity, as the frontend has it.
 * @property {string} entity_id
 * @property {string} platform The integration of the entity.
 * @property {string | null} [device_id]
 * @property {string | null} [translation_key]
 * @property {boolean} [hidden]
 *
 * @typedef {object} DeviceEntry The registry entry of a device: a station, or the risks of a municipality.
 * @property {string} id
 * @property {string | null} [name]
 * @property {string | null} [name_by_user]
 * @property {Array<Array<string | number>>} [identifiers] e.g. [["arpa_piemonte", "PIE_188"]]
 * @property {string[]} [config_entries] The entry of its municipality.
 *
 * @typedef {object} StateObject The state of an entity, as the frontend has it.
 * @property {string} entity_id
 * @property {string} state
 *
 * @typedef {object} ConfigEntry A config entry, as the websocket gives it: a municipality.
 * @property {string} entry_id
 * @property {string} title
 *
 * @typedef {object} Hass The parts of the Home Assistant object the strategy reads.
 * @property {Record<string, EntityEntry>} entities
 * @property {Record<string, DeviceEntry>} devices
 * @property {Record<string, StateObject>} [states]
 * @property {{ version: string }} config
 * @property {{ language: string }} [locale]
 * @property {string} [language]
 * @property {(key: string, values?: Record<string, string>) => string} [localize]
 *   The texts of the frontend, in the language of the user.
 * @property {(category: string, integration: string) => Promise<Hass["localize"]>} [loadBackendTranslation]
 *   Load texts of an integration into the frontend, and return them with the others.
 * @property {(message: Record<string, unknown>) => Promise<any>} [callWS]
 *   A command of the websocket API of Home Assistant.
 *
 * @typedef {Record<string, any>} Card A card configuration.
 * @typedef {{ type: string, cards: Card[] }} Section A section of a sections view.
 */

/** The integration whose entities the dashboard shows. */
export const PLATFORM = "arpa_piemonte";

/** The name of the strategy, `custom:arpa-piemonte` in a dashboard or a view. */
export const STRATEGY = "arpa-piemonte";

/** The prefix of the identifier of the device of a station: "PIE_188". */
export const STATION_PREFIX = "PIE_";

/**
 * The prefix of the identifier of the device of the risks of a municipality,
 * its ISTAT code: "ISTAT_096050".
 */
export const RISKS_PREFIX = "ISTAT_";

/** The icon of the dashboard, and of a station with a hydrometer. */
export const ICON = "mdi:waves-arrow-up";

/** The icon of a station without hydrometer. */
export const WEATHER_ICON = "mdi:weather-partly-rainy";

/** The icon of the natural risks of a municipality. */
export const RISKS_ICON = "mdi:shield-alert";

/** The colors of the levels, as on the alert maps: normal, then each threshold. */
const LEVEL_COLORS = ["#90c985", "#f8f865", "#f0bf01", "#fd6767"];

/** Color of each state of the level status of a station. */
export const LEVEL_STATUS_COLORS = Object.fromEntries(
  ["normal", "pre_alarm", "guard", "danger"].map((status, index) => [status, LEVEL_COLORS[index]]),
);

/**
 * Color of each level of the alert bulletin and of the danger now, as on the
 * alert maps; not evaluated (white on the maps), without color.
 */
export const ALERT_COLORS = Object.fromEntries(
  ["green", "yellow", "orange", "red"].map((level, index) => [level, LEVEL_COLORS[index]]),
);

/**
 * Color of each operational phase of a municipality, as the legend of the
 * widget of Arpa; none (white in the legend), without color.
 */
export const PHASE_COLORS = { attention: "#c7fff0", pre_alarm: "#cc99ff", alarm: "#7030a0" };

/** The risks of the alert bulletin, by the key of their entities, in the order of the widget. */
export const RISKS = ["hydrogeological", "hydraulic", "thunderstorm", "snow", "avalanche"];

/** The days of the risks, as the keys of their entities end. */
export const DAYS = ["today", "tomorrow"];

/** The sensors of the thresholds of a hydrometer, from the lowest, and the color above each. */
export const THRESHOLD_COLORS = {
  pre_alarm_threshold: LEVEL_COLORS[1],
  guard_threshold: LEVEL_COLORS[2],
  danger_threshold: LEVEL_COLORS[3],
};

/**
 * The top of the gauge of the level: the highest threshold of the station and
 * a quarter more, so that the band above it shows (the choice of the
 * maintainer). Pray Sessera, 2.3 / 3.0 / 3.8 m, goes from 0 to 4.75 m.
 */
export const GAUGE_MARGIN = 1.25;

/**
 * The sensors of the readings of a station, in the order they are shown, with
 * the columns of a section they take: the three rains on a row, the others two
 * by two.
 */
export const READINGS = {
  temperature: 6,
  humidity: 6,
  rain_1h: 4,
  rain_3h: 4,
  rain_24h: 4,
  wind_speed: 6,
  wind_direction: 6,
  gust_speed: 6,
  gust_direction: 6,
  snow_depth: 6,
  pressure: 6,
  solar_radiation: 6,
};

/** The charts of a station, by the key of their image entity, in the order they are shown. */
export const CHARTS = [
  "level_chart",
  "rain_chart",
  "temperature_chart",
  "humidity_chart",
  "snow_chart",
  "wind_chart",
  "pressure_chart",
  "radiation_chart",
];

/** The source of the readings when Meteo 3R answers: the data source shows only otherwise. */
export const PRIMARY_SOURCE = "meteo3r";

/** States of an entity without data. */
export const NO_DATA_STATES = ["unknown", "unavailable"];

/** The first version of Home Assistant that names an entity without its device. */
const ENTITY_NAME_VERSION = [2025, 11];

/** The texts of the dashboard and of the editor of the card, in the languages of the integration. */
const TEXTS = {
  en: {
    integration_name: "ARPA Piemonte",
    description:
      "River levels, rain, temperature, wind and snow of your stations of Arpa Piemonte, and the natural risks of their municipalities.",
    no_stations: "Add a station of the ARPA Piemonte integration to see its readings here.",
    station: "Station",
    heading: "Heading",
    title: "Title",
    content: "Content",
    readings: "Readings",
    charts: "Charts",
    columns: "Columns",
    natural_risks: "Natural risks",
    today: "Today",
    tomorrow: "Tomorrow",
    hydrogeological: "Hydrogeological",
    hydraulic: "Hydraulic",
    thunderstorm: "Thunderstorms",
    snow: "Snow",
    avalanche: "Avalanches",
  },
  it: {
    integration_name: "ARPA Piemonte",
    description:
      "Livelli dei fiumi, pioggia, temperatura, vento e neve delle tue stazioni di Arpa Piemonte, e i rischi naturali dei loro comuni.",
    no_stations: "Aggiungi una stazione dell'integrazione ARPA Piemonte per vederne qui le misure.",
    station: "Stazione",
    heading: "Intestazione",
    title: "Titolo",
    content: "Contenuto",
    readings: "Misure",
    charts: "Grafici",
    columns: "Colonne",
    natural_risks: "Rischi naturali",
    today: "Oggi",
    tomorrow: "Domani",
    hydrogeological: "Idrogeologico",
    hydraulic: "Idraulico",
    thunderstorm: "Temporali",
    snow: "Neve",
    avalanche: "Valanghe",
  },
  "pt-BR": {
    integration_name: "ARPA Piemonte",
    description:
      "Nível dos rios, chuva, temperatura, vento e neve das suas estações da Arpa Piemonte, e os riscos naturais dos municípios delas.",
    no_stations: "Adicione uma estação da integração ARPA Piemonte para ver as medições dela aqui.",
    station: "Estação",
    heading: "Cabeçalho",
    title: "Título",
    content: "Conteúdo",
    readings: "Medições",
    charts: "Gráficos",
    columns: "Colunas",
    natural_risks: "Riscos naturais",
    today: "Hoje",
    tomorrow: "Amanhã",
    hydrogeological: "Hidrogeológico",
    hydraulic: "Hidráulico",
    thunderstorm: "Tempestades",
    snow: "Neve",
    avalanche: "Avalanches",
  },
};

/**
 * Return the texts in a language: its own, those of its base language
 * (`it` for `it-CH`, `pt-BR` for `pt`), or English.
 *
 * @param {string | undefined} language
 */
export function textsIn(language) {
  const base = (language ?? "en").split("-")[0];
  const match =
    Object.keys(TEXTS).find((known) => known === language) ??
    Object.keys(TEXTS).find((known) => known.split("-")[0] === base) ??
    "en";
  return TEXTS[/** @type {keyof typeof TEXTS} */ (match)];
}

/**
 * Return the texts in the language of the user.
 *
 * @param {Hass} hass
 */
export function textsOf(hass) {
  return textsIn(hass.locale?.language ?? hass.language);
}

/**
 * Return the localized dashboard creation suggestion.
 *
 * @param {string | undefined} language
 */
export function dashboardSuggestion(language) {
  return { title: textsIn(language).integration_name, icon: ICON };
}

/**
 * Return Home Assistant with the names of the entities of the integration in
 * the language of the user: Home Assistant names them in the language of the
 * server.
 *
 * @param {Hass} hass
 * @returns {Promise<Hass>}
 */
export async function withTexts(hass) {
  if (!hass.loadBackendTranslation) {
    return hass;
  }
  const localize = await hass.loadBackendTranslation("entity", PLATFORM);
  return { ...hass, localize };
}

/**
 * Return a text of the integration in the language of the user, if the
 * frontend has it.
 *
 * @param {Hass} hass
 * @param {string} key e.g. "entity.sensor.level.name"
 */
export function translated(hass, key) {
  return hass.localize?.(`component.${PLATFORM}.${key}`) || undefined;
}

/**
 * Return the name of an entity of the integration in the language of the
 * user, from its translation key: "Livello idrometrico" for the level.
 *
 * @param {Hass} hass
 * @param {string} entity
 */
export function entityName(hass, entity) {
  const key = hass.entities[entity]?.translation_key;
  return key ? translated(hass, `entity.${entity.split(".")[0]}.${key}.name`) : undefined;
}

/**
 * Return whether Home Assistant is at least the given year and month version.
 *
 * @param {Hass} hass
 * @param {number[]} version e.g. [2025, 11]
 */
export function isAtLeast(hass, [year, month]) {
  const [major, minor] = hass.config.version.split(".").map(Number);
  return major > year || (major === year && minor >= month);
}

/**
 * Return the code of the station of a device, from its identifier: "188" for
 * ["arpa_piemonte", "PIE_188"]; none for another device.
 *
 * @param {DeviceEntry} device
 */
export function stationCode(device) {
  for (const [domain, id] of device.identifiers ?? []) {
    if (domain === PLATFORM && String(id).startsWith(STATION_PREFIX)) {
      return String(id).slice(STATION_PREFIX.length);
    }
  }
  return undefined;
}

/**
 * Return whether a device is that of the risks of a municipality: its
 * identifier is ["arpa_piemonte", "ISTAT_096050"].
 *
 * @param {DeviceEntry} device
 */
export function isRisksDevice(device) {
  return (device.identifiers ?? []).some(
    ([domain, id]) => domain === PLATFORM && String(id).startsWith(RISKS_PREFIX),
  );
}

/** A device of the integration: its entities, by domain and translation key. */
class Device {
  /**
   * @param {DeviceEntry} device
   * @param {EntityEntry[]} entities
   */
  constructor(device, entities) {
    this.device = device;
    this.entries = entities;
  }

  /** The entry of its municipality. */
  get municipality() {
    return this.device.config_entries?.[0];
  }

  /**
   * Return the entity ID of an entity of the device, if it is enabled.
   *
   * @param {string} domain e.g. "sensor"
   * @param {string} translationKey e.g. "level"
   */
  entity(domain, translationKey) {
    return this.entries.find(
      (entry) =>
        entry.entity_id.startsWith(`${domain}.`) && entry.translation_key === translationKey,
    )?.entity_id;
  }
}

/** A station: its device and its entities, by domain and translation key. */
export class Station extends Device {
  /** The name of the station, as the user sees its device. */
  get name() {
    return this.device.name_by_user || this.device.name || this.code;
  }

  /** The code of the station in the network: "188". */
  get code() {
    return stationCode(this.device) ?? this.device.id;
  }

  /** Whether the station measures a water level. */
  get isHydrometer() {
    return this.entity("sensor", "level") !== undefined;
  }
}

/** The natural risks of a municipality: their device and their entities. */
export class Risks extends Device {
  /** The name of the device, as the user sees it: "Pray · Natural risks". */
  get name() {
    return this.device.name_by_user || this.device.name || this.device.id;
  }
}

/**
 * Return the visible entities of the integration on the devices a test
 * accepts, by device.
 *
 * @param {Hass} hass
 * @param {(device: DeviceEntry) => boolean} accepts
 * @returns {Array<[DeviceEntry, EntityEntry[]]>}
 */
function entitiesByDevice(hass, accepts) {
  /** @type {Map<string, EntityEntry[]>} */
  const byDevice = new Map();
  for (const entry of Object.values(hass.entities)) {
    const device = entry.device_id ? hass.devices[entry.device_id] : undefined;
    if (entry.platform !== PLATFORM || !device || entry.hidden || !accepts(device)) {
      continue;
    }
    byDevice.set(device.id, [...(byDevice.get(device.id) ?? []), entry]);
  }
  return [...byDevice].map(([deviceId, entities]) => [hass.devices[deviceId], entities]);
}

/**
 * Return the stations, from the devices of the visible entities of the
 * integration: those with a hydrometer first, then by name.
 *
 * @param {Hass} hass
 * @returns {Station[]}
 */
export function findStations(hass) {
  return entitiesByDevice(hass, (device) => stationCode(device) !== undefined)
    .map(([device, entities]) => new Station(device, entities))
    .sort(
      (a, b) => Number(b.isHydrometer) - Number(a.isHydrometer) || a.name.localeCompare(b.name),
    );
}

/**
 * Return the risks of the municipalities, from the devices of the visible
 * entities of the integration.
 *
 * @param {Hass} hass
 * @returns {Risks[]}
 */
export function findRisks(hass) {
  return entitiesByDevice(hass, isRisksDevice).map(
    ([device, entities]) => new Risks(device, entities),
  );
}

/**
 * Return the number an entity shows; none without a number, as without data.
 *
 * @param {Hass} hass
 * @param {string | undefined} entity
 */
export function numberOf(hass, entity) {
  const state = entity ? hass.states?.[entity]?.state : undefined;
  const number = state === undefined || state === "" ? NaN : Number(state);
  return Number.isFinite(number) ? number : undefined;
}

/**
 * Return the thresholds of a station that have a value, from the lowest.
 *
 * @param {Hass} hass
 * @param {Station} station
 * @returns {Array<{ key: keyof typeof THRESHOLD_COLORS, value: number }>}
 */
export function thresholdsOf(hass, station) {
  return /** @type {Array<keyof typeof THRESHOLD_COLORS>} */ (Object.keys(THRESHOLD_COLORS))
    .map((key) => ({ key, value: numberOf(hass, station.entity("sensor", key)) }))
    .filter(
      /** @returns {item is { key: keyof typeof THRESHOLD_COLORS, value: number }} */
      (item) => item.value !== undefined,
    )
    .sort((a, b) => a.value - b.value);
}

/**
 * Return a number rounded to the centimetre, the precision of the levels.
 *
 * @param {number} value
 */
const centimetres = (value) => Math.round(value * 100) / 100;

/**
 * Return a tile of an entity, named in the language of the user, or else
 * without the station when Home Assistant can.
 *
 * @param {Hass} hass
 * @param {string} entity
 * @param {Card} [options]
 * @returns {Card}
 */
export function tile(hass, entity, options = {}) {
  const translatedName = entityName(hass, entity);
  /** @type {Card} */
  let name = {};
  if (translatedName) {
    name = { name: translatedName };
  } else if (isAtLeast(hass, ENTITY_NAME_VERSION)) {
    name = { name: { type: "entity" } };
  }
  return { type: "tile", entity, ...name, ...options };
}

/**
 * Return the gauge of the level of a station: a band for each threshold, in
 * the color of the level above it, from 0 (or a level below it) to the highest
 * threshold and a quarter more (or a level above it). None without a level or
 * a threshold with a value.
 *
 * @param {Hass} hass
 * @param {Station} station
 * @returns {Card | undefined}
 */
export function levelGauge(hass, station) {
  const level = station.entity("sensor", "level");
  const thresholds = thresholdsOf(hass, station);
  if (!level || !thresholds.length) {
    return undefined;
  }
  const current = numberOf(hass, level);
  const highest = thresholds[thresholds.length - 1].value;
  const min = current !== undefined && current < 0 ? Math.floor(current) : 0;
  const max = Math.max(centimetres(highest * GAUGE_MARGIN), current ?? -Infinity);
  const name = entityName(hass, level);
  return {
    type: "gauge",
    entity: level,
    ...(name ? { name } : {}),
    min,
    max,
    needle: true,
    segments: [
      { from: min, color: LEVEL_STATUS_COLORS.normal },
      ...thresholds.map(({ key, value }) => ({ from: value, color: THRESHOLD_COLORS[key] })),
    ],
  };
}

/**
 * Return the variants of a card, one per state of an entity, each in the color
 * of its state and visible only in that state; and the card without color for
 * any other state, as without data, but those it hides.
 *
 * Cards have a fixed color: the variants give them the color of the state.
 *
 * @param {Card} card
 * @param {string} entity The entity whose state gives the color.
 * @param {Record<string, string>} colors The color of each state.
 * @param {string[]} [hidden] The states in which the card is not shown.
 * @returns {Card[]}
 */
export function colorByState(card, entity, colors, hidden = []) {
  const states = Object.keys(colors);
  return [
    ...states.map((state) => ({
      ...card,
      color: colors[state],
      visibility: [{ condition: "state", entity, state }],
    })),
    { ...card, visibility: [{ condition: "state", entity, state_not: [...states, ...hidden] }] },
  ];
}

/**
 * Return the condition that shows a card while its entity has data.
 *
 * @param {string} entity
 */
export function withData(entity) {
  return { condition: "state", entity, state_not: NO_DATA_STATES };
}

/**
 * Return the heading of a station: its name, and as badges its flood risk, in
 * the color of its level status, the time of its last measurement, and the
 * source of its readings when it is not Meteo 3R.
 *
 * @param {Station} station
 * @returns {Card}
 */
export function stationHeading(station) {
  const floodRisk = station.entity("binary_sensor", "flood_risk");
  const levelStatus = station.entity("sensor", "level_status");
  const lastMeasurement = station.entity("sensor", "last_measurement");
  const dataSource = station.entity("sensor", "data_source");
  /** @type {Card[]} */
  const badges = [];
  if (floodRisk) {
    const badge = { type: "entity", entity: floodRisk };
    badges.push(...(levelStatus ? colorByState(badge, levelStatus, LEVEL_STATUS_COLORS) : [badge]));
  }
  if (lastMeasurement) {
    badges.push({ type: "entity", entity: lastMeasurement });
  }
  if (dataSource) {
    badges.push({
      type: "entity",
      entity: dataSource,
      visibility: [
        { condition: "state", entity: dataSource, state_not: [PRIMARY_SOURCE, ...NO_DATA_STATES] },
      ],
    });
  }
  return {
    type: "heading",
    heading: station.name,
    icon: station.isHydrometer ? ICON : WEATHER_ICON,
    badges,
  };
}

/**
 * Return the picture of a chart, without name nor state, shown while it has
 * data: until Meteo 3R gives the series of the station, it has none.
 *
 * @param {string} entity An image entity.
 * @returns {Card}
 */
export function chartPicture(entity) {
  return {
    type: "picture-entity",
    entity,
    show_name: false,
    show_state: false,
    grid_options: { columns: 12 },
    visibility: [withData(entity)],
  };
}

/**
 * Return the section of a station: its heading; for a hydrometer, its level
 * status in its color and the gauge of its level with the thresholds (without
 * threshold, the tile of the level); the tiles of its readings; and its charts.
 *
 * @param {Hass} hass
 * @param {Station} station
 * @returns {Section}
 */
export function stationSection(hass, station) {
  const levelStatus = station.entity("sensor", "level_status");
  // A hydrometer has a flood risk only with a threshold: its status is unknown otherwise
  const hasThresholds = station.entity("binary_sensor", "flood_risk") !== undefined;
  const level = station.entity("sensor", "level");
  const gauge = levelGauge(hass, station);
  const wide = { grid_options: { columns: 12 } };
  return {
    type: "grid",
    cards: [
      stationHeading(station),
      ...(levelStatus && hasThresholds
        ? colorByState(tile(hass, levelStatus, wide), levelStatus, LEVEL_STATUS_COLORS)
        : []),
      ...(gauge ? [{ ...gauge, ...wide }] : level ? [tile(hass, level, wide)] : []),
      ...Object.entries(READINGS).flatMap(([key, columns]) => {
        const entity = station.entity("sensor", key);
        return entity ? [tile(hass, entity, { grid_options: { columns } })] : [];
      }),
      ...CHARTS.flatMap((key) => {
        const entity = station.entity("image", key);
        return entity ? [chartPicture(entity)] : [];
      }),
    ],
  };
}

/** The state of a level of a risk until the bulletin covers its day: tomorrow, in the morning. */
const NOT_COVERED = "unknown";

/**
 * Return the cards of the risks of a day: its name, and the level of each risk
 * in the colors of the alert maps, named after the risk. Shown while the
 * bulletin covers the day: tomorrow, from the bulletin of the day, around
 * 13:00.
 *
 * @param {Hass} hass
 * @param {Risks} risks
 * @param {string} day e.g. "tomorrow"
 * @returns {Card[]}
 */
export function riskDayCards(hass, risks, day) {
  const texts = /** @type {Record<string, string>} */ (textsOf(hass));
  const levels = RISKS.flatMap((risk) => {
    const entity = risks.entity("sensor", `${risk}_risk_level_${day}`);
    return entity ? [{ risk, entity }] : [];
  });
  if (!levels.length) {
    return [];
  }
  return [
    {
      type: "heading",
      heading: texts[day],
      heading_style: "subtitle",
      visibility: [
        {
          condition: "or",
          conditions: levels.map(({ entity }) => ({
            condition: "state",
            entity,
            state_not: [NOT_COVERED],
          })),
        },
      ],
    },
    ...levels.flatMap(({ risk, entity }) =>
      colorByState(
        tile(hass, entity, { name: texts[risk], grid_options: { columns: 6 } }),
        entity,
        ALERT_COLORS,
        [NOT_COVERED],
      ),
    ),
  ];
}

/**
 * Return the section of the natural risks of a municipality: their heading,
 * with the alert zone and the time of the bulletin; the highest alert of
 * today and tomorrow, the danger now and the operational phase, in the colors
 * of Arpa; then the level of each risk, today and tomorrow.
 *
 * @param {Hass} hass
 * @param {Risks} risks
 * @returns {Section}
 */
export function risksSection(hass, risks) {
  /** @param {string} key */
  const sensor = (key) => risks.entity("sensor", key);
  /**
   * @param {string} key
   * @param {Record<string, string>} colors
   * @param {number} columns
   */
  const colored = (key, colors, columns) => {
    const entity = sensor(key);
    return entity
      ? colorByState(tile(hass, entity, { grid_options: { columns } }), entity, colors)
      : [];
  };
  return {
    type: "grid",
    cards: [
      {
        type: "heading",
        heading: textsOf(hass).natural_risks,
        icon: RISKS_ICON,
        badges: ["alert_zone", "alert_bulletin"].flatMap((key) => {
          const entity = sensor(key);
          return entity ? [{ type: "entity", entity }] : [];
        }),
      },
      ...colored("highest_alert", ALERT_COLORS, 12),
      ...colored("current_danger", ALERT_COLORS, 6),
      ...colored("operational_phase", PHASE_COLORS, 6),
      ...DAYS.flatMap((day) => riskDayCards(hass, risks, day)),
    ],
  };
}

/**
 * Return the view of a municipality: the section of its risks, then a section
 * for each of its stations.
 *
 * @param {Hass} hass
 * @param {Station[]} stations
 * @param {Risks} [risks]
 */
export function municipalityView(hass, stations, risks) {
  return {
    type: "sections",
    max_columns: 3,
    sections: [
      ...(risks ? [risksSection(hass, risks)] : []),
      ...stations.map((station) => stationSection(hass, station)),
    ],
  };
}

/**
 * Return a URL path made of a name: "Mondovì" is "mondovi".
 *
 * @param {string} name
 */
export function slugify(name) {
  return (
    name
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "arpa-piemonte"
  );
}

/**
 * Return the entries of the integration, the municipalities with their names;
 * none when Home Assistant does not give them.
 *
 * @param {Hass} hass
 * @returns {Promise<ConfigEntry[]>}
 */
export async function municipalityEntries(hass) {
  if (!hass.callWS) {
    return [];
  }
  try {
    return await hass.callWS({ type: "config_entries/get", domain: PLATFORM });
  } catch {
    return [];
  }
}

/**
 * Return the municipalities of the stations and of the risks, by name: the
 * entry of each, its name (or else the name of its first station, or of its
 * risks), its stations and its risks.
 *
 * @param {Station[]} stations
 * @param {ConfigEntry[]} entries
 * @param {Risks[]} [risks]
 */
export function municipalitiesOf(stations, entries, risks = []) {
  const titles = new Map(entries.map((entry) => [entry.entry_id, entry.title]));
  /** @type {Map<string, { stations: Station[], risks?: Risks }>} */
  const byEntry = new Map();
  /** @param {string | undefined} entryId */
  const municipality = (entryId) => {
    const key = entryId ?? "";
    const found = byEntry.get(key) ?? { stations: [] };
    byEntry.set(key, found);
    return found;
  };
  for (const station of stations) {
    municipality(station.municipality).stations.push(station);
  }
  for (const item of risks) {
    municipality(item.municipality).risks = item;
  }
  return [...byEntry]
    .map(([entryId, members]) => ({
      entryId,
      name:
        titles.get(entryId) ||
        members.stations[0]?.name ||
        /** @type {Risks} */ (members.risks).name,
      stations: members.stations,
      risks: members.risks,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Return a view that asks for a station, in the language of the user.
 *
 * @param {Hass} hass
 */
function noStationsView(hass) {
  return { type: "panel", cards: [{ type: "markdown", content: textsOf(hass).no_stations }] };
}

/**
 * Return the dashboard: a tab per municipality, each built by the view strategy.
 *
 * @param {Hass} hass
 */
export async function generateDashboard(hass) {
  const stations = findStations(hass);
  const risks = findRisks(hass);
  if (!stations.length && !risks.length) {
    return { views: [noStationsView(hass)] };
  }
  const municipalities = municipalitiesOf(stations, await municipalityEntries(hass), risks);
  /** @type {Set<string>} */
  const paths = new Set();
  return {
    views: municipalities.map(({ entryId, name }) => {
      let path = slugify(name);
      for (let number = 2; paths.has(path); number += 1) {
        path = `${slugify(name)}-${number}`;
      }
      paths.add(path);
      // No icon: a tab with an icon shows only the icon, and every municipality has the same
      return { title: name, path, strategy: { type: `custom:${STRATEGY}`, entry_id: entryId } };
    }),
  };
}

/**
 * Return the view of a municipality, its risks and its stations, for
 * `custom:arpa-piemonte` in a view.
 *
 * @param {{ entry_id?: string }} config
 * @param {Hass} hass
 */
export function generateView(config, hass) {
  /** @param {{ municipality: string | undefined }} item */
  const ofTheEntry = (item) => (item.municipality ?? "") === (config.entry_id ?? "");
  const stations = findStations(hass).filter(ofTheEntry);
  const risks = findRisks(hass).find(ofTheEntry);
  return stations.length || risks ? municipalityView(hass, stations, risks) : noStationsView(hass);
}

// The strategies, as Home Assistant looks them up: a custom element per kind,
// with static methods. Not defined outside a browser, as in the tests.

/** Rebuild the dashboard when stations or their entities come and go. */
const REGISTRY_DEPENDENCIES = ["entities", "devices"];

if (globalThis.customElements && globalThis.HTMLElement) {
  class ArpaPiemonteDashboardStrategy extends HTMLElement {
    static registryDependencies = REGISTRY_DEPENDENCIES;

    static noEditor = true;

    /** @param {unknown} _config @param {Hass} hass */
    static async generate(_config, hass) {
      return generateDashboard(hass);
    }

    /** @param {Hass} hass */
    static getCreateSuggestions(hass) {
      return dashboardSuggestion(hass.locale?.language ?? hass.language);
    }
  }

  class ArpaPiemonteViewStrategy extends HTMLElement {
    static registryDependencies = REGISTRY_DEPENDENCIES;

    /** @param {{ entry_id?: string }} config @param {Hass} hass */
    static async generate(config, hass) {
      return generateView(config, await withTexts(hass));
    }
  }

  /** @param {string} tag @param {CustomElementConstructor} strategy */
  const define = (tag, strategy) => customElements.get(tag) || customElements.define(tag, strategy);
  define(`ll-strategy-dashboard-${STRATEGY}`, ArpaPiemonteDashboardStrategy);
  define(`ll-strategy-view-${STRATEGY}`, ArpaPiemonteViewStrategy);

  // Listed in the Add dashboard dialog, from Home Assistant 2026.5
  const strategies = /** @type {any} */ (window).customStrategies ?? [];
  /** @type {any} */ (window).customStrategies = strategies;
  if (!strategies.some((/** @type {{ type: string }} */ item) => item.type === STRATEGY)) {
    strategies.push({
      type: STRATEGY,
      strategyType: "dashboard",
      name: "ARPA Piemonte",
      description: textsIn(document.documentElement.lang || navigator.language).description,
      documentationURL: "https://github.com/webysther/ha-arpa-piemonte#dashboard",
    });
  }
}
