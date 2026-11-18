// @ts-check
/**
 * The Arpa Piemonte card, `custom:arpa-piemonte-card`, for the dashboards of
 * the users, listed in the card picker as soon as the integration is
 * installed: a station, with its flood risk, the status and the gauge of its
 * level, its readings and its charts. Its visual editor chooses the station,
 * what the heading shows, what the card shows, and one or two columns.
 *
 * The integration serves this file next to the dashboard strategy, whose
 * helpers it shares, and has the frontend load it
 * (custom_components/arpa_piemonte/dashboard.py).
 *
 * The card draws nothing of its own: it is a card of Home Assistant
 * (`ha-card`) with native cards inside, without their own background, so that
 * the whole station is one card and follows the theme. What it adds is finding
 * the entities of the station by their translation key, so it keeps working
 * when users rename them; the colors of the level status, which native cards
 * cannot change by state; and names in the language of the user, rather than
 * of the server.
 */

import {
  CHARTS,
  ICON,
  LEVEL_STATUS_COLORS,
  NO_DATA_STATES,
  PRIMARY_SOURCE,
  READINGS,
  WEATHER_ICON,
  findStations,
  levelGauge,
  textsIn,
  textsOf,
  tile,
  translated,
  withTexts,
} from "./arpa-piemonte-dashboard.js";

/**
 * @typedef {import("./arpa-piemonte-dashboard.js").Hass} Hass
 * @typedef {import("./arpa-piemonte-dashboard.js").Station} Station
 * @typedef {import("./arpa-piemonte-dashboard.js").Card} Card
 * @typedef {import("./arpa-piemonte-dashboard.js").StateObject} StateObject
 *
 * @typedef {Hass & { states: Record<string, StateObject> }} CardHass
 *   The parts of the Home Assistant object the card reads.
 *
 * @typedef {object} CardConfig What the card shows; without an option, all of it.
 * @property {string} [type]
 * @property {string} [device_id] The device of the station; the first station without it.
 * @property {boolean} [show_title] The name of the station, above the rest.
 * @property {boolean} [show_flood_risk] Its flood risk, in the heading.
 * @property {boolean} [show_last_measurement] The time of its last measurement, in the heading.
 * @property {boolean} [show_level] The status and the gauge of its level.
 * @property {boolean} [show_readings] The tiles of its readings.
 * @property {boolean} [show_charts] Its charts.
 * @property {number} [columns] The readings in 1 column, or 2.
 *
 * @typedef {"all" | "cell"} Column Where a card goes: the whole width, or the
 *   next cell of the columns of the readings.
 *
 * @typedef {object} Placed A native card, and where it goes in the card.
 * @property {Card} card
 * @property {Column} column
 *
 * @typedef {Record<string, any>} FormField A field of the visual editor, as
 *   `ha-form` draws it, with its label.
 */

/** The name of the card, `custom:arpa-piemonte-card` in a dashboard. */
export const CARD = "arpa-piemonte-card";

/** What the heading of the card can show, each with the option that shows it. */
export const HEADING_OPTIONS = {
  title: "show_title",
  flood_risk: "show_flood_risk",
  last_measurement: "show_last_measurement",
};

/** What the card can show below its heading, each with the option that shows it. */
export const CONTENT_OPTIONS = {
  level: "show_level",
  readings: "show_readings",
  charts: "show_charts",
};

/** The options of the card that show everything: what it shows without them. */
export const DEFAULTS = {
  show_title: true,
  show_flood_risk: true,
  show_last_measurement: true,
  show_level: true,
  show_readings: true,
  show_charts: true,
  columns: 2,
};

/**
 * Return the station a card shows: the station of its device, or the first.
 *
 * @param {Station[]} stations
 * @param {CardConfig} config
 */
export function stationOf(stations, config) {
  return config.device_id
    ? stations.find((station) => station.device.id === config.device_id)
    : stations[0];
}

/**
 * Return the state of an entity; none without the entity or its state.
 *
 * @param {CardHass} hass
 * @param {string | undefined} entity
 */
function stateOf(hass, entity) {
  return entity ? hass.states[entity]?.state : undefined;
}

/**
 * Return whether an entity has data, such as a chart, which has none until
 * Meteo 3R gives the series of the station.
 *
 * @param {CardHass} hass
 * @param {string | undefined} entity
 */
