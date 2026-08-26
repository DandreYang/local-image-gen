import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function expectAccessible(page, state) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(result.violations, `${state}: ${JSON.stringify(result.violations, null, 2)}`).toEqual([]);
}

test("the production start surface passes WCAG A/AA automated checks", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Local Studio");
  await expect(page.getByRole("heading", { name: "描述你想看到的画面" })).toBeVisible();
  await expectAccessible(page, "start");
});

test("the fixture creation journey stays accessible through export", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "画面描述" }).fill("无障碍验收：深蓝背景上的青色圆形，无文字");
  await page.getByRole("button", { name: "开始生成" }).click();

  await expect(page.getByRole("dialog", { name: /将生成 2 张候选/ })).toBeVisible();
  await expect(page.getByText("确认前未调用外部文本或搜索模型")).toBeVisible();
  await expectAccessible(page, "confirm");

  await page.getByRole("button", { name: "确认并生成" }).click();
  await expect(page.getByRole("heading", { name: "挑一张继续打磨" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".candidate-card")).toHaveCount(2);
  await expect(page.getByText(/64x64 · 请求 2k/).first()).toBeVisible();
  await expectAccessible(page, "candidates");

  await page.getByRole("button", { name: "选择 01" }).click();
  await expect(page.getByRole("region", { name: "当前作品" })).toBeVisible();
  await expectAccessible(page, "refine");

  await page.getByRole("button", { name: "导出" }).click();
  await expect(page.getByRole("heading", { name: "定稿导出" })).toBeVisible();
  await expectAccessible(page, "export");

  await page.getByRole("button", { name: "素材库" }).click();
  await expect(page.getByRole("heading", { name: "素材库" })).toBeVisible();
  const firstLibraryImage = page.locator(".library-grid img").first();
  await expect(firstLibraryImage).toHaveAttribute("loading", "lazy");
  await expect(firstLibraryImage).toHaveAttribute("decoding", "async");
  await expect(firstLibraryImage).toHaveAttribute("src", /\/studio-api\/thumb\//);
  await expectAccessible(page, "library");
});

test("mobile and reduced-motion start surfaces remain usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    animationDurations: [...document.getAnimations()].map((animation) => animation.effect?.getTiming().duration),
  }));
  expect(metrics.scrollWidth).toBe(metrics.clientWidth);
  expect(metrics.animationDurations.filter((duration) => Number(duration) > 1_000)).toEqual([]);
  await expect(page.getByRole("button", { name: "开始生成" })).toBeVisible();
  await expectAccessible(page, "mobile-reduced-motion");
});

test("the desktop start flow reflows at a 200-percent-equivalent viewport", async ({ page }) => {
  // A 1440px desktop viewport at 200% browser zoom exposes roughly 720 CSS px.
  await page.setViewportSize({ width: 720, height: 900 });
  await page.goto("/");
  await page.getByRole("button", { name: /auto · 按模板 · 2k/ }).click();
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(metrics.scrollWidth).toBe(metrics.clientWidth);
  await expect(page.getByRole("button", { name: "开始生成" })).toBeVisible();
  await expect(page.getByRole("group", { name: "生成设置" })).toBeVisible();
  await expectAccessible(page, "desktop-200-percent-equivalent");
});

test("Path A survives a real Chromium PNG round-trip with zero outside mismatches", async ({ page }) => {
  const probeUrl = new URL("../../../../tests/path_a_probe.html", import.meta.url);
  await page.goto(probeUrl.href);
  await page.getByRole("button", { name: "运行自检" }).click();
  await expect(page.locator("#report")).toContainText("RGB 不同 0");

  const proof = await page.evaluate(async () => {
    const original = document.createElement("canvas");
    original.width = 96;
    original.height = 72;
    const originalContext = original.getContext("2d");
    originalContext.fillStyle = "#c45c26";
    originalContext.fillRect(0, 0, original.width, original.height);

    const regen = document.createElement("canvas");
    regen.width = original.width;
    regen.height = original.height;
    const regenContext = regen.getContext("2d");
    regenContext.fillStyle = "#1d4ed8";
    regenContext.fillRect(0, 0, regen.width, regen.height);

    const box = {
      x: pctToPixels(20, original.width),
      y: pctToPixels(20, original.height),
      w: pctToPixels(40, original.width),
      h: pctToPixels(40, original.height),
    };
    const pasted = pasteRegion({ base: original, regen, box });

    async function pngRoundTrip(canvas) {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      const signature = [...new Uint8Array(await blob.arrayBuffer()).slice(0, 8)];
      const url = URL.createObjectURL(blob);
      const image = new Image();
      image.src = url;
      await image.decode();
      URL.revokeObjectURL(url);
      return { image, signature };
    }

    const originalPng = await pngRoundTrip(original);
    const resultPng = await pngRoundTrip(pasted);
    const compared = countOutsideMismatches(originalPng.image, resultPng.image, box);
    return {
      ...compared,
      originalSignature: originalPng.signature,
      resultSignature: resultPng.signature,
    };
  });

  expect(proof.originalSignature).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  expect(proof.resultSignature).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  expect(proof.outside).toBeGreaterThan(0);
  expect(proof.mismatches).toBe(0);
});
