const pendingByTab = new Map();
const awaitingChildByTab = new Map();
const PDF_FETCH_RETRY_DELAYS = [0, 1200, 3000, 6000];
const MAX_CAPTURE_TABS = 1;
const CAPTURE_OPEN_DELAY_MS = 1200;
const CAPTURE_TAB_TIMEOUT_MS = 90000;

const captureQueue = [];
const captureTimeouts = new Map();
const attachingItemKeys = new Set();
const completedItemKeys = new Set();
let activeCaptureCount = 0;
let queueRunning = false;

browser.runtime.onMessage.addListener(async (message, sender) => {
  if (message?.type === "OPEN_URL" && message.url) {
    await browser.tabs.create({ url: message.url });
    return;
  }

  if (message?.type === "START_CARSI_PDF_CAPTURE") {
    await startCaptureQueue(message.pendingPdfs || [], message.apiBase);
    return;
  }

  if (message?.type === "PDF_CANDIDATE_FOUND" && message.task && message.pdfUrl) {
    await handlePdfCandidate(message.task, message.pdfUrl, message.task.apiBase, sender?.tab?.id, sender?.tab?.url);
  }

  if (message?.type === "PDF_BUTTON_CLICKING" && message.task && sender?.tab?.id) {
    awaitingChildByTab.set(sender.tab.id, { ...message.task, apiBase: message.task.apiBase });
    setTimeout(() => awaitingChildByTab.delete(sender.tab.id), 30000);
  }
});

browser.tabs.onCreated.addListener((tab) => {
  if (!tab.openerTabId) return;
  const task = awaitingChildByTab.get(tab.openerTabId);
  if (task && tab.id) pendingByTab.set(tab.id, { ...task, openedByQueue: false });
});

browser.tabs.onRemoved.addListener((tabId) => {
  const task = pendingByTab.get(tabId);
  if (!task) return;
  pendingByTab.delete(tabId);
  clearCaptureTimeout(tabId);
  if (task.openedByQueue) finishQueuedTask(task, false, true);
});

browser.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  const task = pendingByTab.get(tabId);
  if (!task || !tab.url) return;

  const derivedPdfUrl = derivePdfUrlFromPageUrl(tab.url);
  if (derivedPdfUrl && !sameUrl(derivedPdfUrl, tab.url)) {
    if (task.redirectedToPdfUrl && sameUrl(task.redirectedToPdfUrl, derivedPdfUrl)) {
      await notify(`${task.title || "当前论文"} 已尝试打开 PDF 链接，页面仍未返回 PDF；请手动确认登录/权限后点击保存。`);
      return;
    }
    pendingByTab.set(tabId, { ...task, redirectedToPdfUrl: derivedPdfUrl });
    await browser.tabs.update(tabId, { url: derivedPdfUrl });
    return;
  }

  if (looksLikePdfUrl(tab.url)) {
    await fetchAndAttachPdfWithRetry(task, tab.url, task.apiBase, tabId);
    return;
  }

  try {
    await browser.tabs.sendMessage(tabId, { type: "SCAN_FOR_PDF", task, allowClick: !task.clickAttempted });
    if (!task.clickAttempted) {
      pendingByTab.set(tabId, { ...task, clickAttempted: true });
    }
  } catch {
    // Some pages, redirects, and built-in viewers cannot receive content-script messages.
  }
});

async function startCaptureQueue(tasks, apiBase) {
  const queueItems = tasks
    .map((task) => ({ ...task, apiBase }))
    .filter((task) => targetUrlFor(task) && !completedItemKeys.has(task.item_key));

  if (!queueItems.length) return;

  captureQueue.push(...queueItems);
  await notify(`已加入 PDF 获取队列：${queueItems.length} 篇。将一次只打开 ${MAX_CAPTURE_TABS} 个页面，避免浏览器卡顿。`);
  processCaptureQueue();
}

function processCaptureQueue() {
  if (queueRunning) return;
  queueRunning = true;
  drainCaptureQueue().finally(() => {
    queueRunning = false;
    if (captureQueue.length && activeCaptureCount < MAX_CAPTURE_TABS) processCaptureQueue();
  });
}

async function drainCaptureQueue() {
  while (activeCaptureCount < MAX_CAPTURE_TABS && captureQueue.length) {
    const task = captureQueue.shift();
    await openCaptureTask(task);
    if (captureQueue.length) await sleep(CAPTURE_OPEN_DELAY_MS);
  }
}

