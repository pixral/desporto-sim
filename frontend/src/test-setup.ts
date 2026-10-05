import { useLang } from "./i18n";

// Tests check the English texts, whatever the machine's locale (Node may report es-ES).
useLang.setState({ lang: "en" });
