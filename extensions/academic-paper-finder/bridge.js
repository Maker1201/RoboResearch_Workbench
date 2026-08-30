// 工作台网页 ↔ 扩展 桥接：让工作台可以直接把“浏览器认证并抓取”任务交给扩展。
// 工作台页面 postMessage({ type: "RRW_START_CAPTURE", task })，
// 本脚本转发给后台，由后台打开出版商页面（用户完成 CARSI 登录后自动抓取 PDF）。
(() => {
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.type !== "RRW_START_CAPTURE" || !data.task || !data.task.item_key) return;
    browser.runtime
      .sendMessage({ type: "RRW_START_CAPTURE", task: data.task })
      .then((reply) => {
        window.postMessage({ type: "RRW_CAPTURE_ACK", accepted: Boolean(reply && reply.accepted), reason: reply?.reason || "" }, "*");
      })
      .catch(() => {
        window.postMessage({ type: "RRW_CAPTURE_ACK", accepted: false, reason: "extension-error" }, "*");
      });
  });
})();