function hasData(hass, entity) {
  const state = stateOf(hass, entity);
  return state !== undefined && !NO_DATA_STATES.includes(state);
}

/**
 * Return the color option of the level status of a station, as its state is
 * now: none without a known status.
 *
 * @param {CardHass} hass
 * @param {Station} station
 */
function levelColor(hass, station) {
  const status = stateOf(hass, station.entity("sensor", "level_status"));
  const color = status === undefined ? undefined : LEVEL_STATUS_COLORS[status];
  return color ? { color } : {};
}

/**
 * Return the heading of the card: the station, with its flood risk in the
 * color of its level status and the time of its last measurement, as chosen,
 * and the source of its readings while it is not Meteo 3R. Without the title,
 * only the badges; without either, no heading.
 *
 * @param {CardHass} hass
 * @param {Station} station
 * @param {CardConfig} config
 * @returns {Placed[]}
 */
function heading(hass, station, config) {
  const floodRisk = station.entity("binary_sensor", "flood_risk");
  const lastMeasurement = station.entity("sensor", "last_measurement");
  const dataSource = station.entity("sensor", "data_source");
  const sourceState = stateOf(hass, dataSource);
  /** @type {Card[]} */
  const badges = [];
  if (floodRisk && (config.show_flood_risk ?? true)) {
    badges.push({ type: "entity", entity: floodRisk, ...levelColor(hass, station) });
  }
  if (lastMeasurement && (config.show_last_measurement ?? true)) {
    badges.push({ type: "entity", entity: lastMeasurement });
  }
  if (dataSource && hasData(hass, dataSource) && sourceState !== PRIMARY_SOURCE) {
    badges.push({ type: "entity", entity: dataSource });
  }
  const title = config.show_title ?? true;
  if (!title && !badges.length) {
    return [];
  }
  return [
    {
      card: {
        type: "heading",
        heading: title ? station.name : "",
        ...(title ? { icon: station.isHydrometer ? ICON : WEATHER_ICON } : {}),
        badges,
      },
      column: "all",
    },
  ];
}

/**
 * Return the native cards of the level of a station: its status in its color,
 * with a threshold, and the gauge of its level with the thresholds, or without
 * a threshold the tile of the level.
 *
 * @param {CardHass} hass
 * @param {Station} station
 * @returns {Placed[]}
 */
function levelCards(hass, station) {
  const level = station.entity("sensor", "level");
  if (!level) {
    return [];
  }
  /** @type {Placed[]} */
  const placed = [];
  const levelStatus = station.entity("sensor", "level_status");
  if (levelStatus && station.entity("binary_sensor", "flood_risk")) {
    placed.push({ card: tile(hass, levelStatus, levelColor(hass, station)), column: "all" });
  }
  placed.push({ card: levelGauge(hass, station) ?? tile(hass, level), column: "all" });
  return placed;
}

/**
 * Return the native cards of a station, as chosen: a heading, the level, the
 * readings in their columns, and the charts that have data.
 *
 * @param {CardHass} hass
 * @param {Station} station
 * @param {CardConfig} [config]
 * @returns {Placed[]}
 */
export function stationLayout(hass, station, config = {}) {
  return [
    ...heading(hass, station, config),
    ...((config.show_level ?? true) ? levelCards(hass, station) : []),
    ...((config.show_readings ?? true)
      ? Object.keys(READINGS).flatMap((key) => {
          const entity = station.entity("sensor", key);
          return entity
            ? [{ card: tile(hass, entity), column: /** @type {Column} */ ("cell") }]
            : [];
        })
      : []),
    ...((config.show_charts ?? true)
      ? CHARTS.flatMap((key) => {
          const entity = station.entity("image", key);
          return entity && hasData(hass, entity)
            ? [
                {
                  card: { type: "picture-entity", entity, show_name: false, show_state: false },
                  column: /** @type {Column} */ ("all"),
                },
              ]
            : [];
        })
      : []),
  ];
}

/**
 * Return the native cards the card shows: those of its station, or a message
 * without one.
 *
 * @param {CardHass} hass
 * @param {Station[]} stations
 * @param {CardConfig} config
 * @returns {Placed[]}
 */
export function cardLayout(hass, stations, config) {
  const station = stationOf(stations, config);
  if (!station) {
    return [{ card: { type: "markdown", content: textsOf(hass).no_stations }, column: "all" }];
  }
  return stationLayout(hass, station, config);
}

