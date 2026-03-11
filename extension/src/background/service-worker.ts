console.log("service worker ready");

chrome.runtime.onInstalled.addListener(() => {
  console.log("Surfy extension installed");
});
