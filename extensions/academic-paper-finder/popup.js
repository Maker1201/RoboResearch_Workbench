const API_CANDIDATES = ["http://127.0.0.1:8770", "http://localhost:8770", "http://127.0.0.1:8766", "http://localhost:8766"];

const statusEl = document.getElementById("status");

function setStatus(message) {
  statusEl.textContent = message;
}

async function findApiBase() {
  for (const baseUrl of API_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });
      if (response.ok) return baseUrl;
    } catch {}
  }
  return null;
}

document.getElementById("openApp").addEventListener("click", async () => {
  const url = browser.runtime.getURL("app.html");
  await browser.tabs.create({ url });
  window.close();
});

document.getElementById("capturePending").addEventListener("click", async () => {
  setStatus("正在读取工作台待获取清单…");
  const apiBase = await findApiBase();
  if (!apiBase) {
    setStatus("无法连接本地后台，请先启动 RoboResearch Workbench。");
    return;
  }
  try {
    const response = await fetch(`${apiBase}/papers/pending-pdfs`, { cache: "no-store" });
    const data = await response.json();
    const pending = data.pending_pdfs || [];
    if (!pending.length) {
      setStatus("工作台没有待获取的 PDF，全部文献都已挂载。");
      return;
    }
    await browser.runtime.sendMessage({
      type: "START_CARSI_PDF_CAPTURE",
      pendingPdfs: pending,
      apiBase
    });
    setStatus(`已把 ${pending.length} 篇加入 CARSI 抓取队列，浏览器将逐篇打开页面（保持学校网络/登录状态）。`);
  } catch (error) {
    setStatus(`读取待获取清单失败：${error?.message || "未知错误"}`);
  }
});

document.getElementById("syncSession").addEventListener("click", async () => {
  setStatus("正在同步各出版商站点的登录会话…");
  try {
    const result = await browser.runtime.sendMessage({ type: "SYNC_PUBLISHER_COOKIES" });
    if (result?.synced?.length) {
      setStatus(`已同步 ${result.synced.length} 个站点的机构登录会话：${result.synced.join("、")}。之后服务器下载会自动携带。`);
    } else {
      setStatus("没有找到可同步的登录会话。请先在浏览器里通过学校认证登录出版商网站。");
    }
  } catch (error) {
    setStatus(`同步会话失败：${error?.message || "未知错误"}`);
  }
});
