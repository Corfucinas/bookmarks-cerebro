document.addEventListener("DOMContentLoaded", async () => {
  const urlEl = document.getElementById("url",);
  const btn = document.getElementById("cerebro-btn",);
  const status = document.getElementById("status",);

  // Get current tab URL
  const [tab,] = await chrome.tabs.query({ active: true, currentWindow: true, },);
  urlEl.textContent = tab?.url || "No active tab";

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    status.textContent = "Sending...";
    status.className = "";

    try {
      const resp = await fetch("http://localhost:8765/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json", },
        body: JSON.stringify({
          url: tab.url,
          title: tab.title,
        },),
      },);

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`,);
      const data = await resp.json();
      status.textContent = `✅ Added to ${data.category || "vault"}`;
      status.className = "success";
    } catch (err) {
      status.textContent = `❌ ${err.message}. Is cerebro serve running?`;
      status.className = "error";
    } finally {
      btn.disabled = false;
    }
  },);
},);