/**
 * Check the configuration of the card, as Home Assistant shows its errors.
 *
 * @param {CardConfig} config
 */
export function checkConfig(config) {
  if (config.device_id !== undefined && typeof config.device_id !== "string") {
    throw new Error("device_id must be the ID of the device of a station of Arpa Piemonte");
  }
  for (const option of [...Object.values(HEADING_OPTIONS), ...Object.values(CONTENT_OPTIONS)]) {
    const value = config[/** @type {keyof CardConfig} */ (option)];
    if (value !== undefined && typeof value !== "boolean") {
      throw new Error(`${option} must be true or false`);
    }
  }
  if (config.columns !== undefined && config.columns !== 1 && config.columns !== 2) {
    throw new Error("columns must be 1 or 2");
  }
}

/**
 * Return the configuration of the card from its visual editor: the columns as
 * a number, the lists of the heading and of the content as their options, and
 * without the options that show what the card shows anyway, so that its YAML
 * stays short.
 *
 * @param {Record<string, any>} value
 * @returns {CardConfig}
 */
export function cleanConfig(value) {
  /** @type {Record<string, any>} */
  const config = { ...value };
  if (typeof config.columns === "string") {
    config.columns = Number(config.columns);
  }
  const lists = { heading: HEADING_OPTIONS, content: CONTENT_OPTIONS };
  for (const [field, options] of Object.entries(lists)) {
    if (Array.isArray(config[field])) {
      for (const [item, option] of Object.entries(options)) {
        config[option] = config[field].includes(item);
      }
      delete config[field];
    }
  }
  for (const [option, fallback] of Object.entries(DEFAULTS)) {
    if (config[option] === fallback) {
      delete config[option];
    }
  }
  return config;
}

/**
 * Return the data of the visual editor of the card: its options, with those it
 * leaves out as they show, the station it shows, and what its heading and its
 * content show.
 *
 * @param {Station[]} stations
 * @param {CardConfig} config
 */
export function editorData(stations, config) {
  /** @type {Record<string, any>} */
  const options = { ...DEFAULTS, ...config };
  /** @param {Record<string, string>} items */
  const chosen = (items) =>
    Object.entries(items)
      .filter(([, option]) => options[option])
      .map(([item]) => item);
  return {
    ...options,
    device_id: config.device_id ?? stations[0]?.device.id,
    heading: chosen(HEADING_OPTIONS),
    content: chosen(CONTENT_OPTIONS),
    columns: String(config.columns ?? DEFAULTS.columns),
  };
}

/**
 * Return the name of an entity of the integration, by its translation key, in
 * the language of the user.
 *
 * @param {Hass} hass
 * @param {string} domain
 * @param {string} key
 */
function entityText(hass, domain, key) {
  return translated(hass, `entity.${domain}.${key}.name`) || key;
}

/**
 * Return the fields of the visual editor of the card, labeled in the language
 * of the user, with the names of the integration where it has them.
 *
 * @param {Hass} hass
 * @param {Station[]} stations
 * @param {CardConfig} config
 * @returns {FormField[]}
 */
export function editorSchema(hass, stations, config) {
  const texts = textsOf(hass);
  const options = stations.map((station) => ({ value: station.device.id, label: station.name }));
  // A station that is gone stays, by its ID, until another is chosen
  if (config.device_id && !options.some(({ value }) => value === config.device_id)) {
    options.push({ value: config.device_id, label: config.device_id });
  }
  /** @type {Record<string, string>} */
  const labels = {
    title: texts.title,
    flood_risk: entityText(hass, "binary_sensor", "flood_risk"),
    last_measurement: entityText(hass, "sensor", "last_measurement"),
    level: entityText(hass, "sensor", "level"),
    readings: texts.readings,
    charts: texts.charts,
  };
  /** @param {string} name @param {string} label @param {Record<string, string>} items */
  const list = (name, label, items) => ({
    name,
    label,
    selector: {
      select: {
        multiple: true,
        mode: "list",
        options: Object.keys(items).map((item) => ({ value: item, label: labels[item] })),
      },
    },
  });
  return [
    {
      name: "device_id",
      label: texts.station,
      selector: { select: { options, mode: "dropdown" } },
    },
    list("heading", texts.heading, HEADING_OPTIONS),
    list("content", texts.content, CONTENT_OPTIONS),
    {
      name: "columns",
      label: texts.columns,
      selector: { select: { options: ["1", "2"], mode: "dropdown" } },
    },
  ];
}

