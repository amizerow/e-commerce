document.addEventListener("DOMContentLoaded", function () {
  const settingsBtn = document.getElementById("settingsBtn");
  const settingsPanel = document.getElementById("settingsPanel");
  const settingsClose = document.getElementById("settingsClose");

  if (!settingsBtn || !settingsPanel) {
    console.error("Settings button or panel not found.");
    return;
  }

  settingsBtn.addEventListener("click", function () {
    settingsPanel.classList.toggle("open");
    settingsPanel.classList.toggle("active");
  });

  if (settingsClose) {
    settingsClose.addEventListener("click", function () {
      settingsPanel.classList.remove("open");
      settingsPanel.classList.remove("active");
    });
  }

  const root = document.documentElement;

  const themeMode = document.getElementById("themeMode");
  const colorTheme = document.getElementById("colorTheme");
  const fontSize = document.getElementById("fontSize");
  const fontFamily = document.getElementById("fontFamily");
  const contrastMode = document.getElementById("contrastMode");
  const readingMode = document.getElementById("readingMode");

  function applySettings() {
    const theme = localStorage.getItem("themeMode") || "light";
    const color = localStorage.getItem("colorTheme") || "blue";
    const size = localStorage.getItem("fontSize") || "medium";
    const family = localStorage.getItem("fontFamily") || "default";
    const contrast = localStorage.getItem("contrastMode") === "true";
    const reading = localStorage.getItem("readingMode") === "true";

    root.setAttribute("data-theme", theme);
    root.setAttribute("data-color", color);
    root.setAttribute("data-font-size", size);
    root.setAttribute("data-font-family", family);

    document.body.classList.toggle("dark-mode", theme === "dark");
    document.body.classList.toggle("high-contrast", contrast);
    document.body.classList.toggle("reading-mode", reading);

    if (themeMode) themeMode.value = theme;
    if (colorTheme) colorTheme.value = color;
    if (fontSize) fontSize.value = size;
    if (fontFamily) fontFamily.value = family;
    if (contrastMode) contrastMode.checked = contrast;
    if (readingMode) readingMode.checked = reading;
  }

  if (themeMode) {
    themeMode.addEventListener("change", function () {
      localStorage.setItem("themeMode", this.value);
      applySettings();
    });
  }

  if (colorTheme) {
    colorTheme.addEventListener("change", function () {
      localStorage.setItem("colorTheme", this.value);
      applySettings();
    });
  }

  if (fontSize) {
    fontSize.addEventListener("change", function () {
      localStorage.setItem("fontSize", this.value);
      applySettings();
    });
  }

  if (fontFamily) {
    fontFamily.addEventListener("change", function () {
      localStorage.setItem("fontFamily", this.value);
      applySettings();
    });
  }

  if (contrastMode) {
    contrastMode.addEventListener("change", function () {
      localStorage.setItem("contrastMode", this.checked);
      applySettings();
    });
  }

  if (readingMode) {
    readingMode.addEventListener("change", function () {
      localStorage.setItem("readingMode", this.checked);
      applySettings();
    });
  }

  applySettings();
});