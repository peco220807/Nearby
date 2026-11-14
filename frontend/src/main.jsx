import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Family from "./pages/Family.jsx";
import Benefits from "./pages/Benefits.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/f/:token" element={<Family />} />
        <Route path="/benefits" element={<Benefits />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
