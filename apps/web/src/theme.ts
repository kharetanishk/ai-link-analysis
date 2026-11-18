export type Theme = "light" | "dark";

const KEY = "linklens-theme";

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function initTheme(): Theme {
  const param = new URLSearchParams(location.search).get("theme");
  const theme: Theme =
    param === "light" || param === "dark"
      ? param
      : stored() ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
  return theme;
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* private mode: sirf is session ke liye */
  }
}
