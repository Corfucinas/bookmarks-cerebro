// content.js — lightweight content script for metadata extraction
// Injected declaratively on all URLs (manifest.json content_scripts)
// and programmatically via chrome.scripting.executeScript when needed.

chrome.runtime.onMessage.addListener((request, _sender, sendResponse,) => {
  if (request.action === "extractMetadata") {
    const descMeta = document.querySelector("meta[name=\"description\"]",);
    const ogDesc = document.querySelector("meta[property=\"og:description\"]",);
    const ogTitle = document.querySelector("meta[property=\"og:title\"]",);
    const selection = window.getSelection().toString();

    sendResponse({
      url: location.href,
      title: document.title,
      description: descMeta?.getAttribute("content",)
        || ogDesc?.getAttribute("content",)
        || "",
      selectedText: selection ? selection.slice(0, 1000,) : "",
      ogTitle: ogTitle?.getAttribute("content",) || "",
    },);
  }
  return true;
},);
