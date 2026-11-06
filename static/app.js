const elements = {
    status: document.getElementById("connection-status"),
    totalPlays: document.getElementById("total-plays"),
    message: document.getElementById("dashboard-message"),
    artists: document.getElementById("artists-list"),
    tracks: document.getElementById("tracks-list"),
    history: document.getElementById("history-list"),
};

function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function showMessage(text, isError = false) {
    elements.message.textContent = text;
    elements.message.classList.toggle("is-error", isError);
    elements.message.hidden = false;
}

function addEmptyState(container, text) {
    container.replaceChildren(makeElement("p", "empty-state", text));
}

function processHistory(history) {
    const artistCounts = new Map();
    const trackCounts = new Map();

    for (const play of history) {
        const artists = (play.artist || "Artista desconocido")
            .split(",")
            .map((artist) => artist.trim())
            .filter(Boolean);

        for (const artist of artists) {
            artistCounts.set(artist, (artistCounts.get(artist) || 0) + 1);
        }

        const key = play.track_id || `${play.name}:${play.artist}`;
        const current = trackCounts.get(key);
        if (current) {
            current.count += 1;
        } else {
            trackCounts.set(key, {
                name: play.name || "Canción desconocida",
                artist: play.artist || "Artista desconocido",
                count: 1,
            });
        }
    }

    return {
        artists: [...artistCounts.entries()]
            .map(([name, count]) => ({ name, count }))
            .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "es")),
        tracks: [...trackCounts.values()]
            .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "es")),
    };
}

function renderArtists(artists) {
    if (!artists.length) {
        addEmptyState(elements.artists, "Todavía no hay reproducciones guardadas.");
        return;
    }

    const maxCount = artists[0].count;
    const cards = artists.map((artist, index) => {
        const card = makeElement("article", "artist-card");
        const top = makeElement("div", "artist-card-top");
        const nameWrap = makeElement("div", "artist-name-wrap");
        nameWrap.append(
            makeElement("span", "rank-badge", `#${index + 1}`),
            makeElement("span", "artist-name", artist.name),
        );
        top.append(
            nameWrap,
            makeElement("span", "play-count", `${artist.count} ${artist.count === 1 ? "play" : "plays"}`),
        );

        const barTrack = makeElement("div", "bar-track");
        barTrack.setAttribute("role", "progressbar");
        barTrack.setAttribute("aria-label", `Reproducciones de ${artist.name}`);
        barTrack.setAttribute("aria-valuemin", "0");
        barTrack.setAttribute("aria-valuemax", String(maxCount));
        barTrack.setAttribute("aria-valuenow", String(artist.count));
        const barFill = makeElement("div", "bar-fill");
        barFill.style.width = `${Math.max(4, Math.round((artist.count / maxCount) * 100))}%`;
        barTrack.append(barFill);
        card.append(top, barTrack);
        return card;
    });

    elements.artists.replaceChildren(...cards);
}

function renderTracks(tracks) {
    if (!tracks.length) {
        addEmptyState(elements.tracks, "Todavía no hay reproducciones guardadas.");
        return;
    }

    const cards = tracks.map((track, index) => {
        const card = makeElement("article", "track-card");
        const top = makeElement("div", "track-card-top");
        const info = makeElement("div");
        info.append(
            makeElement("p", "track-rank", `FAVORITA #${index + 1}`),
            makeElement("h4", "track-title", track.name),
            makeElement("p", "track-artist", track.artist),
        );
        top.append(info, makeElement("span", "rank-badge", "♡"));

        const bottom = makeElement("div", "track-card-bottom");
        bottom.append(
            makeElement("span", "", "Veces reproducida"),
            makeElement("strong", "", `${track.count} ${track.count === 1 ? "vez" : "veces"}`),
        );
        card.append(top, bottom);
        return card;
    });

    elements.tracks.replaceChildren(...cards);
}

function formatPlayedAt(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value || "Fecha desconocida";
    return new Intl.DateTimeFormat("es-AR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function renderHistory(history) {
    if (!history.length) {
        addEmptyState(elements.history, "Todavía no hay reproducciones guardadas.");
        return;
    }

    const rows = history.map((play, index) => {
        const row = document.createElement("tr");
        for (const value of [
            String(index + 1),
            play.name || "Canción desconocida",
            play.artist || "Artista desconocido",
            formatPlayedAt(play.played_at),
        ]) {
            row.append(makeElement("td", "", value));
        }
        return row;
    });
    elements.history.replaceChildren(...rows);
}

function setupTabs() {
    const buttons = [...document.querySelectorAll(".tab-button")];
    for (const button of buttons) {
        button.addEventListener("click", () => {
            const selectedTab = button.dataset.tab;
            for (const tabButton of buttons) {
                const active = tabButton === button;
                tabButton.classList.toggle("is-active", active);
                tabButton.setAttribute("aria-selected", String(active));
            }
            for (const panel of document.querySelectorAll(".tab-panel")) {
                panel.hidden = panel.id !== `panel-${selectedTab}`;
            }
        });
    }
}

async function loadDashboard() {
    setupTabs();
    try {
        const response = await fetch("/api/history");
        if (!response.ok) {
            throw new Error(`La API respondió HTTP ${response.status}.`);
        }

        const data = await response.json();
        const history = data.history || [];
        const analytics = processHistory(history);
        elements.totalPlays.textContent = String(data.total ?? history.length);
        elements.status.textContent = "Base de datos conectada · datos reales";
        renderArtists(analytics.artists);
        renderTracks(analytics.tracks);
        renderHistory(history);

        if (!history.length) {
            showMessage("La tabla play_history todavía no tiene reproducciones.");
        }
    } catch (error) {
        elements.status.textContent = "No se pudo conectar con la API";
        elements.totalPlays.textContent = "—";
        showMessage(
            `No se pudieron cargar los datos. Comprueba que FastAPI esté iniciado. ${error.message}`,
            true,
        );
        addEmptyState(elements.artists, "Datos no disponibles.");
        addEmptyState(elements.tracks, "Datos no disponibles.");
        addEmptyState(elements.history, "Datos no disponibles.");
    }
}

loadDashboard();