async function openCaptureTask(task) {
  const targetUrl = targetUrlFor(task);
  if (!targetUrl) return;

  activeCaptureCount += 1;
  try {
    const tab = await browser.tabs.create({ url: targetUrl, active: true });
    const queuedTask = { ...task, openedByQueue: true };
    pendingByTab.set(tab.id, queuedTask);
    scheduleCaptureTimeout(tab.id, queuedTask);
  } catch (error) {
    activeCaptureCount = Math.max(0, activeCaptureCount - 1);
    await notify(`PDF 页面打开失败：${task.title || targetUrl}。${error?.message || "未知错误"}`);
    processCaptureQueue();
  }
}

function targetUrlFor(task) {
  return task.pdf_url || task.url || (task.doi ? `https://doi.org/${task.doi}` : null);
}

function scheduleCaptureTimeout(tabId, task) {
  clearCaptureTimeout(tabId);
  const timeoutId = setTimeout(async () => {
    if (!pendingByTab.has(tabId)) return;
    await notify(`${task.title || "当前论文"} 获取超时：90 秒内没有捕获到 PDF，已跳过并继续下一篇。`);
    await failCapturedTab(tabId, task);
  }, CAPTURE_TAB_TIMEOUT_MS);
  captureTimeouts.set(tabId, timeoutId);
}

function clearCaptureTimeout(tabId) {
  const timeoutId = captureTimeouts.get(tabId);
  if (timeoutId) clearTimeout(timeoutId);
  captureTimeouts.delete(tabId);
}

async function handlePdfCandidate(task, pdfUrl, apiBase, tabId, currentUrl) {
  const normalizedPdfUrl = normalizePdfFetchUrl(new URL(pdfUrl, currentUrl || undefined).href);
  const targetPdfUrl = derivePdfUrlFromPageUrl(normalizedPdfUrl) || normalizedPdfUrl;
  if (tabId && currentUrl && !looksLikePdfUrl(currentUrl) && looksLikePdfUrl(targetPdfUrl)) {
    const existingTask = pendingByTab.get(tabId) || task;
    if (existingTask.redirectedToPdfUrl && sameUrl(existingTask.redirectedToPdfUrl, targetPdfUrl)) {
      await notify(`${task.title || "当前论文"} 已尝试打开 PDF 链接，请等待加载或手动点击右下角保存。`);
      return;
    }
    pendingByTab.set(tabId, { ...existingTask, ...task, apiBase, redirectedToPdfUrl: targetPdfUrl });
    await browser.tabs.update(tabId, { url: targetPdfUrl });
    return;
  }
  await fetchAndAttachPdfWithRetry(task, targetPdfUrl, apiBase, tabId);
}

async function fetchAndAttachPdfWithRetry(task, pdfUrl, apiBase, tabId) {
  let lastMessage = "PDF 自动保存失败。";
  for (const delayMs of PDF_FETCH_RETRY_DELAYS) {
    if (delayMs) await sleep(delayMs);
    const result = await fetchAndAttachPdf(task, pdfUrl, apiBase, tabId);
    if (result.ok) return;
    lastMessage = result.message || lastMessage;
  }

  const title = task.title || filenameFor(task, pdfUrl);
  await notify(`${title} 获取失败：${lastMessage}`);
  await failCapturedTab(tabId, task);
}

