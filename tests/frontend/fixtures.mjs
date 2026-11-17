// Fixtures of the tests of the frontend: stations of ARPA Piemonte as Home Assistant has them.

/**
 * The stations, as the Meteo 3R list of 2026-11-17 describes them: their
 * municipality, code, name, sensor letters, and the keys of their entities.
 */
export const STATIONS = {
  // A hydrometer with three thresholds
  pray: {
    entry: "pray_entry",
    code: "188",
    name: "Pray Sessera",
    sensors: [
      "level",
      "temperature",
      "rain_1h",
      "rain_3h",
      "rain_24h",
      "level_status",
      "pre_alarm_threshold",
      "guard_threshold",
      "danger_threshold",
      "data_source",
      "last_measurement",
    ],
    binarySensors: ["flood_risk"],
    images: ["level_chart", "rain_chart", "temperature_chart"],
  },
  // A weather station with wind and snow
  colle: {
    entry: "vinadio_entry",
    code: "001",
    name: "Colle Lombarda",
    sensors: [
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
      "data_source",
      "last_measurement",
    ],
    binarySensors: [],
    images: ["rain_chart", "temperature_chart", "humidity_chart", "snow_chart", "wind_chart"],
  },
  // Baceno has two stations: a weather station, and a hydrometer without thresholds
  alpe: {
    entry: "baceno_entry",
    code: "154",
    name: "Alpe Devero",
    sensors: [
      "temperature",
      "humidity",
      "rain_1h",
      "rain_3h",
      "rain_24h",
      "snow_depth",
      "data_source",
      "last_measurement",
    ],
    binarySensors: [],
    images: ["rain_chart", "temperature_chart", "humidity_chart", "snow_chart"],
  },
  devero: {
    entry: "baceno_entry",
    code: "S4059",
    name: "Baceno Devero",
    sensors: [
      "level",
      "level_status",
      "pre_alarm_threshold",
      "guard_threshold",
      "danger_threshold",
      "data_source",
      "last_measurement",
    ],
    binarySensors: [],
    images: ["level_chart"],
  },
};

/** The municipalities, as the websocket gives their entries. */
export const ENTRIES = [
  { entry_id: "pray_entry", title: "Pray", domain: "arpa_piemonte" },
  { entry_id: "vinadio_entry", title: "Vinadio", domain: "arpa_piemonte" },
  { entry_id: "baceno_entry", title: "Baceno", domain: "arpa_piemonte" },
];

/** Return the entity ID of an entity of a station, as the integration suggests it. */
export function entityId(station, domain, key) {
  const slug = STATIONS[station].name.toLowerCase().replaceAll(" ", "_");
  return `${domain}.arpa_piemonte_${slug}_${key}`;
}

/** Return the device of a station. */
export function stationDevice(station) {
  const { code, name, entry } = STATIONS[station];
  return {
    id: station,
    name,
    identifiers: [["arpa_piemonte", `PIE_${code}`]],
    config_entries: [entry],
  };
}

/** Return the registry entries of the entities of a station. */
export function stationEntities(station) {
  const { sensors, binarySensors, images } = STATIONS[station];
  const entity = (domain, key) => ({
    entity_id: entityId(station, domain, key),
    platform: "arpa_piemonte",
    device_id: station,
    translation_key: key,
  });
  return [
    ...sensors.map((key) => entity("sensor", key)),
    ...binarySensors.map((key) => entity("binary_sensor", key)),
    ...images.map((key) => entity("image", key)),
  ];
}

/** The states of the stations at 03:40 in Italy on 2026-11-17. */
export const STATES = {
  [entityId("pray", "sensor", "level")]: "0.86",
  [entityId("pray", "sensor", "level_status")]: "normal",
  [entityId("pray", "sensor", "pre_alarm_threshold")]: "2.3",
  [entityId("pray", "sensor", "guard_threshold")]: "3.0",
  [entityId("pray", "sensor", "danger_threshold")]: "3.8",
  [entityId("pray", "binary_sensor", "flood_risk")]: "off",
  [entityId("pray", "sensor", "data_source")]: "meteo3r",
  [entityId("pray", "image", "level_chart")]: "2026-11-17T02:00:00+00:00",
  [entityId("pray", "image", "rain_chart")]: "2026-11-17T02:00:00+00:00",
  [entityId("pray", "image", "temperature_chart")]: "unavailable",
  [entityId("devero", "sensor", "level")]: "0.4",
  [entityId("devero", "sensor", "level_status")]: "unknown",
  [entityId("devero", "sensor", "pre_alarm_threshold")]: "unknown",
  [entityId("devero", "sensor", "guard_threshold")]: "unknown",
  [entityId("devero", "sensor", "danger_threshold")]: "unknown",
  [entityId("colle", "sensor", "data_source")]: "arpa_realtime",
};

/** Return states, as Home Assistant has them. */
export const statesOf = (states) =>
  Object.fromEntries(
    Object.entries(states).map(([entity_id, state]) => [entity_id, { entity_id, state }]),
  );

/**
 * Return a Home Assistant with the four stations, whose websocket gives the
 * municipalities.
 */
export function homeAssistant({
  version = "2026.11.0",
  language = "en",
  entities = [],
  states = {},
  entries = ENTRIES,
} = {}) {
  const all = [
    ...Object.keys(STATIONS).flatMap(stationEntities),
    // Another integration on the same device is not shown
    { entity_id: "sensor.other", platform: "other", device_id: "pray" },
    ...entities,
  ];
  return {
    config: { version },
    locale: { language },
    devices: Object.fromEntries(
      Object.keys(STATIONS).map((station) => [station, stationDevice(station)]),
    ),
    entities: Object.fromEntries(all.map((entry) => [entry.entity_id, entry])),
    states: statesOf({ ...STATES, ...states }),
    callWS: async (message) => {
      if (message.type !== "config_entries/get" || message.domain !== "arpa_piemonte") {
        throw new Error(`Unexpected command ${JSON.stringify(message)}`);
      }
      return entries;
    },
  };
}
