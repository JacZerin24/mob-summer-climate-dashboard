const cache = new Map();

async function fetchJson(path) {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(path, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error(`Unable to load ${path}`);
        return response.json();
      }),
    );
  }
  return cache.get(path);
}

export async function loadStations() {
  return fetchJson(`${import.meta.env.BASE_URL}data/stations.json`);
}

export async function loadStationData(station, year) {
  const [season, climatology, history] = await Promise.all([
    fetchJson(`${import.meta.env.BASE_URL}data/seasons/${year}/${station}.json`),
    fetchJson(`${import.meta.env.BASE_URL}data/climatology/${year}/${station}.json`),
    fetchJson(`${import.meta.env.BASE_URL}data/history/${station}.json`),
  ]);
  return {
    season,
    history,
    climatology: { ...climatology, history },
  };
}
