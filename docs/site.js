// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

// This preview changes only the illustration on this page.
const preview = document.querySelector(".preview");
const colors = [
  { name: "White", light: "#ffffff", glow: "rgba(255,255,255,.3)" },
  { name: "Blue", light: "#9bbfff", glow: "rgba(87,142,255,.55)" },
  { name: "Red", light: "#ffaaa0", glow: "rgba(255,110,90,.5)" },
  { name: "Green", light: "#a4f9b2", glow: "rgba(100,245,137,.4)" },
  { name: "Cyan", light: "#a1f4f6", glow: "rgba(95,228,240,.5)" },
  { name: "Yellow", light: "#fff2a6", glow: "rgba(245,220,87,.5)" },
  { name: "Pink", light: "#f6b3fa", glow: "rgba(235,125,245,.5)" }
];
let colorIndex = 0;

function showColor(index) {
  colorIndex = index;
  const color = colors[index];
  preview.style.setProperty("--key-light", color.light);
  preview.style.setProperty("--key-glow", color.glow);
  document.getElementById("preview-color").textContent = color.name;
  document.getElementById("preview-announcement").textContent =
    `Preview color: ${color.name.toLowerCase()}. Your keyboard has not been changed.`;
}

// Enhance the native HTML/CSS picker with the original one-click cycle.
document.getElementById("preview-palette").reset();
const cycleButton = document.getElementById("cycle-color");
cycleButton.removeAttribute("popovertarget");
cycleButton.setAttribute("aria-label", "Cycle the keyboard preview color");
cycleButton.addEventListener("click", () => {
  showColor((colorIndex + 1) % colors.length);
});
document.getElementById("reset-color").addEventListener("click", () => showColor(0));

// Commands remain visible and selectable when JavaScript or clipboard access
// is unavailable. Only the website theme preference is stored locally;
// no requests, analytics, or device APIs are used.
if (navigator.clipboard && window.isSecureContext) {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.removeAttribute("popovertarget");
    const label = button.textContent;
    let resetTimer;
    button.addEventListener("click", async () => {
      const text = document.getElementById(button.dataset.copy).textContent;
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied ✓";
        document.getElementById("copy-announcement").textContent =
          "Command copied to the clipboard.";
        window.clearTimeout(resetTimer);
        resetTimer = window.setTimeout(() => {
          button.textContent = label;
        }, 2200);
      } catch {
        document.getElementById("copy-announcement").textContent =
          "Clipboard access is unavailable. Select and copy the command directly.";
      }
    });
  });
}
