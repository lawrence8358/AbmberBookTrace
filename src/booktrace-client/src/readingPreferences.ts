import { ref } from "vue";

const key = "booktrace-reading-size";
export const readingSize = ref<"standard" | "large">("standard");

export function initializeReadingPreferences() {
  try {
    readingSize.value = localStorage.getItem(key) === "large" ? "large" : "standard";
  } catch {
    readingSize.value = "standard";
  }
  document.documentElement.classList.toggle("large-text", readingSize.value === "large");
}

export function setReadingSize(value: "standard" | "large"): boolean {
  readingSize.value = value;
  document.documentElement.classList.toggle("large-text", value === "large");
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}
