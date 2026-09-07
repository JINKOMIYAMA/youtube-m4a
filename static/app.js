const $ = (id) => document.getElementById(id);
const urlInput = $("url");
const fetchBtn = $("fetchBtn");
const pasteBtn = $("pasteBtn");
const editor = $("editor");
const artwork = $("artwork");
const titleInput = $("title");
const artistInput = $("artist");
const downloadBtn = $("downloadBtn");
const statusBox = $("status");

function setStatus(message = "", type = "") {
  statusBox.textContent = message;
  statusBox.className = `status ${message ? "" : "hidden"} ${type}`.trim();
}

function setBusy(button, busy, busyText, normalText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : normalText;
}

async function readError(response) {
  try {
    const json = await response.json();
    return json.detail || "エラーが発生しました。";
  } catch {
    return "エラーが発生しました。";
  }
}

pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    urlInput.value = text.trim();
  } catch {
    urlInput.focus();
    setStatus("Safariの設定により自動貼り付けできません。入力欄を長押しして貼り付けてください。");
  }
});

fetchBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return setStatus("YouTube URLを入力してください。", "error");

  setBusy(fetchBtn, true, "取得中…", "動画情報を取得");
  setStatus("動画情報を取得しています…");
  editor.classList.add("hidden");

  try {
    const response = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) throw new Error(await readError(response));
    const data = await response.json();

    titleInput.value = data.title || "";
    artistInput.value = data.artist || "";
    artwork.src = data.thumbnail || "";
    editor.classList.remove("hidden");
    setStatus("取得完了。必要ならタイトルとアーティスト名を編集してください。", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(fetchBtn, false, "取得中…", "動画情報を取得");
  }
});

downloadBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  const title = titleInput.value.trim();
  const artist = artistInput.value.trim();
  if (!url || !title || !artist) return setStatus("URL・タイトル・アーティスト名を確認してください。", "error");

  setBusy(downloadBtn, true, "M4Aを作成中…", "M4Aを作成してダウンロード");
  setStatus("音声を取得してM4Aを作成しています。長い動画は少し時間がかかります…");

  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, artist }),
    });
    if (!response.ok) throw new Error(await readError(response));

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const utf8Match = disposition.match(/filename\*=utf-8''([^;]+)/i);
    const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
    let filename = `${title}.m4a`;
    if (utf8Match) filename = decodeURIComponent(utf8Match[1]);
    else if (plainMatch) filename = plainMatch[1];

    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    setStatus("M4Aの作成が完了しました。", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(downloadBtn, false, "M4Aを作成中…", "M4Aを作成してダウンロード");
  }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
