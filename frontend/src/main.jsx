import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles.css";
import Home from "./pages/Home.jsx";
import Family from "./pages/Family.jsx";
import Benefits from "./pages/Benefits.jsx";
import ScenariosPage from "./pages/Scenarios.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/f/:token" element={<Family />} />
        <Route path="/benefits" element={<Benefits />} />
        <Route path="/scenarios" element={<ScenariosPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
