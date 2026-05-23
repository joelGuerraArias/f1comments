(() => {
  // frontend/app.jsx
  var { useState, useEffect, useRef } = React;
  var App = () => {
    const [view, setView] = useState("positions");
    const [raceState, setRaceState] = useState({ lap: 0, positions: [], race_control: [], session_info: {}, total_laps: 0 });
    const [isNarrationActive, setIsNarrationActive] = useState(false);
    const [narrationHistory, setNarrationHistory] = useState([]);
    const [audioQueue, setAudioQueue] = useState([]);
    const [pendingSegments, setPendingSegments] = useState([]);
    const [playedSegments, setPlayedSegments] = useState([]);
    const [narrationSubTab, setNarrationSubTab] = useState("upcoming");
    const [isPlaying, setIsPlaying] = useState(false);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [apiStatus, setApiStatus] = useState({ datalive: "checking", openai: "checking" });
    const [endpointsData, setEndpointsData] = useState(null);
    const [endpointsLoading, setEndpointsLoading] = useState(false);
    const [twoCommentaries, setTwoCommentaries] = useState(null);
    const [twoCommentariesLoading, setTwoCommentariesLoading] = useState(false);
    const [commentaryNow, setCommentaryNow] = useState(null);
    const [commentaryNowLoading, setCommentaryNowLoading] = useState(false);
    const [adminConfig, setAdminConfig] = useState({ race_name: "", race_info: "", context: "" });
    const [adminSaving, setAdminSaving] = useState(false);
    const [adminSaved, setAdminSaved] = useState(false);
    const [narrationSource, setNarrationSource] = useState("api");
    const [micBusy, setMicBusy] = useState("idle");
    const [micFeedback, setMicFeedback] = useState("");
    const [apiCallsCount, setApiCallsCount] = useState(0);
    const [dataEndpoints, setDataEndpoints] = useState({});
    const [dataLoading, setDataLoading] = useState({});
    const lastNarrationId = useRef(0);
    const messagesEndRef = useRef(null);
    const currentAudioRef = useRef(null);
    const currentPlayingSegmentRef = useRef(null);
    const nextPreloadedRef = useRef(null);
    const isPlayingRef = useRef(false);
    const micRecorderRef = useRef(null);
    const micChunksRef = useRef([]);
    const micStreamRef = useRef(null);
    const API_BASE = "";
    const positionsSortedByRank = React.useMemo(() => [...raceState.positions || []].sort((a, b) => {
      const pa = Number(a.position);
      const pb = Number(b.position);
      const fa = Number.isFinite(pa);
      const fb = Number.isFinite(pb);
      if (fa && fb) return pa - pb;
      if (fa && !fb) return -1;
      if (!fa && fb) return 1;
      return String(a.tla || "").localeCompare(String(b.tla || ""));
    }), [raceState.positions]);
    const getTeamColor = (team) => {
      const colors = {
        "Red Bull Racing": "#3671C6",
        "Ferrari": "#E8002D",
        "Scuderia Ferrari": "#E8002D",
        "Mercedes": "#27F4D2",
        "McLaren": "#FF8000",
        "Aston Martin": "#229971",
        "Alpine": "#FF87BC",
        "Williams": "#64C4FF",
        "RB": "#6692FF",
        "Kick Sauber": "#52E252",
        "Haas F1 Team": "#B6BABD",
        "Racing Bulls": "#6692FF",
        "Audi": "#F20000",
        "Cadillac": "#9d8d7a"
      };
      return colors[team] || "#FFFFFF";
    };
    const F1_LOGO_CDN_PREFIX = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1";
    const FERRARI_LOGO_LIGHT_URL = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1/2025/ferrari/2025ferrarilogolight.webp";
    const ALPINE_LOGO_WHITE_URL = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1/2025/alpine/2025alpinelogowhite.webp";
    const RED_BULL_RACING_LOGO_WHITE_URL = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1/2025/redbullracing/2025redbullracinglogowhite.webp";
    const MERCEDES_LOGO_WHITE_URL = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1/2025/mercedes/2025mercedeslogowhite.webp";
    const CADILLAC_LOGO_WHITE_URL = "https://media.formula1.com/image/upload/c_fit,h_64/q_auto/v1740000001/common/f1/2026/cadillac/2026cadillaclogowhite.webp";
    const TEAM_F1_LOGO_PATH = {
      "McLaren": { season: "2025", dir: "mclaren" },
      "Aston Martin": { season: "2025", dir: "astonmartin" },
      "Williams": { season: "2025", dir: "williams" },
      "Racing Bulls": { season: "2025", dir: "racingbulls" },
      "RB": { season: "2025", dir: "racingbulls" },
      "Kick Sauber": { season: "2025", dir: "kicksauber" },
      "Haas F1 Team": { season: "2025", dir: "haas" },
      "Haas": { season: "2025", dir: "haas" },
      Audi: { season: "2026", dir: "audi", variant: "white" }
    };
    const getTeamLogoUrl = (team) => {
      if (team === "Ferrari" || team === "Scuderia Ferrari") {
        return FERRARI_LOGO_LIGHT_URL;
      }
      if (team === "Alpine") {
        return ALPINE_LOGO_WHITE_URL;
      }
      if (team === "Red Bull Racing") {
        return RED_BULL_RACING_LOGO_WHITE_URL;
      }
      if (team === "Mercedes") {
        return MERCEDES_LOGO_WHITE_URL;
      }
      if (team === "Cadillac") {
        return CADILLAC_LOGO_WHITE_URL;
      }
      const m = team && TEAM_F1_LOGO_PATH[team];
      if (m) {
        if (m.variant === "white") {
          return `${F1_LOGO_CDN_PREFIX}/${m.season}/${m.dir}/${m.season}${m.dir}logowhite.webp`;
        }
        const file = `${m.season}${m.dir}logolight.webp`;
        return `${F1_LOGO_CDN_PREFIX}/${m.season}/${m.dir}/${file}`;
      }
      return "";
    };
    const formatPodiumGap = (position, gap) => {
      const g = Number(gap);
      if (position === 1 || !Number.isFinite(g) || g === 0) return "+0S";
      return `+${g.toFixed(3)}`;
    };
    const driverLastName = (name) => {
      if (!name) return "";
      const parts = name.trim().split(/\s+/);
      return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : name.toUpperCase();
    };
    const TEAM_PODIUM_LABEL = {
      "Red Bull Racing": "RED BULL",
      "Haas F1 Team": "HAAS",
      "Racing Bulls": "RACING BULLS",
      "RB": "RACING BULLS",
      "Kick Sauber": "KICK SAUBER",
      "Aston Martin": "ASTON MARTIN",
      "Scuderia Ferrari": "FERRARI"
    };
    const teamPodiumLabel = (team) => {
      if (TEAM_PODIUM_LABEL[team]) return TEAM_PODIUM_LABEL[team];
      return (team || "").toUpperCase();
    };
    useEffect(() => {
      isPlayingRef.current = isPlaying;
    }, [isPlaying]);
    useEffect(() => {
      const fetchState = async () => {
        try {
          const res = await fetch(`${API_BASE}/api/state`);
          const data = await res.json();
          if (!isPlayingRef.current) {
            setRaceState({
              lap: data.lap != null ? data.lap : 0,
              total_laps: data.total_laps != null ? data.total_laps : 0,
              positions: Array.isArray(data.positions) ? data.positions : [],
              race_control: Array.isArray(data.race_control) ? data.race_control : [],
              weather: data.weather,
              session_info: data.session_info || {}
            });
          }
        } catch (err) {
          console.error("Error fetching state", err);
        }
      };
      fetchState();
      const interval = setInterval(fetchState, 2e3);
      return () => clearInterval(interval);
    }, []);
    useEffect(() => {
      const fetchStats = async () => {
        try {
          const res = await fetch(`${API_BASE}/api/stats`);
          const data = await res.json();
          setApiCallsCount(data.api_calls != null ? data.api_calls : 0);
        } catch (err) {
          console.error("Error fetching stats", err);
        }
      };
      fetchStats();
      const interval = setInterval(fetchStats, 2e3);
      return () => clearInterval(interval);
    }, []);
    useEffect(() => {
      const fetchAdmin = async () => {
        try {
          const res = await fetch(`${API_BASE}/api/admin/config`);
          const data = await res.json();
          setAdminConfig({ race_name: data.race_name || "", race_info: data.race_info || "", context: data.context || "" });
        } catch (err) {
          console.error("Error fetching admin config", err);
        }
      };
      if (view === "admin") fetchAdmin();
    }, [view]);
    useEffect(() => {
      fetch(`${API_BASE}/api/admin/config`).then((res) => res.json()).then((data) => setAdminConfig((prev) => ({ ...prev, race_name: data.race_name || "", race_info: data.race_info || "", context: data.context || "" }))).catch(() => {
      });
    }, []);
    useEffect(() => {
      fetch(`${API_BASE}/api/narration/source`).then((res) => res.json()).then((data) => setNarrationSource((data.source || "api").toLowerCase())).catch(() => {
      });
    }, []);
    const fetchNarration = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/narration/latest`);
        const data = await res.json();
        if (data && data.id && data.id !== lastNarrationId.current) {
          lastNarrationId.current = data.id;
          setNarrationHistory((prev) => [...prev, data]);
          if (data.state) {
            const s = data.state;
            setRaceState((prev) => ({
              ...prev,
              lap: s.lap != null ? s.lap : prev.lap,
              total_laps: s.total_laps != null ? s.total_laps : prev.total_laps,
              positions: Array.isArray(s.positions) ? s.positions : prev.positions || [],
              race_control: Array.isArray(s.race_control) ? s.race_control : prev.race_control || [],
              weather: s.weather != null ? s.weather : prev.weather,
              session_info: s.session_info != null ? s.session_info : prev.session_info
            }));
          }
          setApiStatus((prev) => ({ ...prev, datalive: "connected" }));
          if (isNarrationActive && data.comments) {
            const newSegments = data.comments.map((segment) => ({
              narrator: segment.narrator,
              text: segment.text,
              lap: data.lap,
              timestamp: data.timestamp,
              listener: false
            }));
            data.comments.forEach((segment) => {
              const audioUrl = `${API_BASE}/api/narration/audio?text=${encodeURIComponent(segment.text)}&voice=${segment.narrator}`;
              setAudioQueue((prev) => [...prev, audioUrl]);
            });
            setPendingSegments((prev) => [...prev, ...newSegments]);
            setApiStatus((prev) => ({ ...prev, openai: "connected" }));
          }
        }
      } catch (err) {
        console.error("Error fetching narration", err);
        setApiStatus((prev) => ({ ...prev, datalive: "error", openai: "error" }));
      }
    };
    const cleanupMicStream = () => {
      const stream = micStreamRef.current;
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        micStreamRef.current = null;
      }
    };
    const handleMicToggle = async () => {
      if (micBusy === "sending") return;
      if (micBusy === "idle") {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          setMicFeedback("Este navegador no permite usar el micr\xF3fono aqu\xED.");
          return;
        }
        setMicFeedback("");
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          micStreamRef.current = stream;
          micChunksRef.current = [];
          let preferredMime = "";
          const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
          for (const c of candidates) {
            if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) {
              preferredMime = c;
              break;
            }
          }
          let recorder = null;
          try {
            recorder = preferredMime ? new MediaRecorder(stream, { mimeType: preferredMime }) : new MediaRecorder(stream);
          } catch {
            recorder = new MediaRecorder(stream);
          }
          recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) micChunksRef.current.push(event.data);
          };
          recorder.onerror = () => setMicFeedback("Error del micr\xF3fono al grabar.");
          recorder.onstop = async () => {
            cleanupMicStream();
            micRecorderRef.current = null;
            try {
              const mime = recorder.mimeType || preferredMime || "audio/webm";
              const blob = new Blob(micChunksRef.current, { type: mime });
              micChunksRef.current = [];
              if (!blob.size) {
                setMicFeedback("Grabaci\xF3n vac\xEDa; prob\xE1 otra vez.");
                setMicBusy("idle");
                return;
              }
              const fd = new FormData();
              fd.append("audio", blob, "listener.webm");
              const resp = await fetch(`${API_BASE}/api/interaction/voice`, { method: "POST", body: fd });
              const data = await resp.json();
              if (data.error || !Array.isArray(data.comments) || data.comments.length === 0) {
                setMicFeedback(data.error ? data.error : "Sin respuesta de los locutores.");
                setMicBusy("idle");
                return;
              }
              const lapUse = typeof data.lap === "number" ? data.lap : 1;
              const tsNow = Date.now() / 1e3;
              const newSegments = data.comments.map((segment) => ({
                narrator: segment.narrator,
                text: segment.text,
                lap: lapUse,
                timestamp: tsNow,
                listener: true
              }));
              const newUrls = data.comments.map(
                (segment) => `${API_BASE}/api/narration/audio?text=${encodeURIComponent(segment.text)}&voice=${segment.narrator}`
              );
              setAudioQueue((prev) => [...newUrls, ...prev]);
              setPendingSegments((prev) => [...newSegments, ...prev]);
              nextPreloadedRef.current = null;
              setApiStatus((prev) => ({ ...prev, openai: "connected" }));
              const shortTxt = typeof data.transcript === "string" ? data.transcript : "";
              setMicFeedback(
                `"${shortTxt.slice(0, 72)}${shortTxt.length > 72 ? "\u2026" : ""}" \u2014 marcando la fila siguiente en la cola.`
              );
              setMicBusy("idle");
            } catch (e2) {
              console.error(e2);
              setMicFeedback("Error de red procesando tu voz.");
              setMicBusy("idle");
            }
          };
          micRecorderRef.current = recorder;
          recorder.start();
          setMicBusy("recording");
          setMicFeedback("Grabando\u2026 puls\xE1 otra vez el micr\xF3fono para ENVIAR a Mark y Mar\xEDa.");
        } catch (err) {
          console.error(err);
          cleanupMicStream();
          micRecorderRef.current = null;
          setMicFeedback("Sin permiso o sin micr\xF3fono (necesita HTTPS salvo localhost).");
          setMicBusy("idle");
        }
        return;
      }
      const rec = micRecorderRef.current;
      if (micBusy === "recording" && rec && rec.state === "recording") {
        setMicBusy("sending");
        setMicFeedback("Subiendo tu voz\u2026");
        try {
          rec.stop();
        } catch (err) {
          console.error(err);
          cleanupMicStream();
          micRecorderRef.current = null;
          setMicFeedback("No se pudo finalizar la grabaci\xF3n.");
          setMicBusy("idle");
        }
      }
    };
    useEffect(() => {
      if (isNarrationActive) {
        fetchNarration();
        const interval = setInterval(fetchNarration, 1500);
        return () => clearInterval(interval);
      }
    }, [isNarrationActive]);
    useEffect(() => {
      const playNext = async () => {
        if (audioQueue.length === 0 || isPlaying) return;
        const hasInteractivePending = pendingSegments.some((s) => s.listener);
        if (!isNarrationActive && !hasInteractivePending) return;
        const nextSegment = pendingSegments[0];
        if (nextSegment) currentPlayingSegmentRef.current = nextSegment;
        const nextAudioUrl = audioQueue[0];
        const followingUrl = audioQueue.length > 1 ? audioQueue[1] : null;
        let audio;
        if (nextPreloadedRef.current && nextPreloadedRef.current.url === nextAudioUrl) {
          audio = nextPreloadedRef.current.audio;
          nextPreloadedRef.current = null;
        } else {
          audio = new Audio(nextAudioUrl);
        }
        setIsPlaying(true);
        setAudioQueue((prev) => prev.slice(1));
        setPendingSegments((prev) => prev.slice(1));
        currentAudioRef.current = audio;
        if (followingUrl) {
          const preloadAudio = new Audio(followingUrl);
          preloadAudio.preload = "auto";
          preloadAudio.load();
          nextPreloadedRef.current = { url: followingUrl, audio: preloadAudio };
        }
        audio.onended = () => {
          const played = currentPlayingSegmentRef.current;
          if (played) {
            setPlayedSegments((prev) => [...prev, played]);
            currentPlayingSegmentRef.current = null;
          }
          setIsPlaying(false);
          currentAudioRef.current = null;
        };
        audio.onerror = (e) => {
          console.error("Audio playback error", e);
          currentPlayingSegmentRef.current = null;
          setIsPlaying(false);
          currentAudioRef.current = null;
        };
        try {
          await audio.play();
        } catch (err) {
          console.error("Audio play promise error", err);
          currentPlayingSegmentRef.current = null;
          setIsPlaying(false);
          currentAudioRef.current = null;
        }
      };
      playNext();
    }, [audioQueue, isPlaying, isNarrationActive, pendingSegments]);
    useEffect(() => {
      if (!isNarrationActive) {
        if (currentAudioRef.current) {
          currentAudioRef.current.pause();
          setIsPlaying(false);
        }
        nextPreloadedRef.current = null;
      }
    }, [isNarrationActive]);
    useEffect(() => {
      if (view === "narration" && messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
      }
    }, [narrationHistory, view]);
    useEffect(() => {
      if (view !== "podium" && view !== "positions") return;
      const timer = setInterval(() => {
        setView((prev) => prev === "podium" ? "positions" : "podium");
      }, 2e4);
      return () => clearInterval(timer);
    }, [view]);
    return /* @__PURE__ */ React.createElement("div", { className: "flex h-screen bg-black text-white overflow-hidden", style: { fontFamily: "'Montserrat', sans-serif" } }, /* @__PURE__ */ React.createElement("div", { className: `${isSidebarOpen ? "w-64" : "w-20"} transition-all duration-300 bg-gray-950 border-r border-gray-800 flex flex-col items-center py-6 gap-8` }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 px-4" }, /* @__PURE__ */ React.createElement("div", { className: "w-10 h-10 bg-red-600 rounded-lg flex items-center justify-center font-bold text-xl italic shadow-lg shadow-red-900/20" }, "F1"), isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-bold tracking-tighter text-xl italic" }, "DASHBOARD")), /* @__PURE__ */ React.createElement("nav", { className: "flex flex-col w-full gap-2 px-3" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("podium"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "podium" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-trophy w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "Podium Live")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("positions"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "positions" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-list-ol w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "Race State")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("narration"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "narration" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-comments w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "Comentarios")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("api"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "api" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-code w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "API Debug")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("data"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "data" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-database w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "Data")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setView("admin"),
        className: `flex items-center gap-4 w-full p-3 rounded-xl transition-all ${view === "admin" ? "bg-red-600 text-white" : "text-gray-400 hover:bg-gray-900"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-cog w-6 text-center" }),
      isSidebarOpen && /* @__PURE__ */ React.createElement("span", { className: "font-semibold" }, "Admin")
    )), /* @__PURE__ */ React.createElement("div", { className: "mt-auto flex flex-col gap-4 w-full px-3 pb-4" }, isSidebarOpen && /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-3 w-full" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Comentarios desde"), /* @__PURE__ */ React.createElement("div", { className: "flex rounded-lg bg-gray-900 border border-gray-700 p-0.5" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          if (narrationSource === "pista") return;
          setNarrationSource("pista");
          fetch(`${API_BASE}/api/narration/source`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: "pista" }) }).catch(() => {
          });
        },
        className: `px-3 py-1.5 text-[10px] font-bold rounded-md transition-all ${narrationSource === "pista" ? "bg-red-600 text-white" : "text-gray-400 hover:text-white"}`
      },
      "Pista"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          if (narrationSource === "api") return;
          setNarrationSource("api");
          fetch(`${API_BASE}/api/narration/source`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: "api" }) }).catch(() => {
          });
        },
        className: `px-3 py-1.5 text-[10px] font-bold rounded-md transition-all ${narrationSource === "api" ? "bg-red-600 text-white" : "text-gray-400 hover:text-white"}`
      },
      "API"
    )))), isSidebarOpen && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-900/50 p-3 rounded-xl border border-gray-800 text-[10px] space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 uppercase tracking-widest font-bold" }, "Llamadas API F1"), /* @__PURE__ */ React.createElement("span", { className: "text-amber-400 font-black tabular-nums" }, apiCallsCount.toLocaleString())), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 uppercase tracking-widest font-bold" }, "DataLive"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement("div", { className: `w-1.5 h-1.5 rounded-full ${apiStatus.datalive === "connected" ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" : apiStatus.datalive === "checking" ? "bg-yellow-500" : "bg-red-500"}` }), /* @__PURE__ */ React.createElement("span", { className: apiStatus.datalive === "connected" ? "text-green-500" : "text-gray-400" }, apiStatus.datalive.toUpperCase()))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 uppercase tracking-widest font-bold" }, "OpenAI Speech"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement("div", { className: `w-1.5 h-1.5 rounded-full ${apiStatus.openai === "connected" ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" : apiStatus.openai === "checking" ? "bg-yellow-500" : "bg-red-500"}` }), /* @__PURE__ */ React.createElement("span", { className: apiStatus.openai === "connected" ? "text-green-500" : "text-gray-400" }, apiStatus.openai.toUpperCase())))), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setIsNarrationActive(!isNarrationActive),
        className: `flex items-center justify-center gap-2 w-full p-3 rounded-xl font-bold transition-all shadow-lg ${isNarrationActive ? "bg-yellow-600 text-white hover:bg-yellow-700" : "bg-red-600 text-white hover:bg-red-700 active:scale-95"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: `fas ${isNarrationActive ? "fa-pause-circle" : "fa-play-circle"}` }),
      isSidebarOpen && (isNarrationActive ? "PAUSAR NARRACION" : narrationHistory.length > 0 ? "REANUDAR NARRACION" : "NARRACION")
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => handleMicToggle(),
        disabled: micBusy === "sending",
        title: micBusy === "recording" ? "Pulsar otra vez para enviar tu pregunta a Mark y Mar\xEDa" : micBusy === "sending" ? "Procesando tu voz\u2026" : "Pulsar para grabarte; puls\xE1 de nuevo para enviar a los locutores",
        className: `flex items-center justify-center gap-2 w-full p-3 rounded-xl font-bold transition-all border ${micBusy === "recording" ? "bg-red-700 border-red-400 text-white animate-pulse shadow-red-900/40" : micBusy === "sending" ? "bg-gray-800 border-gray-700 text-gray-400 cursor-not-allowed" : "bg-gray-900 border-purple-700/60 text-purple-300 hover:bg-gray-800 hover:border-purple-500"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: `fas ${micBusy === "recording" ? "fa-microphone-lines" : "fa-microphone"}` }),
      !isSidebarOpen ? null : micBusy === "recording" ? "ENVIAR al aire" : micBusy === "sending" ? "PROCESANDO\u2026" : "HABLAR (tap x2)"
    ), isSidebarOpen && micFeedback && /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 leading-snug" }, micFeedback))), /* @__PURE__ */ React.createElement("main", { className: "app-main-scroll flex-1 p-8 overflow-y-auto bg-gradient-to-br from-black via-gray-950 to-gray-900" }, /* @__PURE__ */ React.createElement("header", { className: "flex justify-between items-end mb-10 border-b border-gray-800/50 pb-8" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h1", { className: "text-4xl font-black italic tracking-tighter mb-1 select-none" }, (() => {
      const name = (adminConfig.race_name || "").trim() || (raceState.session_info && raceState.session_info.meetingOfficialName || "").replace("FORMULA 1 ", "").replace("FORMULA1 ", "") || "F1 GRAND PRIX";
      const i = name.indexOf(" de ");
      const part1 = i >= 0 ? name.slice(0, i) : name.split(" ")[0] || name;
      const part2 = i >= 0 ? name.slice(i) : name.slice(part1.length).trim();
      return part2 ? /* @__PURE__ */ React.createElement(React.Fragment, null, part1.toUpperCase(), " ", /* @__PURE__ */ React.createElement("span", { className: "text-red-600" }, part2.toUpperCase())) : /* @__PURE__ */ React.createElement("span", null, name.toUpperCase());
    })()), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center gap-3 md:gap-4 text-sm font-bold text-gray-500" }, view === "podium" && /* @__PURE__ */ React.createElement("span", { className: "rounded-lg border-2 border-white/90 bg-[#1a283d] px-3 py-1 text-white font-black text-xs md:text-sm tracking-tight" }, "Vuelta ", raceState.lap, " / ", raceState.total_laps || "\u2014"), (() => {
      const sInfo = raceState.session_info || {};
      const sType = (sInfo.sessionType || "").toLowerCase();
      const isRace = sType === "race" || sType === "sprint";
      const sName = sInfo.sessionName || "";
      const clockRem = (sInfo.clockRemaining || "").trim();
      const sStatus = (sInfo.sessionStatusStarted || sInfo.sessionStatusStatus || "").toLowerCase();
      const isFinished = sStatus.includes("finish") || sStatus.includes("finalis") || clockRem === "00:00:00";
      if (isRace) {
        if (view === "podium") return null;
        return /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-flag-checkered text-red-500" }), " LAP ", raceState.lap, "/", raceState.total_laps || "\u2014");
      }
      if (!sName) return null;
      return /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-stopwatch text-blue-400" }), /* @__PURE__ */ React.createElement("span", null, sName.toUpperCase()), clockRem && /* @__PURE__ */ React.createElement("span", { className: `ml-2 px-2 py-0.5 rounded-md font-mono text-xs font-black ${isFinished ? "bg-gray-800 text-gray-400" : "bg-red-600/15 text-red-400 border border-red-600/30"}` }, isFinished ? "FIN" : clockRem));
    })(), /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-thermometer-half text-orange-400" }), " ", isPlaying ? "ON AIR" : raceState.weather && raceState.weather.airTemp != null ? `${Math.round(raceState.weather.airTemp)}\xB0C AIR` : "\u2014\xB0C AIR"))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-right" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] font-black text-gray-600 uppercase tracking-[0.2em] mb-1" }, "Race Status"), /* @__PURE__ */ React.createElement("div", { className: "bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1.5 rounded-full font-black text-xs" }, /* @__PURE__ */ React.createElement("span", { className: "inline-block w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse" }), "LIVE TRACK DATA")))), view === "podium" ? /* @__PURE__ */ React.createElement("div", { className: "h-[calc(100vh-200px)] min-h-[420px] flex gap-2 md:gap-3 mt-2 overflow-hidden" }, positionsSortedByRank.slice(0, 5).map((driver, idx) => {
      const teamLogoUrl = getTeamLogoUrl(driver.team);
      return /* @__PURE__ */ React.createElement(
        "div",
        {
          key: `${driver.position}-${driver.tla || idx}`,
          className: "flex-1 flex flex-col min-w-0 rounded-2xl border border-gray-700/40 bg-[#151926] overflow-hidden shadow-[0_12px_40px_rgba(0,0,0,0.45)]"
        },
        /* @__PURE__ */ React.createElement("div", { className: "shrink-0 pt-3 pb-2 px-2 text-center" }, /* @__PURE__ */ React.createElement("span", { className: "text-white font-black text-sm md:text-base tracking-tight tabular-nums" }, formatPodiumGap(driver.position, driver.gap))),
        /* @__PURE__ */ React.createElement("div", { className: "h-2 md:h-2.5 shrink-0 w-full", style: { backgroundColor: getTeamColor(driver.team) } }),
        /* @__PURE__ */ React.createElement("div", { className: "shrink-0 flex items-center gap-2 px-3 py-2.5 border-b border-white/5" }, teamLogoUrl ? /* @__PURE__ */ React.createElement(
          "img",
          {
            src: teamLogoUrl,
            alt: "",
            "aria-hidden": "true",
            className: "f1-team-logo h-7 w-10 md:h-8 md:w-12 shrink-0 object-contain object-left",
            style: { filter: "none" },
            loading: "lazy",
            decoding: "async",
            onError: (e) => {
              e.target.style.display = "none";
            }
          }
        ) : null, /* @__PURE__ */ React.createElement("div", { className: "min-w-0 text-left leading-tight" }, /* @__PURE__ */ React.createElement("p", { className: "text-white font-black text-xs md:text-sm tracking-wide truncate" }, driverLastName(driver.name)), /* @__PURE__ */ React.createElement("p", { className: "text-white/55 font-bold text-[10px] md:text-[11px] tracking-[0.15em] truncate" }, teamPodiumLabel(driver.team)))),
        /* @__PURE__ */ React.createElement("div", { className: "relative flex-1 min-h-[180px] flex items-end justify-center pt-2 pb-4" }, /* @__PURE__ */ React.createElement("div", { className: "absolute left-2 md:left-3 top-[42%] z-20 w-9 h-9 md:w-10 md:h-10 rounded-full bg-red-600 flex items-center justify-center font-black text-white text-base md:text-lg border-2 border-white shadow-[0_4px_14px_rgba(220,38,38,0.55)]" }, driver.position), /* @__PURE__ */ React.createElement(
          "img",
          {
            src: driver.photo_url,
            alt: driver.name,
            className: "max-h-[92%] w-full object-contain object-bottom pointer-events-none select-none",
            onError: (e) => {
              e.target.src = "https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2026/drivers/fallback.webp";
            }
          }
        ))
      );
    })) : view === "positions" ? /* @__PURE__ */ React.createElement("div", { className: "grid gap-3" }, positionsSortedByRank.map((driver) => /* @__PURE__ */ React.createElement(
      "div",
      {
        key: driver.tla,
        className: "group relative flex items-center bg-gray-900/40 hover:bg-gray-800/60 border border-gray-800/50 hover:border-red-600/30 p-4 rounded-2xl transition-all duration-300"
      },
      /* @__PURE__ */ React.createElement("div", { className: "w-12 h-12 flex items-center justify-center font-black text-2xl italic text-gray-700 group-hover:text-red-600 transition-colors mr-6" }, driver.position),
      /* @__PURE__ */ React.createElement("div", { className: "relative mr-6" }, /* @__PURE__ */ React.createElement("div", { className: "w-16 h-16 rounded-full border-2 p-0.5 shadow-xl transition-all duration-300", style: { borderColor: getTeamColor(driver.team) } }, /* @__PURE__ */ React.createElement("div", { className: "w-full h-full rounded-full overflow-hidden bg-gray-800" }, /* @__PURE__ */ React.createElement("img", { src: driver.photo_url, alt: driver.name, className: "w-full h-full object-cover object-top pt-2 scale-110", onError: (e) => e.target.src = "https://via.placeholder.com/64x64/333/fff?text=" + driver.tla })))),
      /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 mb-0.5" }, /* @__PURE__ */ React.createElement("h2", { className: "text-lg font-bold tracking-tight" }, driver.name.toUpperCase()), /* @__PURE__ */ React.createElement("span", { className: "text-[10px] bg-gray-800 py-0.5 px-2 rounded-md border border-gray-700 text-gray-400 font-bold" }, driver.team)), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-4 text-xs font-black italic text-gray-500 uppercase tracking-widest" }, /* @__PURE__ */ React.createElement("span", { className: "text-white bg-gray-800/50 px-2 rounded" }, "LAST: ", driver.last_lap_time), /* @__PURE__ */ React.createElement("span", null, "S1: ", driver.sector_times ? driver.sector_times[0] : "-"), /* @__PURE__ */ React.createElement("span", null, "S2: ", driver.sector_times ? driver.sector_times[1] : "-"), /* @__PURE__ */ React.createElement("span", null, "S3: ", driver.sector_times ? driver.sector_times[2] : "-"))),
      /* @__PURE__ */ React.createElement("div", { className: "hidden lg:block mx-8 opacity-100 group-hover:opacity-60 transition-opacity" }, /* @__PURE__ */ React.createElement("img", { src: driver.car_url, alt: driver.team, className: "h-8 object-contain", onError: (e) => e.target.style.display = "none" })),
      /* @__PURE__ */ React.createElement("div", { className: "text-right min-w-[120px]" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] font-black text-gray-600 uppercase mb-1" }, "Gap to Leader"), /* @__PURE__ */ React.createElement("p", { className: `text-xl font-bold italic tracking-tighter ${driver.position === 1 ? "text-red-500" : "text-white"}` }, driver.gap === 0 ? "INTERVAL" : `+${driver.gap}s`))
    ))) : view === "narration" ? /* @__PURE__ */ React.createElement("div", { className: "flex flex-col gap-6 max-w-4xl mx-auto pb-10" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 border-b border-gray-800 pb-4" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setNarrationSubTab("played"),
        className: `px-5 py-2.5 rounded-xl font-bold text-sm transition-all ${narrationSubTab === "played" ? "bg-red-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-check-double mr-2" }),
      "Narrados (",
      playedSegments.length,
      ")"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setNarrationSubTab("upcoming"),
        className: `px-5 py-2.5 rounded-xl font-bold text-sm transition-all ${narrationSubTab === "upcoming" ? "bg-red-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`
      },
      /* @__PURE__ */ React.createElement("i", { className: "fas fa-clock mr-2" }),
      "Pr\xF3ximos (",
      pendingSegments.length,
      ")"
    )), narrationSubTab === "played" ? /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Comentarios ya narrados (voz)"), playedSegments.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-center justify-center h-48 border-2 border-dashed border-gray-800 rounded-2xl text-gray-500" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-volume-up text-3xl mb-3 opacity-30" }), /* @__PURE__ */ React.createElement("p", { className: "font-semibold" }, "A\xFAn no se ha narrado ning\xFAn comentario."), /* @__PURE__ */ React.createElement("p", { className: "text-sm" }, "Activa la narraci\xF3n y los que se reproduzcan aparecer\xE1n aqu\xED.")) : playedSegments.map((seg, idx) => /* @__PURE__ */ React.createElement("div", { key: idx, className: `p-5 rounded-2xl border ${seg.narrator === "Mark" ? "bg-gray-900/80 border-gray-800" : "bg-red-950/20 border-red-900/30"}` }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mb-2" }, /* @__PURE__ */ React.createElement("span", { className: `px-2 py-0.5 text-[10px] font-black rounded italic ${seg.narrator === "Mark" ? "bg-gray-800 text-red-500" : "bg-red-600 text-white"}` }, seg.narrator.toUpperCase()), seg.lap && /* @__PURE__ */ React.createElement("span", { className: "text-[10px] text-gray-500 font-bold" }, "LAP ", seg.lap), seg.listener && /* @__PURE__ */ React.createElement("span", { className: "text-[9px] px-2 py-0.5 rounded bg-purple-950/70 text-purple-300 font-black" }, "Oyente\u2192")), /* @__PURE__ */ React.createElement("p", { className: "text-gray-100 leading-relaxed font-semibold italic" }, '"', seg.text, '"'))), /* @__PURE__ */ React.createElement("div", { ref: messagesEndRef })) : /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Cola de comentarios por narrar"), pendingSegments.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-center justify-center h-48 border-2 border-dashed border-gray-800 rounded-2xl text-gray-500" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-list-ol text-3xl mb-3 opacity-30" }), /* @__PURE__ */ React.createElement("p", { className: "font-semibold" }, "No hay comentarios en cola."), /* @__PURE__ */ React.createElement("p", { className: "text-sm" }, "Cada nuevo bloque generado se a\xF1adir\xE1 aqu\xED antes de reproducirse.")) : pendingSegments.map((seg, idx) => /* @__PURE__ */ React.createElement("div", { key: idx, className: `p-5 rounded-2xl border ${seg.narrator === "Mark" ? "bg-gray-900/60 border-gray-700" : "bg-red-950/10 border-red-900/20"} ${idx === 0 && isPlaying ? "ring-2 ring-yellow-500/50" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mb-2" }, /* @__PURE__ */ React.createElement("span", { className: `px-2 py-0.5 text-[10px] font-black rounded italic ${seg.narrator === "Mark" ? "bg-gray-800 text-red-500" : "bg-red-600 text-white"}` }, seg.narrator.toUpperCase()), seg.lap && /* @__PURE__ */ React.createElement("span", { className: "text-[10px] text-gray-500 font-bold" }, "LAP ", seg.lap), seg.listener && /* @__PURE__ */ React.createElement("span", { className: "text-[9px] px-2 py-0.5 rounded bg-purple-950/70 text-purple-300 font-black" }, "Oyente\u2192"), idx === 0 && isPlaying && /* @__PURE__ */ React.createElement("span", { className: "text-[10px] text-yellow-500 font-bold animate-pulse" }, "ON AIR")), /* @__PURE__ */ React.createElement("p", { className: "text-gray-200 leading-relaxed font-semibold italic" }, '"', seg.text, '"'))))) : view === "api" ? /* @__PURE__ */ React.createElement("div", { className: "bg-gray-950 p-6 rounded-2xl border border-gray-800 h-[calc(100vh-200px)] overflow-y-auto space-y-8" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-2 text-white border-b border-gray-800 pb-2" }, "COMENTARIO CON DATOS ACTUALES"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-4" }, "Genera un \xFAnico comentario (Mark + Mar\xEDa) usando el estado actual de la carrera del API."), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: async () => {
          setCommentaryNowLoading(true);
          setCommentaryNow(null);
          try {
            const res = await fetch(`${API_BASE}/api/commentary/now`);
            const data = await res.json();
            setCommentaryNow(data);
          } catch (e) {
            setCommentaryNow({ error: e && e.message ? e.message : String(e) });
          }
          setCommentaryNowLoading(false);
        },
        disabled: commentaryNowLoading,
        className: "px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded-lg font-bold text-sm"
      },
      commentaryNowLoading ? "Generando comentario..." : "Generar comentario con datos actuales"
    ), commentaryNow && !commentaryNow.error && commentaryNow.commentary && commentaryNow.commentary.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "mt-6 space-y-4" }, commentaryNow.state_used && /* @__PURE__ */ React.createElement("div", { className: "p-4 rounded-xl bg-gray-900/50 border border-gray-800" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-2" }, "Datos del API usados"), /* @__PURE__ */ React.createElement("pre", { className: "text-xs font-mono text-gray-400 whitespace-pre-wrap" }, JSON.stringify(commentaryNow.state_used, null, 2))), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-green-500 uppercase font-bold" }, "Comentario generado"), commentaryNow.commentary.map((c, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: `p-5 rounded-xl border ${c.narrator === "Mark" ? "bg-gray-800/50 border-gray-700" : "bg-red-950/20 border-red-900/30"}` }, /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-black px-2 py-0.5 rounded italic ${c.narrator === "Mark" ? "bg-gray-700 text-red-400" : "bg-red-600 text-white"}` }, c.narrator), /* @__PURE__ */ React.createElement("p", { className: "text-gray-200 mt-2 text-sm italic" }, '"', c.text, '"'))))), commentaryNow && commentaryNow.error && /* @__PURE__ */ React.createElement("p", { className: "mt-4 text-red-400 text-sm" }, commentaryNow.error)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-2 text-white border-b border-gray-800 pb-2" }, "ENDPOINTS F1 LIVE PULSE"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-4" }, "Llama a cada endpoint del API para ver qu\xE9 hace y c\xF3mo se estructura la respuesta."), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: async () => {
          setEndpointsLoading(true);
          setEndpointsData(null);
          try {
            const res = await fetch(`${API_BASE}/api/debug/endpoints`);
            const data = await res.json();
            setEndpointsData(data.endpoints || data.error || []);
          } catch (e) {
            setEndpointsData([{ endpoint: "error", error: e && e.message ? e.message : String(e) }]);
          }
          setEndpointsLoading(false);
        },
        disabled: endpointsLoading,
        className: "px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-lg font-bold text-sm"
      },
      endpointsLoading ? "Llamando a cada endpoint..." : "Explorar todos los endpoints"
    ), endpointsData && Array.isArray(endpointsData) && endpointsData.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "mt-6 space-y-6" }, endpointsData.map((ep, idx) => /* @__PURE__ */ React.createElement("div", { key: ep.endpoint || idx, className: "border border-gray-800 rounded-xl p-5 bg-black/30" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mb-2" }, /* @__PURE__ */ React.createElement("span", { className: "font-mono font-bold text-red-500" }, ep.endpoint || "N/A"), /* @__PURE__ */ React.createElement("span", { className: `text-[10px] px-2 py-0.5 rounded ${ep.status === "ok" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"}` }, ep.status || "error")), /* @__PURE__ */ React.createElement("p", { className: "text-gray-300 text-sm mb-2" }, ep.description), /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 text-xs mb-3" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-600" }, "Uso en la app:"), " ", ep.use_in_app), ep.error && /* @__PURE__ */ React.createElement("p", { className: "text-red-400 text-xs mb-2" }, "Error: ", ep.error), ep.structure && /* @__PURE__ */ React.createElement("div", { className: "mb-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-1" }, "Estructura"), /* @__PURE__ */ React.createElement("pre", { className: "text-[10px] font-mono text-green-600/80 bg-black/50 p-3 rounded overflow-x-auto" }, JSON.stringify(ep.structure, null, 2))), ep.sample && /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-1" }, "Muestra (recortada)"), /* @__PURE__ */ React.createElement("pre", { className: "text-[10px] font-mono text-amber-600/80 bg-black/50 p-3 rounded overflow-x-auto" }, JSON.stringify(ep.sample, null, 2))), ep.sample_lines_item && /* @__PURE__ */ React.createElement("div", { className: "mt-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-1" }, "Ejemplo Lines[0]"), /* @__PURE__ */ React.createElement("pre", { className: "text-[10px] font-mono text-cyan-600/80 bg-black/50 p-3 rounded overflow-x-auto" }, JSON.stringify(ep.sample_lines_item, null, 2))), ep.sample_first_item && /* @__PURE__ */ React.createElement("div", { className: "mt-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-1" }, "Ejemplo primer \xEDtem"), /* @__PURE__ */ React.createElement("pre", { className: "text-[10px] font-mono text-cyan-600/80 bg-black/50 p-3 rounded overflow-x-auto" }, JSON.stringify(ep.sample_first_item, null, 2)))))), endpointsData && !Array.isArray(endpointsData) && /* @__PURE__ */ React.createElement("pre", { className: "mt-4 text-red-400 text-sm" }, typeof endpointsData === "string" ? endpointsData : JSON.stringify(endpointsData, null, 2))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-2 text-white border-b border-gray-800 pb-2" }, "DOS COMENTARIOS CON DATOS DEL API"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-4" }, "Genera dos bloques de comentarios (Mark + Mar\xEDa) usando el estado actual de la carrera del API."), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: async () => {
          setTwoCommentariesLoading(true);
          setTwoCommentaries(null);
          try {
            const res = await fetch(`${API_BASE}/api/debug/two-commentaries`);
            const data = await res.json();
            setTwoCommentaries(data);
          } catch (e) {
            setTwoCommentaries({ error: e && e.message ? e.message : String(e) });
          }
          setTwoCommentariesLoading(false);
        },
        disabled: twoCommentariesLoading,
        className: "px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 rounded-lg font-bold text-sm"
      },
      twoCommentariesLoading ? "Generando dos comentarios..." : "Generar 2 comentarios"
    ), twoCommentaries && !twoCommentaries.error && twoCommentaries.commentary_1 && /* @__PURE__ */ React.createElement("div", { className: "mt-6 space-y-6" }, twoCommentaries.state_used && /* @__PURE__ */ React.createElement("div", { className: "p-4 rounded-xl bg-gray-900/50 border border-gray-800" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500 uppercase font-bold mb-2" }, "Datos del API usados"), /* @__PURE__ */ React.createElement("pre", { className: "text-xs font-mono text-gray-400 whitespace-pre-wrap" }, JSON.stringify(twoCommentaries.state_used, null, 2))), /* @__PURE__ */ React.createElement("div", { className: "grid gap-6 md:grid-cols-2" }, /* @__PURE__ */ React.createElement("div", { className: "p-5 rounded-xl border border-gray-700 bg-gray-900/30" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-amber-500 uppercase font-bold mb-3" }, "Comentario 1"), twoCommentaries.commentary_1.map((c, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: `mb-4 p-4 rounded-lg ${c.narrator === "Mark" ? "bg-gray-800/50 border border-gray-700" : "bg-red-950/20 border border-red-900/30"}` }, /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-black px-2 py-0.5 rounded italic ${c.narrator === "Mark" ? "bg-gray-700 text-red-400" : "bg-red-600 text-white"}` }, c.narrator), /* @__PURE__ */ React.createElement("p", { className: "text-gray-200 mt-2 text-sm italic" }, '"', c.text, '"')))), /* @__PURE__ */ React.createElement("div", { className: "p-5 rounded-xl border border-gray-700 bg-gray-900/30" }, /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-amber-500 uppercase font-bold mb-3" }, "Comentario 2"), twoCommentaries.commentary_2 && twoCommentaries.commentary_2.map((c, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: `mb-4 p-4 rounded-lg ${c.narrator === "Mark" ? "bg-gray-800/50 border border-gray-700" : "bg-red-950/20 border border-red-900/30"}` }, /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-black px-2 py-0.5 rounded italic ${c.narrator === "Mark" ? "bg-gray-700 text-red-400" : "bg-red-600 text-white"}` }, c.narrator), /* @__PURE__ */ React.createElement("p", { className: "text-gray-200 mt-2 text-sm italic" }, '"', c.text, '"')))))), twoCommentaries && twoCommentaries.error && /* @__PURE__ */ React.createElement("p", { className: "mt-4 text-red-400 text-sm" }, twoCommentaries.error)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-4 text-white border-b border-gray-800 pb-2" }, "TOP 5 POSITIONS (LIVE API)"), /* @__PURE__ */ React.createElement("div", { className: "grid gap-2" }, positionsSortedByRank.slice(0, 5).map((driver) => /* @__PURE__ */ React.createElement("div", { key: driver.tla, className: "flex items-center gap-4 bg-gray-900/50 p-3 rounded-xl border border-gray-800" }, /* @__PURE__ */ React.createElement("div", { className: "w-8 h-8 rounded-full bg-red-600 flex items-center justify-center font-bold italic" }, driver.position), /* @__PURE__ */ React.createElement("div", { className: "font-bold w-12 text-gray-400" }, driver.tla), /* @__PURE__ */ React.createElement("div", { className: "flex-1 font-semibold" }, driver.name), /* @__PURE__ */ React.createElement("div", { className: "text-sm text-gray-500 w-32" }, driver.team), /* @__PURE__ */ React.createElement("div", { className: "font-mono text-green-400 w-24 text-right" }, driver.gap === 0 ? "LEADER" : `+${driver.gap}s`))), (raceState.positions || []).length === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 italic text-sm" }, "Waiting for live data..."))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-4 text-gray-500 border-b border-gray-800 pb-2" }, "RAW JSON PAYLOAD (estado actual)"), /* @__PURE__ */ React.createElement("pre", { className: "text-green-500/70 font-mono text-[10px] whitespace-pre-wrap bg-black/50 p-4 rounded-xl border border-gray-800" }, JSON.stringify(raceState, null, 2)))) : view === "admin" ? /* @__PURE__ */ React.createElement("div", { className: "max-w-2xl space-y-8" }, /* @__PURE__ */ React.createElement("div", { className: "border-b border-gray-800 pb-6" }, /* @__PURE__ */ React.createElement("h2", { className: "text-2xl font-bold text-white mb-1" }, "Configuraci\xF3n de narraci\xF3n"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm" }, "Define la carrera que narran Mark y Mar\xEDa y datos de inter\xE9s que se a\xF1aden al prompt cada 5 comentarios.")), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("label", { className: "block text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Carrera que se va a narrar"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        value: adminConfig.race_name,
        onChange: (e) => setAdminConfig((prev) => ({ ...prev, race_name: e.target.value })),
        placeholder: "ej. Gran Premio de Australia 2026",
        className: "w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-red-600 focus:border-transparent"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("label", { className: "block text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Informaci\xF3n de la carrera (cada 5 comentarios)"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 text-xs" }, "Este texto se inyecta en el prompt cada 5 comentarios para que Mark y Mar\xEDa puedan usar datos de inter\xE9s (contexto, r\xE9cords, estrategias, etc.)."), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        value: adminConfig.race_info,
        onChange: (e) => setAdminConfig((prev) => ({ ...prev, race_info: e.target.value })),
        placeholder: "ej. Primer GP del a\xF1o. Hamilton debutando con Ferrari. Posibles estrategias a un solo pit. R\xE9cord de vuelta en Melbourne: 1:20.235.",
        rows: 6,
        className: "w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-red-600 focus:border-transparent resize-y"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("label", { className: "block text-[10px] font-black text-gray-500 uppercase tracking-widest" }, "Contexto (se inyecta en cada comentario)"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 text-xs" }, "Nacionalidad de pilotos, datos interesantes, rivalidades, r\xE9cords personales, etc. Mark y Mar\xEDa usar\xE1n esta informaci\xF3n de forma natural en cada narraci\xF3n."), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        value: adminConfig.context,
        onChange: (e) => setAdminConfig((prev) => ({ ...prev, context: e.target.value })),
        placeholder: "ej.\n- Verstappen (NED) - 4x campe\xF3n, el m\xE1s joven en ganar un GP\n- Hamilton (GBR) - 7x campe\xF3n, r\xE9cord de victorias\n- Antonelli (ITA) - rookie, el m\xE1s joven desde Verstappen\n- Colapinto (ARG) - primer argentino en F1 desde los 80\n- Norris (GBR) y Piastri (AUS) - la dupla m\xE1s joven de McLaren",
        rows: 8,
        className: "w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-red-600 focus:border-transparent resize-y"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-4" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: async () => {
          setAdminSaving(true);
          setAdminSaved(false);
          try {
            const res = await fetch(`${API_BASE}/api/admin/config`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ race_name: adminConfig.race_name, race_info: adminConfig.race_info, context: adminConfig.context })
            });
            const data = await res.json();
            setAdminConfig({ race_name: data.race_name || "", race_info: data.race_info || "", context: data.context || "" });
            setAdminSaved(true);
            setTimeout(() => setAdminSaved(false), 3e3);
          } catch (e) {
            console.error(e);
          }
          setAdminSaving(false);
        },
        disabled: adminSaving,
        className: "px-6 py-3 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-xl font-bold text-sm"
      },
      adminSaving ? "Guardando..." : "Guardar configuraci\xF3n"
    ), adminSaved && /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2 text-green-500 text-sm font-bold" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-check-circle" }), "Guardado"))) : view === "data" ? (() => {
      const REALTIME_BASE = "http://localhost:4000";
      const DATA_ENDPOINTS = [
        { key: "current", path: "/api/current", label: "Estado completo en vivo" },
        { key: "drivers", path: "/api/drivers", label: "Lista de pilotos" },
        { key: "session-info", path: "/api/data/session-info", label: "Info de la sesi\xF3n" },
        { key: "timing", path: "/api/data/timing", label: "Tiempos por piloto/vuelta" },
        { key: "lap-count", path: "/api/data/lap-count", label: "Conteo de vueltas" },
        { key: "weather", path: "/api/data/weather", label: "Meteorolog\xEDa" },
        { key: "track-status", path: "/api/data/track-status", label: "Estado pista (banderas)" },
        { key: "position", path: "/api/data/position", label: "Posiciones en pista" },
        { key: "car-data", path: "/api/data/car-data", label: "Datos coche (RPM, velocidad)" },
        { key: "race-control", path: "/api/data/race-control", label: "Mensajes de race control" },
        { key: "timing-stats", path: "/api/data/timing-stats", label: "Estad\xEDsticas de tiempos" },
        { key: "team-radio", path: "/api/data/team-radio", label: "Radios de equipo" },
        { key: "session-status", path: "/api/data/session-status", label: "Estado de la sesi\xF3n" }
      ];
      const fetchEndpoint = (ep) => {
        setDataLoading((prev) => Object.assign({}, prev, { [ep.key]: true }));
        fetch(REALTIME_BASE + ep.path).then((r) => r.json()).then((json) => {
          setDataEndpoints((prev) => Object.assign({}, prev, { [ep.key]: { data: json, error: null } }));
          setDataLoading((prev) => Object.assign({}, prev, { [ep.key]: false }));
        }).catch((e) => {
          setDataEndpoints((prev) => Object.assign({}, prev, { [ep.key]: { data: null, error: e.message || String(e) } }));
          setDataLoading((prev) => Object.assign({}, prev, { [ep.key]: false }));
        });
      };
      const fetchAll = () => DATA_ENDPOINTS.forEach((ep) => fetchEndpoint(ep));
      return /* @__PURE__ */ React.createElement("div", { className: "bg-gray-950 p-6 rounded-2xl border border-gray-800 h-[calc(100vh-200px)] overflow-y-auto space-y-6" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between border-b border-gray-800 pb-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "text-2xl font-bold text-white" }, "Datos en vivo (f1-dash Realtime)"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mt-1" }, "Respuestas en tiempo real de cada endpoint en ", /* @__PURE__ */ React.createElement("span", { className: "font-mono text-red-400" }, REALTIME_BASE))), /* @__PURE__ */ React.createElement("button", { onClick: fetchAll, className: "px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-bold text-sm" }, /* @__PURE__ */ React.createElement("i", { className: "fas fa-sync-alt mr-2" }), "Cargar todos")), /* @__PURE__ */ React.createElement("div", { className: "grid gap-4" }, DATA_ENDPOINTS.map((ep) => /* @__PURE__ */ React.createElement("div", { key: ep.key, className: "border border-gray-800 rounded-xl bg-black/30 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-5 py-3 bg-gray-900/50 border-b border-gray-800" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "font-mono text-red-500 text-sm font-bold" }, ep.path), /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 text-xs" }, ep.label)), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => fetchEndpoint(ep),
          disabled: dataLoading[ep.key],
          className: "px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-lg text-xs font-bold"
        },
        dataLoading[ep.key] ? "Cargando..." : "GET"
      )), dataEndpoints[ep.key] && /* @__PURE__ */ React.createElement("div", { className: "p-4" }, dataEndpoints[ep.key].error ? /* @__PURE__ */ React.createElement("p", { className: "text-red-400 text-sm" }, dataEndpoints[ep.key].error) : /* @__PURE__ */ React.createElement("pre", { className: "text-[10px] font-mono text-green-500/80 bg-black/50 p-3 rounded overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap" }, JSON.stringify(dataEndpoints[ep.key].data, null, 2)))))));
    })() : null));
  };
  var root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(/* @__PURE__ */ React.createElement(App, null));
})();
