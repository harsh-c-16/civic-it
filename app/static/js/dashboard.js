/**
 * SentimentPulse dashboard.
 * Reads aggregate civic-issue sentiment from the API and renders the report.
 */

const COLORS = { positive: "#2f6f4f", neutral: "#b5862a", negative: "#a83a2c" };
const WINDOW_LABELS = {
    24: "last 24 hours", 72: "last 3 days", 168: "last 7 days", 720: "last 30 days",
};

const state = { range: 168, page: 1, pageSize: 20, sentiment: "" };
let trendChart = null;

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    loadAll();
    bindEvents();
    setInterval(loadAll, 120000); // refresh every 2 min
});

function bindEvents() {
    document.getElementById("range").addEventListener("change", (e) => {
        state.range = parseInt(e.target.value, 10);
        state.page = 1;
        document.getElementById("windowLabel").textContent = WINDOW_LABELS[state.range] || "";
        loadAll();
    });
    document.getElementById("refresh").addEventListener("click", loadAll);
    document.getElementById("sentimentFilter").addEventListener("change", (e) => {
        state.sentiment = e.target.value;
        state.page = 1;
        loadPosts();
    });
    document.getElementById("prev").addEventListener("click", () => {
        if (state.page > 1) { state.page--; loadPosts(); }
    });
    document.getElementById("next").addEventListener("click", () => {
        state.page++; loadPosts();
    });
}

function loadAll() {
    loadMeta();
    loadSummary();
    loadTrend();
    loadIssues();
    loadPosts();
}

async function loadMeta() {
    try {
        const s = await (await fetch("/api/stats")).json();
        const sources = Object.keys(s.database.by_source || {});
        const el = document.getElementById("source");
        const txt = document.getElementById("sourceText");
        if (sources.includes("reddit")) {
            el.className = "source live";
            txt.textContent = "Live · Reddit";
        } else {
            el.className = "source sample";
            txt.textContent = "Sample data";
        }
    } catch (_) { /* non-critical */ }
}

async function loadSummary() {
    try {
        const d = await (await fetch(`/api/summary?hours=${state.range}`)).json();
        const c = d.summary.counts, p = d.summary.percentages;
        document.getElementById("total").textContent = c.total.toLocaleString();

        document.getElementById("distBar").innerHTML = c.total === 0 ? "" : `
            <span class="s-pos" style="width:${p.positive}%"></span>
            <span class="s-neu" style="width:${p.neutral}%"></span>
            <span class="s-neg" style="width:${p.negative}%"></span>`;

        const row = (key, label, pct, cnt) => `
            <li>
                <span class="swatch s-${key}"></span>
                <span class="lab">${label}</span>
                <span class="pct">${pct}%</span>
                <span class="cnt">${cnt.toLocaleString()}</span>
            </li>`;
        document.getElementById("distLegend").innerHTML =
            row("pos", "Positive", p.positive, c.positive) +
            row("neu", "Neutral", p.neutral, c.neutral) +
            row("neg", "Negative", p.negative, c.negative);
    } catch (_) { /* keep last render */ }
}

async function loadTrend() {
    try {
        const d = await (await fetch(`/api/trends?hours=${state.range}`)).json();
        const pts = d.data || [];
        trendChart.data.labels = pts.map((x) =>
            new Date(x.timestamp).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit" }));
        trendChart.data.datasets[0].data = pts.map((x) => x.positive);
        trendChart.data.datasets[1].data = pts.map((x) => x.neutral);
        trendChart.data.datasets[2].data = pts.map((x) => x.negative);
        trendChart.update();
    } catch (_) { /* keep last render */ }
}

async function loadIssues() {
    const el = document.getElementById("issues");
    try {
        const d = await (await fetch(`/api/topics?hours=${state.range}`)).json();
        if (!d.topics.length) { el.innerHTML = `<li class="empty">No issues detected in this window.</li>`; return; }
        el.innerHTML = d.topics.map((t, i) => {
            const total = t.total || 1;
            const w = (n) => (n / total * 100).toFixed(1);
            return `
                <li class="issue">
                    <span class="rank">${String(i + 1).padStart(2, "0")}</span>
                    <div class="body">
                        <div class="top">
                            <span class="name">${esc(titleCase(t.topic))}</span>
                            <span class="count">${t.total.toLocaleString()} posts</span>
                        </div>
                        <div class="minibar">
                            <span class="s-pos" style="width:${w(t.positive)}%"></span>
                            <span class="s-neu" style="width:${w(t.neutral)}%"></span>
                            <span class="s-neg" style="width:${w(t.negative)}%"></span>
                        </div>
                    </div>
                </li>`;
        }).join("");
    } catch (_) {
        el.innerHTML = `<li class="empty">Could not load issues.</li>`;
    }
}

async function loadPosts() {
    const el = document.getElementById("posts");
    try {
        let url = `/api/recent_posts?hours=${state.range}&page=${state.page}&page_size=${state.pageSize}`;
        if (state.sentiment) url += `&sentiment=${state.sentiment}`;
        const d = await (await fetch(url)).json();

        if (!d.posts.length) {
            el.innerHTML = `<li class="empty">No posts in this window.</li>`;
            setPager(0);
            return;
        }
        el.innerHTML = d.posts.map((p) => {
            const src = p.source_context ? `r/${esc(p.source_context)}` : esc(p.source || "");
            const tag = p.topic ? `<span class="tag">${esc(titleCase(p.topic))}</span>` : "";
            const sent = p.sentiment || "neutral";
            const link = p.url ? `<a class="link" href="${esc(p.url)}" target="_blank" rel="noopener">source ↗</a>` : "";
            return `
                <li class="post ${sent}">
                    <p class="text">${esc(p.text)}</p>
                    <div class="meta">
                        <span class="src">${src}</span>
                        <span>${relTime(p.created_at)}</span>
                        ${tag}
                        <span class="label ${sent}">${sent}</span>
                        ${link}
                    </div>
                </li>`;
        }).join("");
        setPager(d.total);
    } catch (_) {
        el.innerHTML = `<li class="empty">Could not load posts.</li>`;
    }
}

function setPager(total) {
    const pages = Math.ceil(total / state.pageSize) || 1;
    document.getElementById("pageInfo").textContent = `Page ${state.page} of ${pages}`;
    document.getElementById("prev").disabled = state.page <= 1;
    document.getElementById("next").disabled = state.page >= pages;
}

function initChart() {
    const ctx = document.getElementById("trend").getContext("2d");
    const ds = (label, color) => ({
        label, data: [], borderColor: color, backgroundColor: color,
        borderWidth: 1.6, pointRadius: 0, pointHoverRadius: 3, tension: 0.3, fill: false,
    });
    trendChart = new Chart(ctx, {
        type: "line",
        data: { labels: [], datasets: [ds("Positive", COLORS.positive), ds("Neutral", COLORS.neutral), ds("Negative", COLORS.negative)] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10, font: { size: 11 }, color: "#6c655b" } },
            },
            scales: {
                x: { ticks: { color: "#9a9286", font: { size: 10 }, maxRotation: 0, autoSkipPadding: 16 }, grid: { display: false } },
                y: { beginAtZero: true, ticks: { color: "#9a9286", font: { size: 10 }, precision: 0 }, grid: { color: "#ebe6db" }, border: { display: false } },
            },
        },
    });
}

/* helpers */
function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
function titleCase(s) { return String(s).charAt(0) + String(s).slice(1).toLowerCase(); }
function relTime(iso) {
    const diff = (Date.now() - new Date(iso)) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
