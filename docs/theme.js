// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

// Run before the stylesheet so a saved preference applies before first paint.
(() => {
  const storageKey = "ld135-backlight-theme";
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  const themeColors = document.querySelectorAll('meta[name="theme-color"]');
  let preference = "auto";
  let select;

  function updateBrowserColor() {
    const dark = preference === "dark" ||
      (preference === "auto" && systemTheme.matches);
    themeColors.forEach((meta) => {
      meta.content = dark ? "#151c18" : "#f5f5ef";
    });
  }

  function applyTheme(value) {
    preference = ["auto", "dark", "light"].includes(value) ? value : "auto";
    document.documentElement.dataset.theme = preference;
    if (select) select.value = preference;
    updateBrowserColor();
  }

  try {
    preference = window.localStorage.getItem(storageKey);
  } catch {
    // OS detection and the selector still work when storage is unavailable.
  }
  applyTheme(preference);

  systemTheme.addEventListener("change", updateBrowserColor);
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) {
      applyTheme(event.newValue);
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    select = document.getElementById("theme-select");
    select.value = preference;
    select.addEventListener("change", () => {
      applyTheme(select.value);
      try {
        window.localStorage.setItem(storageKey, preference);
      } catch {
        // Keep the selected theme for this visit even if it cannot be saved.
      }
    });
  });
})();