/**
 * Return the width of the columns of the readings.
 *
 * @param {CardConfig} config
 */
export function columnsOf(config) {
  return config.columns === 1 ? "minmax(0, 1fr)" : "minmax(0, 1fr) minmax(0, 1fr)";
}

/**
 * The style of the card. The native cards inside lose their own background,
 * border and shadow, so that the card is one surface, as the theme draws it.
 *
 * The heading lines up with the tiles: the center of its 18px icon, 4px from
 * its edge, with the center of their 36px icons, 10px from theirs (15px), and
 * its badges, 4px from its edge, with their 10px padding (6px). Without the
 * title, the heading is as wide as its badges, at the start.
 */
const STYLE = `
  ha-card {
    overflow: hidden;
  }
  .content {
    display: grid;
    grid-template-columns: var(--arpa-piemonte-columns);
    padding-block-end: 4px;
    --ha-card-background: transparent;
    --ha-card-border-width: 0px;
    --ha-card-box-shadow: none;
  }
  .all {
    grid-column: 1 / -1;
  }
  .heading {
    padding-inline: 15px 6px;
  }
  .badges {
    justify-self: start;
    padding-inline-start: 8px;
    --ha-heading-card-title-min-width: 0px;
  }
  .picture {
    padding: 4px 10px;
  }
`;