async function fetchAndAttachPdf(task, pdfUrl, apiBase, tabId) {
  const itemKey = task.item_key;
  if (completedItemKeys.has(itemKey)) {
    return { ok: true, skipped: true };
  }
  if (attachingItemKeys.has(itemKey)) {
    return { ok: false, message: "该论文的 PDF 正在写入 Zotero，已跳过重复请求。" };
  }
  attachingItemKeys.add(itemKey);
  try {
    const fetchUrl = normalizePdfFetchUrl(pdfUrl);
    const response = await fetch(fetchUrl, { credentials: "include", cache: "no-store" });
    if (!response.ok) {
      return { ok: false, message: `HTTP ${response.status}` };
    }
    const contentType = (response.headers.get("content-type") || "application/pdf").split(";")[0];
    const buffer = await response.arrayBuffer();
    if (!isPdf(buffer, contentType)) {
      return { ok: false, message: "获取到的内容不是 PDF，可能仍停在登录页或出版社 HTML 页面。" };
    }
    const contentBase64 = arrayBufferToBase64(buffer);
    const filename = filenameFor(task, pdfUrl);
    const attachResponse = await fetch(`${apiBase}/papers/attach-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_key: task.item_key,
        pdf_url: fetchUrl,
        filename,
        content_type: contentType || "application/pdf",
        content_base64: contentBase64
      })
    });
    if (attachResponse.ok) {
      completedItemKeys.add(itemKey);
      pendingByTab.forEach((value, tabId) => {
        if (value.item_key === task.item_key) pendingByTab.delete(tabId);
      });
      await notify(`PDF 已挂载到 Zotero：${task.title || filename}`);
      if (tabId) await closeCapturedTab(tabId, task);
      return { ok: true };
    }
    let detail = "后端写入 Zotero 失败。";
    try {
      const data = await attachResponse.json();
      detail = data.detail || detail;
    } catch {}
    return { ok: false, message: detail };
  } catch (error) {
    return { ok: false, message: error?.message || "未知错误" };
  } finally {
    attachingItemKeys.delete(itemKey);
  }
}

async function closeCapturedTab(tabId, task) {
  try {
    if (tabId) clearCaptureTimeout(tabId);
    if (tabId) pendingByTab.delete(tabId);
    if (tabId) await browser.tabs.remove(tabId);
  } catch {}
  finishQueuedTask(task, true, true);
}

async function failCapturedTab(tabId, task) {
  try {
    if (tabId) clearCaptureTimeout(tabId);
    if (tabId) pendingByTab.delete(tabId);
    if (tabId) await browser.tabs.remove(tabId);
  } catch {}
  finishQueuedTask(task, false, true);
}

function finishQueuedTask(task, notifyCompletion, shouldScheduleNext) {
  if (task?.openedByQueue) activeCaptureCount = Math.max(0, activeCaptureCount - 1);
  if (notifyCompletion && !captureQueue.length && activeCaptureCount === 0) {
    notify("PDF 获取队列已处理完成。");
  }
  if (shouldScheduleNext) processCaptureQueue();
}

function normalizePdfFetchUrl(url) {
  return derivePdfUrlFromPageUrl(url) || url;
}

function derivePdfUrlFromPageUrl(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname;
    if (host === "ieeexplore.ieee.org") {
      if (path === "/stamp/stamp.jsp") {
        const articleNumber = parsed.searchParams.get("arnumber");
        if (articleNumber) return ieeePdfUrl(articleNumber);
      }
      const documentMatch = path.match(/^\/document\/(\d+)/i);
      if (documentMatch) return ieeePdfUrl(documentMatch[1]);
      const abstractMatch = path.match(/^\/abstract\/document\/(\d+)/i);
      if (abstractMatch) return ieeePdfUrl(abstractMatch[1]);
    }

    const researchSquare = host.endsWith("researchsquare.com");
    const rsMatch = path.match(/^\/article\/(rs-[^/]+)\/(v\d+|latest)(?:\.pdf)?$/i);
    if (researchSquare && rsMatch) {
      return `https://www.researchsquare.com/article/${rsMatch[1]}/${rsMatch[2]}.pdf`;
    }

    const preprints = host === "preprints.org" || host === "www.preprints.org" || host.endsWith(".preprints.org");
    if (preprints && path.includes("/download")) {
      return url;
    }
  } catch {}
  return null;
}

function ieeePdfUrl(articleNumber) {
  return `https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=${encodeURIComponent(articleNumber)}&ref=`;
}

function sameUrl(left, right) {
  try {
    return new URL(left).href === new URL(right).href;
  } catch {
    return left === right;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isPdf(buffer, contentType) {
  if (contentType === "application/pdf") return true;
  const bytes = new Uint8Array(buffer.slice(0, 4));
  return bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function filenameFor(task, url) {
  const title = (task.title || "paper").replace(/[^A-Za-z0-9._ -]+/g, "").trim().replace(/\s+/g, "_").slice(0, 90) || "paper";
  const pathName = new URL(url).pathname.split("/").pop() || "";
  if (pathName.toLowerCase().endsWith(".pdf")) return pathName;
  return `${title}.pdf`;
}

function looksLikePdfUrl(url) {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.toLowerCase();
    const hostname = parsed.hostname.toLowerCase();
    return path.endsWith(".pdf") || path.includes("/pdf/") || path.includes("/doi/pdf/") || path.includes("/stamp/stamp.jsp") || path.includes("/stamppdf/getpdf.jsp") || hostname === "d1bxh8uas1mnw7.cloudfront.net" || (hostname.endsWith("preprints.org") && path.includes("/download"));
  } catch {
    const lower = String(url || "").toLowerCase();
    return lower.includes(".pdf") || lower.includes("/pdf/") || lower.includes("/doi/pdf/") || lower.includes("/stamp/stamp.jsp") || lower.includes("/stamppdf/getpdf.jsp") || lower.includes("d1bxh8uas1mnw7.cloudfront.net") || (lower.includes("preprints.org") && lower.includes("/download"));
  }
}

async function notify(message) {
  try {
    await browser.notifications.create({
      type: "basic",
      iconUrl: browser.runtime.getURL("popup.html"),
      title: "学术论文检索助手",
      message
    });
  } catch {
    console.info(message);
  }
}
