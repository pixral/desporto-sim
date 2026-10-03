import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/silkscreen/400.css";
import "@fontsource/vt323/400.css";
import "@fontsource/pixelify-sans/400.css";
import "./styles/global.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
