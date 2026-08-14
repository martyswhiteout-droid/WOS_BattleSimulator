const VALUE_RE = /^(?:[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?%|[+-](?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?|(?:\d{1,3}(?:,\d{3})*|\d+))$/;
const VALUE_CHARS_RE = /^[0123456789.,%+\-\s]+$/;
const WHITELIST = "0123456789.,%+-";
const IS_NODE = typeof process !== "undefined" && Boolean(process.versions?.node);

let workerPromise;

function moduleUrl(relative) {
  return new URL(relative, import.meta.url);
}

async function localPath(relative) {
  const { fileURLToPath } = await import("node:url");
  return fileURLToPath(moduleUrl(relative));
}

async function createLocalWorker() {
  const imported = IS_NODE
    ? await import("./vendor/node_modules/tesseract.js/src/index.js")
    : await import("./vendor/node_modules/tesseract.js/dist/tesseract.esm.min.js");
  const Tesseract = imported.default;
  const options = { cacheMethod: "none" };
  if (IS_NODE) {
    options.langPath = await localPath(
      "./vendor/node_modules/@tesseract.js-data/eng/4.0.0_best_int",
    );
    options.corePath = await localPath(
      "./vendor/node_modules/tesseract.js-core/tesseract-core-lstm.js",
    );
  } else {
    options.workerPath = moduleUrl(
      "./vendor/node_modules/tesseract.js/dist/worker.min.js",
    ).href;
    options.langPath = moduleUrl(
      "./vendor/node_modules/@tesseract.js-data/eng/4.0.0_best_int",
    ).href;
    options.corePath = moduleUrl(
      "./vendor/node_modules/tesseract.js-core/tesseract-core-lstm.js",
    ).href;
  }
  return Tesseract.createWorker("eng", Tesseract.OEM.LSTM_ONLY, options);
}

function getWorker() {
  workerPromise ??= createLocalWorker();
  return workerPromise;
}

function parseTsv(tsv) {
  const words = [];
  let width = 0;
  let height = 0;
  for (const line of String(tsv || "").split("\n")) {
    const columns = line.split("\t");
    if (columns.length < 12) continue;
    const level = Number(columns[0]);
    const left = Number(columns[6]);
    const top = Number(columns[7]);
    const boxWidth = Number(columns[8]);
    const boxHeight = Number(columns[9]);
    if (level === 1) {
      width = boxWidth;
      height = boxHeight;
      continue;
    }
    if (level !== 5) continue;
    const text = columns.slice(11).join("\t").trim();
    const confidence = Number(columns[10]);
    if (!text || !Number.isFinite(confidence) || confidence < 0) continue;
    if (boxWidth <= 0 || boxHeight <= 0) continue;
    words.push({
      text,
      conf: Math.max(0, Math.min(1, confidence / 100)),
      box: { x0: left, y0: top, x1: left + boxWidth, y1: top + boxHeight },
    });
  }
  if (!(width > 0 && height > 0)) {
    throw new Error("Tesseract returned no page dimensions");
  }
  return { words, width, height };
}

function looksLikeValue(text) {
  const clean = text.trim();
  return /\d/.test(clean) && VALUE_CHARS_RE.test(clean);
}

function isValue(text) {
  return VALUE_RE.test(text.trim());
}

function overlapRatio(left, right) {
  const width = Math.max(0, Math.min(left.x1, right.x1) - Math.max(left.x0, right.x0));
  const height = Math.max(0, Math.min(left.y1, right.y1) - Math.max(left.y0, right.y0));
  const intersection = width * height;
  const leftArea = (left.x1 - left.x0) * (left.y1 - left.y0);
  const rightArea = (right.x1 - right.x0) * (right.y1 - right.y0);
  return intersection / Math.min(leftArea, rightArea);
}

function mergePasses(fullWords, digitWords) {
  const regions = fullWords.filter((word) => looksLikeValue(word.text));
  const values = [];
  for (const word of digitWords) {
    if (!isValue(word.text)) continue;
    const duplicate = values.find((value) => overlapRatio(value.box, word.box) >= 0.5);
    if (!duplicate) {
      values.push(word);
    } else if (word.conf > duplicate.conf) {
      Object.assign(duplicate, word);
    }
  }
  for (const word of regions) {
    if (!isValue(word.text)) continue;
    const duplicate = values.find((value) => overlapRatio(value.box, word.box) >= 0.5);
    if (!duplicate) {
      values.push(word);
    } else if (word.conf > duplicate.conf) {
      Object.assign(duplicate, word);
    }
  }
  const labels = fullWords.filter((word) => !looksLikeValue(word.text));
  return [...labels, ...values].sort(
    (left, right) => left.box.y0 - right.box.y0 || left.box.x0 - right.box.x0,
  );
}

async function readPixels(imageBytes) {
  if (IS_NODE) {
    const { PNG } = await import("./vendor/node_modules/pngjs/lib/png.js");
    const png = PNG.sync.read(Buffer.from(imageBytes));
    return { width: png.width, height: png.height, data: png.data };
  }
  const blob = new Blob([imageBytes]);
  const bitmap = await createImageBitmap(blob);
  const canvas = typeof OffscreenCanvas !== "undefined"
    ? new OffscreenCanvas(bitmap.width, bitmap.height)
    : Object.assign(document.createElement("canvas"), {
      width: bitmap.width,
      height: bitmap.height,
    });
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0);
  const data = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
  bitmap.close();
  return { width: canvas.width, height: canvas.height, data };
}

function dataUrlBytes(dataUrl) {
  const encoded = dataUrl.slice(dataUrl.indexOf(",") + 1);
  if (IS_NODE) return Buffer.from(encoded, "base64");
  const binary = atob(encoded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function colorCounts(pixels) {
  let green = 0;
  let red = 0;
  for (let offset = 0; offset < pixels.data.length; offset += 4) {
    const rValue = pixels.data[offset];
    const gValue = pixels.data[offset + 1];
    if (gValue > rValue + 40) green += 1;
    else if (rValue > gValue + 40) red += 1;
  }
  return { green, red };
}

async function digitSource(imageBytes, pixels, coloredPanel) {
  if (!coloredPanel) return imageBytes;
  const data = new Uint8Array(pixels.data);
  for (let offset = 0; offset < data.length; offset += 4) {
    const rValue = data[offset];
    const gValue = data[offset + 1];
    const colored = gValue > rValue + 40 || rValue > gValue + 40;
    const value = colored ? 0 : 255;
    data[offset] = value;
    data[offset + 1] = value;
    data[offset + 2] = value;
    data[offset + 3] = 255;
  }
  if (IS_NODE) {
    const { PNG } = await import("./vendor/node_modules/pngjs/lib/png.js");
    return PNG.sync.write({ width: pixels.width, height: pixels.height, data });
  }
  const canvas = typeof OffscreenCanvas !== "undefined"
    ? new OffscreenCanvas(pixels.width, pixels.height)
    : Object.assign(document.createElement("canvas"), {
      width: pixels.width,
      height: pixels.height,
    });
  const context = canvas.getContext("2d");
  context.putImageData(new ImageData(new Uint8ClampedArray(data), pixels.width, pixels.height), 0, 0);
  if (typeof canvas.convertToBlob === "function") {
    const blob = await canvas.convertToBlob({ type: "image/png" });
    return new Uint8Array(await blob.arrayBuffer());
  }
  return canvas.toDataURL("image/png");
}

function valueColor(pixels, box, text) {
  if (!isValue(text)) return null;
  const left = Math.max(0, Math.floor(box.x0));
  const top = Math.max(0, Math.floor(box.y0));
  const right = Math.min(pixels.width, Math.ceil(box.x1));
  const bottom = Math.min(pixels.height, Math.ceil(box.y1));
  let green = 0;
  let red = 0;
  for (let y = top; y < bottom; y += 1) {
    for (let x = left; x < right; x += 1) {
      const offset = (y * pixels.width + x) * 4;
      const rValue = pixels.data[offset];
      const gValue = pixels.data[offset + 1];
      if (gValue > rValue + 40) green += 1;
      else if (rValue > gValue + 40) red += 1;
    }
  }
  if (green === 0 && red === 0) return null;
  return green > red ? "green" : "red";
}

function centeredPanelLabels(words, width) {
  const panelWord = /^(?:Infantry|Lancer|Marksman|Attack|Defense|Lethality|Health|Defender|Troops)$/i;
  return words.some((word) => {
    const centre = (word.box.x0 + word.box.x1) / (2 * width);
    return panelWord.test(word.text) && centre > 0.35 && centre < 0.65;
  });
}

export async function recognizeImage(imageBytes) {
  if (!(imageBytes instanceof Uint8Array) && !(imageBytes instanceof ArrayBuffer)) {
    throw new TypeError("imageBytes must be an ArrayBuffer or Uint8Array");
  }
  const bytes = imageBytes instanceof Uint8Array
    ? imageBytes
    : new Uint8Array(imageBytes);
  const worker = await getWorker();
  const full = await worker.recognize(bytes, {}, { tsv: true, imageColor: true });
  const fullPage = parseTsv(full.data.tsv);
  const normalizedBytes = dataUrlBytes(full.data.imageColor);
  const pixels = await readPixels(normalizedBytes);
  const counts = colorCounts(pixels);
  const leftValue = fullPage.words.some((word) => (
    isValue(word.text)
    && (word.box.x0 + word.box.x1) / (2 * fullPage.width) < 0.45
  ));
  const coloredPanel = counts.green > 64 && counts.red > 64
    && leftValue && centeredPanelLabels(fullPage.words, fullPage.width);
  const valuesImage = await digitSource(normalizedBytes, pixels, coloredPanel);
  const digits = await worker.recognize(
    valuesImage,
    { tessedit_char_whitelist: WHITELIST },
    { tsv: true },
  );
  const digitPage = parseTsv(digits.data.tsv);
  const words = mergePasses(fullPage.words, digitPage.words)
    .filter((word) => word.conf >= 0.5);
  return words.map((word) => ({
    text: word.text,
    x0: Math.max(0, Math.min(1, word.box.x0 / fullPage.width)),
    y0: Math.max(0, Math.min(1, word.box.y0 / fullPage.height)),
    x1: Math.max(0, Math.min(1, word.box.x1 / fullPage.width)),
    y1: Math.max(0, Math.min(1, word.box.y1 / fullPage.height)),
    conf: word.conf,
    color: coloredPanel ? valueColor(pixels, word.box, word.text) : null,
  }));
}

export async function terminateEngine() {
  if (!workerPromise) return;
  const worker = await workerPromise;
  workerPromise = undefined;
  await worker.terminate();
}
