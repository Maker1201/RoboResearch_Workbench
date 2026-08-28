let activeTask = null;
let captureBox = null;

browser.runtime.onMessage.addListener((message) => {
  if (message?.type !== "SCAN_FOR_PDF") return;
  activeTask = message.task;
  installCaptureBox(activeTask);
  const pdfUrl = findBestPdfUrl();
  if (pdfUrl) {
    browser.runtime.sendMessage({ type: "PDF_CANDIDATE_FOUND", task: activeTask, pdfUrl });
    return;
  }
  if (message.allowClick === false) return;
  const clickable = findPdfClickable();
  if (clickable) {
    browser.runtime.sendMessage({ type: "PDF_BUTTON_CLICKING", task: activeTask });
    clickable.click();
  }
});

function findBestPdfUrl() {
  const current = window.location.href;
  if (looksLikePdfUrl(current) || document.contentType === "application/pdf") {
    return current;
  }

  const metaPdf = metaPdfUrl();
  const anchors = [...document.querySelectorAll("a[href], a[data-href]")];
  const candidates = anchors
    .map((anchor) => ({ href: hrefFor(anchor), text: anchor.textContent || "", score: pdfScore(anchor) }))
    .filter((candidate) => candidate.href && looksLikePdfCandidate(candidate.href, candidate.text));
  if (metaPdf) candidates.push({ href: metaPdf, text: "citation_pdf_url", score: 120 });

  candidates.sort((a, b) => b.score - a.score);

  const direct = candidates.find((candidate) => looksLikePdfUrl(candidate.href));
  if (direct) return direct.href;

  const ieee = candidates.find((candidate) => candidate.href.includes("/stamp/stamp.jsp"));
  if (ieee) return ieee.href;

  return candidates[0]?.href || null;
}

function findPdfClickable() {
  const elements = [...document.querySelectorAll("a, button, [role='button'], [data-testid], [aria-label]")];
  return elements
    .map((element) => ({ element, text: element.textContent || element.getAttribute("aria-label") || "", score: pdfScore(element) }))
    .filter((candidate) => /\bpdf\b|full text|download/i.test(candidate.text) || candidate.score >= 20)
    .sort((a, b) => b.score - a.score)[0]?.element || null;
}

function hrefFor(element) {
  const raw = element.getAttribute?.("href") || element.getAttribute?.("data-href") || "";
  if (!raw) return "";
  return new URL(raw, location.href).href;
}

function metaPdfUrl() {
  const selectors = [
    'meta[name="citation_pdf_url"]',
    'meta[property="citation_pdf_url"]',
    'meta[name="dc.identifier"]',
  ];
  for (const selector of selectors) {
    const value = document.querySelector(selector)?.getAttribute("content");
    if (value && value.toLowerCase().includes("pdf")) return new URL(value, location.href).href;
  }
  return null;
}

function pdfScore(element) {
  const href = hrefFor(element);
  const text = `${href} ${element.textContent || ""} ${element.getAttribute?.("aria-label") || ""} ${element.getAttribute?.("data-testid") || ""} ${element.className || ""}`.toLowerCase();
  let score = 0;
  if (text.includes("/stamp/stamp.jsp")) score += 80;
  if (text.includes("pdf")) score += 40;
  if (text.includes("full text")) score += 20;
  if (text.includes("download")) score += 10;
  if (text.includes("download pdf")) score += 60;
  if (text.includes("researchsquare") && text.includes("pdf")) score += 50;
  if (text.includes("preprints.org") && text.includes("download")) score += 80;
  if (text.includes("d1bxh8uas1mnw7.cloudfront.net")) score += 80;
  if (text.includes("stats-pdf") || text.includes("documentpdf")) score += 20;
  return score;
}

function looksLikePdfCandidate(href, text) {
  const value = `${href} ${text}`.toLowerCase();
  return (
    value.includes("pdf") ||
    value.includes("full text") ||
    value.includes("download") ||
    href.includes("/stamp/stamp.jsp") ||
    href.includes("/doi/pdf/") ||
    href.includes("/pdf/") ||
    href.includes(".pdf") ||
    href.includes("d1bxh8uas1mnw7.cloudfront.net") ||
    href.includes("preprints.org") && value.includes("download") ||
    href.includes("/article/") && value.includes("download pdf")
  );
}

function looksLikePdfUrl(url) {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.toLowerCase();
    return path.endsWith(".pdf") || path.includes("/pdf/") || path.includes("/doi/pdf/") || path.includes("/stamp/stamp.jsp") || path.includes("/stamppdf/getpdf.jsp");
  } catch {
    const lower = String(url || "").toLowerCase();
    return lower.includes(".pdf") || lower.includes("/pdf/") || lower.includes("/doi/pdf/") || lower.includes("/stamp/stamp.jsp") || lower.includes("/stamppdf/getpdf.jsp");
  }
}

function installCaptureBox(task) {
  if (captureBox) return;
  captureBox = document.createElement("div");
  captureBox.style.cssText = [
    "position:fixed",
    "right:18px",
    "bottom:18px",
    "z-index:2147483647",
    "background:#126c71",
    "color:#fff",
    "font:14px system-ui,sans-serif",
    "padding:10px 12px",
    "border-radius:6px",
    "box-shadow:0 8px 24px rgba(0,0,0,.22)",
    "max-width:320px"
  ].join(";");
  captureBox.innerHTML = `
    <div style="font-weight:700;margin-bottom:6px">论文检索助手</div>
    <div style="line-height:1.4;margin-bottom:8px">完成 CARSI 登录后，我会自动捕获 PDF。若当前页已是 PDF，请点保存。</div>
    <button id="apf-save-current-pdf" style="border:0;border-radius:4px;background:#fff;color:#126c71;padding:6px 9px;cursor:pointer">保存当前 PDF 到 Zotero</button>
  `;
  document.documentElement.appendChild(captureBox);
  document.getElementById("apf-save-current-pdf")?.addEventListener("click", () => {
    const pdfUrl = findBestPdfUrl() || window.location.href;
    browser.runtime.sendMessage({ type: "PDF_CANDIDATE_FOUND", task, pdfUrl });
  });
}
