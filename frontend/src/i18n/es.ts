import { ES_OFFICE } from "./es/office";
import { ES_PEOPLE } from "./es/people";
import { ES_SERVER } from "./es/server";
import { ES_SHELL } from "./es/shell";
import { ES_VIEWS } from "./es/views";

/** Spanish core (title screen, formats). Keys are the English texts used in the code (see i18n/index.ts). */
export const ES_CORE: Record<string, string> = {
  // ---------------------------------------------------------------- start menu
  "A paper-betting management game": "Un juego de gestión de apuestas en papel",
  "Main menu": "Menú principal",
  "Paper betting only: every euro here is simulated.": "Solo apuestas en papel: cada euro aquí es simulado.",
  "An empty building is waiting for a company.": "Un edificio vacío espera a una empresa.",
  "Bankrupt. The building stands closed, and a floor is on fire.": "En bancarrota. El edificio está cerrado y una planta arde.",
  "Fired by the board. The building has new management.": "Despedido por el consejo. El edificio tiene nueva dirección.",
  "Retired after five seasons. Fireworks over the office.": "Jubilado tras cinco temporadas. Fuegos artificiales sobre la oficina.",
  "Day {n}: a small first office.": "Día {n}: una pequeña primera oficina.",
  "{status} · worth {ratio}× its starting capital": "{status} · vale {ratio}× su capital inicial",
  "You run it · advisor: {style}": "La diriges tú · asesor: {style}",
  "AI CEO: {style}": "CEO IA: {style}",
  "day {n}": "día {n}",
  "No company yet.": "Todavía no hay empresa.",
  "Connecting to the simulation server…": "Conectando con el servidor de la simulación…",
  Continue: "Continuar",
  "New game": "Nueva partida",
  "Load game": "Cargar partida",
  Language: "Idioma",
  "Who runs the company?": "¿Quién dirige la empresa?",
  "You, as CEO": "Tú, como CEO",
  "Briefings, hiring and firing, money, desks and the LAB, with an AI advisor. Five seasons, don't get fired.":
    "Reuniones, contrataciones y despidos, dinero, mesas y el LAB, con un asesor IA. Cinco temporadas, que no te despidan.",
  "An AI CEO": "Un CEO IA",
  "Watch an AI CEO with a personality run the company on its own.": "Mira cómo un CEO IA con personalidad dirige la empresa solo.",
  Back: "Volver",
  "Loading…": "Cargando…",
  "No saves yet.": "Todavía no hay partidas guardadas.",
  ended: "terminada",
  "FOR LEASE": "SE ALQUILA",
  CLOSED: "CERRADO",
  "ON AIR": "AL AIRE",
  "UNDER NEW MANAGEMENT": "NUEVA DIRECCIÓN",
  "THANK YOU, BOSS!": "¡GRACIAS, JEFE!",

  // ---------------------------------------------------------------- formats
  Home: "Local",
  Draw: "Empate",
  "Away|market": "Visitante",
  "Over 2.5": "Más de 2,5",
  "Under 2.5": "Menos de 2,5",
  Thriving: "Próspera",
  Stable: "Estable",
  Strained: "Tensa",
  Distress: "En apuros",
  Bankrupt: "En bancarrota",
  "Morning briefing": "Reunión matinal",
  "Analysis & betting": "Análisis y apuestas",
  "Matches live": "Partidos en juego",
  Settlement: "Liquidación",
};

/** Everything, merged. A test checks that every t("…") text in the code has an entry here. */
export const ES: Record<string, string> = { ...ES_SERVER, ...ES_SHELL, ...ES_PEOPLE, ...ES_VIEWS, ...ES_OFFICE, ...ES_CORE };
