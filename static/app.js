const $ = (id) => document.getElementById(id);

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function renderWallet(w) {
  $("address").textContent = w.address;
  $("native").textContent = `${Number(w.native_eth).toFixed(6)} ETH`;
  $("spent").textContent = `${Number(w.spent_today_eth).toFixed(6)} ETH`;
  $("chainPill").textContent = `chain ${w.chain_id}`;
  $("modePill").textContent = w.dry_run ? "dry-run" : "live";
  $("rpcPill").textContent = w.online ? "rpc live" : "rpc offline";
  $("tokens").textContent = (w.tokens || [])
    .map((t) => `${t.balance} ${t.symbol}`)
    .join(" · ") || (w.ephemeral ? "Ephemeral demo wallet" : "");
}

function renderPolicy(p) {
  $("maxTx").value = p.max_native_per_tx_eth;
  $("dailyCap").value = p.daily_native_cap_eth;
  $("confirmAbove").value = p.confirm_above_eth;
  $("maxGas").value = p.max_gas_gwei;
  $("cooldown").value = p.cooldown_seconds;
  $("allowlistOn").checked = p.allowlist_enabled;
  $("blockUnlimited").checked = p.block_unlimited_approvals;
  $("autonomyOn").checked = p.autonomous_enabled;
  $("allowlist").value = (p.allowlist || []).join("\n");
}

function itemClass(a) {
  const d = a.verdict?.decision;
  if (a.status === "failed" || d === "deny") return "deny";
  if (d === "confirm" || a.status === "queued") return "confirm";
  return "allow";
}

function renderFeed(items) {
  $("feed").innerHTML = items
    .map((a) => {
      const confirm =
        a.status === "queued"
          ? `<div class="meta"><button data-id="${a.id}">Confirm & send</button></div>`
          : "";
      return `<article class="item ${itemClass(a)}">
        <strong>${a.intent.kind}</strong> · ${a.status}
        <div>${a.detail || a.intent.text}</div>
        <div class="meta">${a.ts} · ${(a.verdict?.reasons || []).join("; ")}${a.tx_hash ? " · " + a.tx_hash : ""}</div>
        ${confirm}
      </article>`;
    })
    .join("");
}

async function refresh() {
  const [wallet, policy, activity] = await Promise.all([
    api("/api/wallet"),
    api("/api/policy"),
    api("/api/activity"),
  ]);
  renderWallet(wallet);
  renderPolicy(policy);
  renderFeed(activity);
}

$("cmdForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("cmd").value.trim();
  if (!text) return;
  $("reply").textContent = "Planning…";
  try {
    const out = await api("/api/agent/intent", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    $("reply").textContent = out.message;
    await refresh();
  } catch (err) {
    $("reply").textContent = String(err.message || err);
  }
});

$("autoBtn").addEventListener("click", async () => {
  $("reply").textContent = "Running autonomy cycle…";
  const out = await api("/api/agent/autonomy", { method: "POST" });
  $("reply").textContent = `Autonomy processed ${(out.results || []).length} item(s).`;
  await refresh();
});

$("policyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const policy = {
    max_native_per_tx_eth: Number($("maxTx").value),
    daily_native_cap_eth: Number($("dailyCap").value),
    confirm_above_eth: Number($("confirmAbove").value),
    max_gas_gwei: Number($("maxGas").value),
    cooldown_seconds: Number($("cooldown").value),
    allowlist_enabled: $("allowlistOn").checked,
    block_unlimited_approvals: $("blockUnlimited").checked,
    autonomous_enabled: $("autonomyOn").checked,
    allowlist: $("allowlist").value.split("\n").map((s) => s.trim()).filter(Boolean),
    max_autonomy_intents_per_cycle: 3,
  };
  await api("/api/policy", { method: "PUT", body: JSON.stringify(policy) });
  $("reply").textContent = "Risk policy saved.";
  await refresh();
});

$("feed").addEventListener("click", async (e) => {
  const id = e.target.getAttribute("data-id");
  if (!id) return;
  const out = await api("/api/agent/confirm", {
    method: "POST",
    body: JSON.stringify({ activity_id: id }),
  });
  $("reply").textContent = out.message;
  await refresh();
});

refresh().catch((err) => {
  $("reply").textContent = "Could not load API: " + err.message;
});
