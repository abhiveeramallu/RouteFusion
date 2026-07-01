import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { RouteFusionProvider } from "./context/RouteFusionContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <RouteFusionProvider>
        <App />
      </RouteFusionProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
