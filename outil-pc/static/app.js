(function () {
  const cfg = window.POSITION_CONFIG || {};
  const PREVIEW = !!cfg.preview;
  const PREVIEW_NOTICE = "Aperçu : lance start.bat sur le PC pour appliquer la position";
  const LS_KEY = "position-iphone-lieux";
  const PARIS = [cfg.parisLat || 48.8566, cfg.parisLon || 2.3522];

  const el = (id) => document.getElementById(id);
  const banniere = el("banniere");
  const voyant = el("voyant");
  const etatCourt = el("etat-court");
  const query = el("query");
  const suggestions = el("suggestions");
  const pickLabel = el("pick-label");
  const pickCoords = el("pick-coords");
  const btnApply = el("btn-apply");
  const btnReset = el("btn-reset");
  const btnSearch = el("btn-search");
  const btnFavori = el("btn-favori");
  const msg = el("msg");
  const sim = el("sim");
  const simLabel = el("sim-label");
  const simCoords = el("sim-coords");
  const etatDetail = el("etat-detail");
  const listeFavoris = el("liste-favoris");
  const listeRecents = el("liste-recents");
  const videFavoris = el("vide-favoris");
  const videRecents = el("vide-recents");

  let hasPoint = false;
  let current = { lat: null, lon: null, label: "" };
  let map, marker;

  function showMsg(text, kind) {
    if (!msg) return;
    msg.className = "msg show " + (kind || "ok");
    msg.textContent = text;
  }

  function hideSuggestions() {
    if (!suggestions) return;
    suggestions.style.display = "none";
    suggestions.innerHTML = "";
  }

  function loadLieux() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
      return {
        favoris: Array.isArray(raw.favoris) ? raw.favoris : [],
        recents: Array.isArray(raw.recents) ? raw.recents : [],
      };
    } catch (e) {
      return { favoris: [], recents: [] };
    }
  }

  function saveLieux(data) {
    localStorage.setItem(LS_KEY, JSON.stringify(data));
  }

  function memeLieu(a, b) {
    return Math.abs(a.lat - b.lat) < 1e-5 && Math.abs(a.lon - b.lon) < 1e-5;
  }

  function estFavori(point) {
    if (!point || point.lat == null) return false;
    return loadLieux().favoris.some((f) => memeLieu(f, point));
  }

  function ajouterRecent(point) {
    if (!point || point.lat == null) return;
    const data = loadLieux();
    data.recents = [point, ...data.recents.filter((r) => !memeLieu(r, point))].slice(0, 12);
    saveLieux(data);
    peindreAdresses();
    majFavoriBtn();
  }

  function basculerFavori() {
    if (!hasPoint) return;
    const data = loadLieux();
    if (estFavori(current)) {
      data.favoris = data.favoris.filter((f) => !memeLieu(f, current));
    } else {
      data.favoris = [current, ...data.favoris.filter((f) => !memeLieu(f, current))].slice(0, 20);
    }
    saveLieux(data);
    peindreAdresses();
    majFavoriBtn();
  }

  function majFavoriBtn() {
    if (!btnFavori) return;
    btnFavori.disabled = !hasPoint;
    btnFavori.textContent = estFavori(current) ? "Retirer des favoris" : "Ajouter aux favoris";
  }

  function peindreAdresses() {
    const data = loadLieux();
    remplirListe(listeFavoris, videFavoris, data.favoris, true);
    remplirListe(listeRecents, videRecents, data.recents, false);
  }

  function remplirListe(conteneur, vide, items, favori) {
    if (!conteneur) return;
    conteneur.querySelectorAll(".lieu-wrap").forEach((n) => n.remove());
    if (vide) vide.hidden = items.length > 0;
    items.forEach((item) => {
      const wrap = document.createElement("div");
      wrap.className = "lieu-wrap";
      wrap.style.display = "flex";
      wrap.style.gap = "8px";
      wrap.style.alignItems = "stretch";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "lieu";
      b.innerHTML = "<span class=\"nom\"></span>";
      b.querySelector(".nom").textContent = item.label || (item.lat.toFixed(5) + ", " + item.lon.toFixed(5));
      b.addEventListener("click", () => {
        setPoint(item.lat, item.lon, item.label, true);
        ajouterRecent(item);
        basculerVue("carte");
      });
      const star = document.createElement("button");
      star.type = "button";
      star.className = "etoile secondaire";
      star.setAttribute("aria-label", favori ? "Retirer des favoris" : "Ajouter aux favoris");
      star.textContent = favori ? "★" : "☆";
      star.addEventListener("click", (ev) => {
        ev.stopPropagation();
        current = item;
        hasPoint = true;
        basculerFavori();
      });
      wrap.appendChild(b);
      wrap.appendChild(star);
      conteneur.appendChild(wrap);
    });
  }

  function setPoint(lat, lon, label, fly) {
    hasPoint = true;
    current = { lat, lon, label: label || (lat.toFixed(6) + ", " + lon.toFixed(6)) };
    if (marker && map) {
      marker.setLatLng([lat, lon]);
      if (!map.hasLayer(marker)) marker.addTo(map);
      if (fly) map.flyTo([lat, lon], Math.max(map.getZoom(), 16), { duration: 0.7 });
    }
    if (pickLabel) pickLabel.textContent = current.label;
    if (pickCoords) pickCoords.textContent = lat.toFixed(6) + ", " + lon.toFixed(6);
    if (btnApply) btnApply.disabled = false;
    majFavoriBtn();
  }

  function pinIcon() {
    return L.divIcon({
      className: "",
      html: '<div class="pin-laiton"></div>',
      iconSize: [22, 22],
      iconAnchor: [11, 22],
    });
  }

  async function apiReverse(lat, lon) {
    if (PREVIEW) {
      const url = "https://nominatim.openstreetmap.org/reverse?" + new URLSearchParams({
        lat: String(lat), lon: String(lon), format: "jsonv2", addressdetails: "1",
      });
      const r = await fetch(url, { headers: { "Accept-Language": "fr" } });
      if (!r.ok) throw new Error("reverse");
      const data = await r.json();
      return data.display_name || (lat.toFixed(6) + ", " + lon.toFixed(6));
    }
    const r = await fetch("/api/reverse?lat=" + lat + "&lon=" + lon);
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || "reverse");
    return data.label;
  }

  async function apiGeocode(q) {
    if (PREVIEW) {
      const url = "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({
        q: q, format: "jsonv2", limit: "5", addressdetails: "1",
      });
      const r = await fetch(url, { headers: { "Accept-Language": "fr" } });
      if (!r.ok) throw new Error("search");
      const results = await r.json();
      return (results || []).map((item) => ({
        label: item.display_name,
        lat: parseFloat(item.lat),
        lon: parseFloat(item.lon),
      }));
    }
    const r = await fetch("/api/geocode?q=" + encodeURIComponent(q));
    const data = await r.json();
    if (!data.ok || !data.results) throw new Error(data.error || "Aucun résultat.");
    return data.results;
  }

  function updateSim(simData) {
    if (simData && simData.active && simData.lat != null) {
      if (sim) sim.classList.add("show");
      if (simLabel) simLabel.textContent = simData.label || "Position simulée";
      if (simCoords) simCoords.textContent = Number(simData.lat).toFixed(6) + ", " + Number(simData.lon).toFixed(6);
    } else {
      if (sim) sim.classList.remove("show");
      if (simLabel) simLabel.textContent = "Aucune simulation en cours.";
      if (simCoords) simCoords.textContent = "";
    }
  }

  function peindreEtat(data) {
    if (!etatDetail) return;
    if (PREVIEW) {
      etatDetail.innerHTML = "<p>Ceci est un aperçu. Pour appliquer une position à l’iPhone, lance <strong>start.bat</strong> sur le PC, branche le téléphone en USB, puis ouvre le lien avec le QR code.</p>";
      return;
    }
    const dev = data && data.device;
    const simData = (data && data.simulation) || {};
    const lignes = [];
    if (dev) {
      lignes.push("<p class=\"ok\"><strong>" + (dev.name || "iPhone") + "</strong> — iOS " + (dev.version || "?") + (dev.connection ? " · " + dev.connection : "") + "</p>");
      if (data.tunneld) lignes.push("<p class=\"muted\">tunneld est joignable.</p>");
      else if (dev.ios17) lignes.push("<p class=\"muted\">Tunnel automatique (sans administrateur), adapté à iOS 17.4 et plus.</p>");
    } else {
      lignes.push("<p class=\"erreur\">" + ((data && data.error) || "Aucun iPhone détecté.") + "</p>");
    }
    if (simData.active) {
      lignes.push("<p class=\"ok\"><strong>Position simulée :</strong> " + (simData.label || "") + "</p>");
      lignes.push("<p class=\"coords\">" + Number(simData.lat).toFixed(6) + ", " + Number(simData.lon).toFixed(6) + "</p>");
    } else {
      lignes.push("<p class=\"muted\">Aucune simulation en cours. La position réelle de l’iPhone s’applique.</p>");
    }
    etatDetail.innerHTML = lignes.join("");
  }

  async function refreshStatus() {
    if (PREVIEW) {
      if (banniere) banniere.textContent = "Aperçu — lance start.bat sur le PC pour appliquer la position";
      if (voyant) voyant.className = "voyant";
      if (etatCourt) etatCourt.textContent = "Aperçu";
      peindreEtat(null);
      return;
    }
    try {
      const r = await fetch("/api/status");
      const data = await r.json();
      const dev = data.device;
      const simData = data.simulation || {};
      updateSim(simData);
      peindreEtat(data);
      if (dev) {
        if (voyant) voyant.className = "voyant ok";
        if (etatCourt) etatCourt.textContent = (dev.name || "iPhone") + " · iOS " + (dev.version || "?");
        if (simData.active) {
          if (banniere) banniere.textContent = "Position simulée : " + (simData.label || (Number(simData.lat).toFixed(5) + ", " + Number(simData.lon).toFixed(5)));
        } else {
          if (banniere) banniere.textContent = (dev.name || "iPhone") + " connecté — iOS " + (dev.version || "?") + ". Branche le câble pour appliquer une position.";
        }
      } else {
        if (voyant) voyant.className = "voyant non";
        if (etatCourt) etatCourt.textContent = "Hors ligne";
        if (banniere) banniere.textContent = "Aucun iPhone détecté. Branche-le avec un câble USB.";
      }
    } catch (e) {
      if (voyant) voyant.className = "voyant non";
      if (etatCourt) etatCourt.textContent = "Serveur injoignable";
      if (banniere) banniere.textContent = "Serveur local injoignable. start.bat est-il encore ouvert ?";
    }
  }

  function basculerVue(nom) {
    document.querySelectorAll(".vue").forEach((v) => {
      v.hidden = v.id !== "vue-" + nom;
    });
    document.querySelectorAll(".nav button").forEach((b) => {
      if (b.getAttribute("data-vue") === nom) b.classList.remove("secondaire");
      else b.classList.add("secondaire");
    });
    if (nom === "carte" && map) {
      setTimeout(() => map.invalidateSize(), 80);
    }
    if (nom === "adresses") peindreAdresses();
  }

  function initMap() {
    map = L.map("map", { zoomControl: false, tap: true }).setView(PARIS, 13);
    L.control.zoom({ position: "topright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);
    marker = L.marker(PARIS, { draggable: true, icon: pinIcon() });
    setTimeout(() => map.invalidateSize(), 200);
    window.addEventListener("resize", () => map.invalidateSize());

    marker.on("dragend", async () => {
      const { lat, lng } = marker.getLatLng();
      setPoint(lat, lng, "Point déplacé sur la carte…", false);
      try { setPoint(lat, lng, await apiReverse(lat, lng), false); } catch (e) {
        setPoint(lat, lng, lat.toFixed(6) + ", " + lng.toFixed(6), false);
      }
    });

    map.on("click", async (e) => {
      const { lat, lng } = e.latlng;
      setPoint(lat, lng, "Recherche de l'adresse…", false);
      try { setPoint(lat, lng, await apiReverse(lat, lng), false); } catch (e) {
        setPoint(lat, lng, lat.toFixed(6) + ", " + lng.toFixed(6), false);
      }
    });
  }

  function lireHash() {
    const raw = (location.hash || "").replace(/^#/, "");
    if (!raw) return;
    const p = new URLSearchParams(raw);
    const lat = parseFloat(p.get("lat"));
    const lon = parseFloat(p.get("lon"));
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      setPoint(lat, lon, p.get("label") || "", true);
    }
  }

  el("search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = query.value.trim();
    if (!q) return;
    hideSuggestions();
    btnSearch.disabled = true;
    try {
      const results = await apiGeocode(q);
      if (!results.length) {
        showMsg("Aucun résultat pour cette adresse. Essaie d'être plus précis.", "err");
        return;
      }
      const first = results[0];
      setPoint(first.lat, first.lon, first.label, true);
      ajouterRecent({ lat: first.lat, lon: first.lon, label: first.label });
      showMsg("Adresse trouvée. Vérifie le point, puis applique la position.", "ok");
      if (results.length > 1) {
        results.forEach((item) => {
          const li = document.createElement("li");
          const b = document.createElement("button");
          b.type = "button";
          b.textContent = item.label;
          b.addEventListener("click", () => {
            setPoint(item.lat, item.lon, item.label, true);
            ajouterRecent({ lat: item.lat, lon: item.lon, label: item.label });
            hideSuggestions();
          });
          li.appendChild(b);
          suggestions.appendChild(li);
        });
        suggestions.style.display = "block";
      }
    } catch (err) {
      showMsg(err.message || "La recherche d'adresse a échoué.", "err");
    } finally {
      btnSearch.disabled = false;
    }
  });

  btnApply.addEventListener("click", async () => {
    if (!hasPoint) return;
    if (PREVIEW) {
      showMsg(PREVIEW_NOTICE, "err");
      return;
    }
    btnApply.disabled = true;
    showMsg("Envoi de la position à l'iPhone…", "ok");
    try {
      const r = await fetch("/api/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(current),
      });
      const data = await r.json();
      if (data.ok) {
        showMsg(data.message, "ok");
        ajouterRecent(current);
      } else showMsg(data.error || "Échec.", "err");
    } catch (err) {
      showMsg("Impossible de joindre le serveur local.", "err");
    } finally {
      btnApply.disabled = !hasPoint;
      refreshStatus();
    }
  });

  btnReset.addEventListener("click", async () => {
    if (PREVIEW) {
      showMsg(PREVIEW_NOTICE, "err");
      return;
    }
    btnReset.disabled = true;
    showMsg("Rétablissement de la position réelle…", "ok");
    try {
      const r = await fetch("/api/reset", { method: "POST" });
      const data = await r.json();
      if (data.ok) showMsg(data.message, "ok");
      else showMsg(data.error || "Échec.", "err");
    } catch (err) {
      showMsg("Impossible de joindre le serveur local.", "err");
    } finally {
      btnReset.disabled = false;
      refreshStatus();
    }
  });

  if (btnFavori) btnFavori.addEventListener("click", basculerFavori);

  document.querySelectorAll(".nav button").forEach((b) => {
    b.addEventListener("click", () => basculerVue(b.getAttribute("data-vue")));
  });

  initMap();
  peindreAdresses();
  majFavoriBtn();
  lireHash();
  basculerVue("carte");
  refreshStatus();
  if (!PREVIEW) setInterval(refreshStatus, 5000);

  if (!PREVIEW && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
})();
