// Internal extension message routing
interface OffscreenMessage {
  source: "offscreen";
  type: string;
  data?: unknown;
  connected?: boolean;
}

interface SidePanelMessage {
  source: "sidepanel";
  payload: any;
}

interface ToOffscreenMessage {
  target: "offscreen";
  payload: any;
}

const OFFSCREEN_DOCUMENT_PATH = "offscreen.html";

// Create offscreen document if it doesn't exist
async function setupOffscreenDocument() {
  // @ts-ignore - chrome.offscreen might not be in types yet depending on version
  if (await chrome.offscreen.hasDocument()) {
    return;
  }

  // @ts-ignore
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_DOCUMENT_PATH,
    reasons: ["WEB_SOCKET"],
    justification: "WebSocket connection to Surfy server",
  });
  console.log("Offscreen document created");
}

// Handle extension icon click to open side panel
chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId) {
    // @ts-ignore
    chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

// Message routing
chrome.runtime.onMessage.addListener((msg: any, sender, sendResponse) => {
  // Messages from offscreen -> forward to Side Panel
  if (msg.source === "offscreen") {
    chrome.runtime.sendMessage({
      source: "background",
      ...msg
    });
    return;
  }

  // Messages from Side Panel -> forward to offscreen
  if (msg.source === "sidepanel") {
    chrome.runtime.sendMessage({
      target: "offscreen",
      payload: msg.payload
    } as ToOffscreenMessage);
    return;
  }
});

// Lifecycle events
chrome.runtime.onInstalled.addListener(() => {
  console.log("Surfy extension installed");
  setupOffscreenDocument();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("Surfy extension starting up");
  setupOffscreenDocument();
});
