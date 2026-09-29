const form = document.querySelector("#search-form");
const cityInput = document.querySelector("#city-input");
const unitButtons = [...document.querySelectorAll(".unit-button")];
const searchButton = document.querySelector(".search-button");
const statusMessage = document.querySelector("#status-message");
const result = document.querySelector("#weather-result");
let selectedUnit = "celsius";
let lastCity = "";
let requestSequence = 0;

const weatherIcons = {
  "clear-day": "☀️",
  "clear-night": "🌙",
  "partly-cloudy-day": "🌤️",
  "partly-cloudy-night": "☁️",
  cloudy: "☁️",
  fog: "🌫️",
  drizzle: "🌦️",
  rain: "🌧️",
  snow: "❄️",
  showers: "🌦️",
  "snow-showers": "🌨️",
  thunderstorm: "⛈️"
};

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("is-error", isError);
}

function formatObservedTime(value, timeZone) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Current local conditions";
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZone
  }).format(date);
  return `Observed ${time} local time`;
}

function renderWeather(weather) {
  const location = [weather.city, weather.region, weather.country]
    .filter((part, index, parts) => part && parts.indexOf(part) === index)
    .join(", ");

  document.querySelector("#place-name").textContent = location;
  document.querySelector("#observed-time").textContent = formatObservedTime(
    weather.observed_at,
    weather.timezone
  );
  document.querySelector("#sky-icon").textContent = weatherIcons[weather.icon_key] || "☁️";
  document.querySelector("#temperature").textContent = `${Math.round(weather.temperature)}°`;
  document.querySelector("#condition").textContent = weather.condition;
  document.querySelector("#feels-like").textContent = `Feels like ${Math.round(weather.feels_like)}°`;
  document.querySelector("#humidity").textContent = `${weather.humidity}%`;
  document.querySelector("#wind").textContent = `${Math.round(weather.wind_speed)} ${weather.wind_unit}`;
  document.querySelector("#timezone").textContent = weather.timezone.replaceAll("_", " ");
  result.hidden = false;
  setStatus("Weather updated.");
}

async function loadWeather(city) {
  const sequence = ++requestSequence;
  searchButton.disabled = true;
  result.hidden = true;
  setStatus("Finding current conditions…");

  try {
    const response = await fetch("/api/weather", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city, unit: selectedUnit })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Weather lookup failed. Try again.");
    if (sequence !== requestSequence) return;
    lastCity = city;
    renderWeather(data);
  } catch (error) {
    if (sequence === requestSequence) setStatus(error.message, true);
  } finally {
    if (sequence === requestSequence) searchButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const city = cityInput.value.trim();
  if (!city) {
    setStatus("Enter a city name to continue.", true);
    cityInput.focus();
    return;
  }
  loadWeather(city);
});

unitButtons.forEach((button) => {
  button.addEventListener("click", () => {
    selectedUnit = button.dataset.unit;
    unitButtons.forEach((unitButton) => {
      const isSelected = unitButton === button;
      unitButton.classList.toggle("is-selected", isSelected);
      unitButton.setAttribute("aria-pressed", String(isSelected));
    });
    if (lastCity) loadWeather(lastCity);
  });
});