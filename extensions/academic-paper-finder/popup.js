document.getElementById("openApp").addEventListener("click", async () => {
  const url = browser.runtime.getURL("app.html");
  await browser.tabs.create({ url });
  window.close();
});
