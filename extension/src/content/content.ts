const host = document.createElement("surfy-highlight");
const shadow = host.attachShadow({ mode: "closed" });

const style = document.createElement("style");
style.textContent = `
  :host {
    all: initial;
  }
  .surfy-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 999999;
    background: rgba(37, 99, 235, 0.9);
    color: white;
    padding: 8px 16px;
    font-family: system-ui, sans-serif;
    font-size: 14px;
    text-align: center;
    pointer-events: none;
    display: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }
  .surfy-banner.visible {
    display: block;
  }
`;

const banner = document.createElement("div");
banner.className = "surfy-banner";
shadow.appendChild(style);
shadow.appendChild(banner);

document.body.appendChild(host);

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "dom_highlight") {
    const { action_type, description } = message.data;

    if (action_type === "task_start") {
      banner.textContent = description || "Executing task...";
      banner.classList.add("visible");
    } else if (action_type === "task_end") {
      banner.classList.remove("visible");
    }
  }
});

console.log("Surfy content script initialized");