if (globalThis.customElements && globalThis.HTMLElement) {
  /**
   * Have the frontend define its forms, which it loads with the editors of
   * its own cards: the editor of a tile has one.
   */
  const loadForms = async () => {
    if (customElements.get("ha-form")) {
      return;
    }
    const helpers = await /** @type {any} */ (window).loadCardHelpers();
    helpers.createCardElement({ type: "tile", entity: "sun.sun" });
    await customElements.whenDefined("hui-tile-card");
    await /** @type {any} */ (customElements.get("hui-tile-card")).getConfigElement();
  };

  /**
   * Return the texts of the frontend with those of the integration in the
   * language of the user, loaded once per language, then a call back.
   */
  class Texts {
    /** @type {string | undefined} */
    #language;

    /** @type {Hass["localize"]} */
    #localize;

    /**
     * Return Home Assistant with the texts loaded so far, and load them in
     * a new language, calling back once they are.
     *
     * @template {Hass} H
     * @param {H} hass
     * @param {() => void} loaded
     * @returns {H}
     */
    of(hass, loaded) {
      const language = hass.locale?.language ?? hass.language;
      if (language !== this.#language) {
        this.#language = language;
        withTexts(hass).then(({ localize }) => {
          this.#localize = localize;
          loaded();
        });
      }
      return { ...hass, localize: this.#localize ?? hass.localize };
    }
  }

  /** The visual editor of the card: a form of Home Assistant. */
  class ArpaPiemonteCardEditor extends HTMLElement {
    /** @type {CardConfig | undefined} */
    #config;

    /** @type {Hass | undefined} */
    #hass;

    /** @type {any} */
    #form;

    #texts = new Texts();

    /** @param {CardConfig} config */
    setConfig(config) {
      this.#config = config;
      this.#render();
    }

    /** @param {Hass} hass */
    set hass(hass) {
      this.#hass = hass;
      this.#render();
    }

    #render() {
      if (!this.#hass || !this.#config) {
        return;
      }
      const hass = this.#texts.of(this.#hass, () => this.#render());
      if (!this.#form) {
        this.#form = document.createElement("ha-form");
        this.#form.computeLabel = (/** @type {FormField} */ field) => field.label ?? field.name;
        this.#form.addEventListener("value-changed", (/** @type {CustomEvent} */ event) => {
          event.stopPropagation();
          this.dispatchEvent(
            new CustomEvent("config-changed", {
              detail: { config: cleanConfig(event.detail.value) },
              bubbles: true,
              composed: true,
            }),
          );
        });
        this.append(this.#form);
      }
      const stations = findStations(hass);
      this.#form.hass = this.#hass;
      this.#form.schema = editorSchema(hass, stations, this.#config);
      this.#form.data = editorData(stations, this.#config);
    }
  }

  /** A card of a station, made of native cards. */
  class ArpaPiemonteCard extends HTMLElement {
    /** @type {CardConfig} */
    #config = {};

    /** @type {CardHass | undefined} */
    #hass;

    /** The stations, found again only when the registries change. */
    /** @type {{ entities: unknown, devices: unknown, stations: Station[] } | undefined} */
    #stations;

    /** The native cards inside. */
    /** @type {any[]} */
    #cards = [];

    /** The layout the native cards were created from. */
    #shown = "";

    #texts = new Texts();

    /** @type {number} */
    #size = 1;

    constructor() {
      super();
      this.attachShadow({ mode: "open" });
    }

    /** @param {CardConfig} config */
    setConfig(config) {
      checkConfig(config);
      this.#config = config;
      this.#update();
    }

    /** @param {CardHass} hass */
    set hass(hass) {
      this.#hass = hass;
      this.#update();
    }

    getCardSize() {
      return this.#size;
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6 };
    }

    /** @param {CardHass} hass */
    static getStubConfig(hass) {
      const station = findStations(hass)[0];
      return station ? { device_id: station.device.id } : {};
    }

    static async getConfigElement() {
      await loadForms();
      return document.createElement(`${CARD}-editor`);
    }

    /** Return the stations, from the registries of the last time they changed. */
    #findStations() {
      const hass = /** @type {CardHass} */ (this.#hass);
      if (this.#stations?.entities !== hass.entities || this.#stations?.devices !== hass.devices) {
        this.#stations = {
          entities: hass.entities,
          devices: hass.devices,
          stations: findStations(hass),
        };
      }
      return this.#stations.stations;
    }

    /**
     * Create the native cards again when what they show changes, such as the
     * color of the level status; otherwise only give them the new states.
     */
    async #update() {
      if (!this.#hass || !this.shadowRoot) {
        return;
      }
      const hass = this.#texts.of(this.#hass, () => this.#update());
      const placed = cardLayout(hass, this.#findStations(), this.#config);
      const shown = JSON.stringify([columnsOf(this.#config), placed]);
      if (shown !== this.#shown) {
        this.#shown = shown;
        const helpers = await /** @type {any} */ (window).loadCardHelpers();
        // A newer update may have created its cards while the helpers loaded
        if (shown !== this.#shown) {
          return;
        }
        this.#render(placed, helpers.createCardElement);
      }
      for (const card of this.#cards) {
        card.hass = this.#hass;
      }
    }

    /**
     * Put the native cards of a layout in the card, each in its place.
     *
     * @param {Placed[]} placed
     * @param {(config: Card) => any} createCardElement
     */
    #render(placed, createCardElement) {
      const root = /** @type {ShadowRoot} */ (this.shadowRoot);
      const style = document.createElement("style");
      style.textContent = STYLE;
      const card = document.createElement("ha-card");
      const content = document.createElement("div");
      content.className = "content";
      content.style.setProperty("--arpa-piemonte-columns", columnsOf(this.#config));
      this.#cards = placed.map(({ card: config, column }) => {
        const element = createCardElement(config);
        element.classList.add(column);
        if (config.type === "heading") {
          element.classList.add(config.heading ? "heading" : "badges");
        }
        if (config.type === "picture-entity") {
          element.classList.add("picture");
        }
        content.append(element);
        return element;
      });
      card.append(content);
      root.replaceChildren(style, card);
      // About a row for each card as wide as the card, and one for each pair of tiles
      const wide = placed.filter(({ column }) => column === "all").length;
      this.#size = wide + Math.ceil((placed.length - wide) / 2);
    }
  }

  customElements.get(CARD) || customElements.define(CARD, ArpaPiemonteCard);
  customElements.get(`${CARD}-editor`) ||
    customElements.define(`${CARD}-editor`, ArpaPiemonteCardEditor);

  // Listed in the card picker, with a preview
  const texts = textsIn(document.documentElement.lang || navigator.language);
  const pickable = /** @type {any} */ (window).customCards ?? [];
  /** @type {any} */ (window).customCards = pickable;
  if (!pickable.some((/** @type {{ type: string }} */ item) => item.type === CARD)) {
    pickable.push({
      type: CARD,
      name: "Arpa Piemonte",
      description: texts.description,
      preview: true,
      documentationURL: "https://github.com/webysther/ha-arpa-piemonte#card",
    });
  }
}
