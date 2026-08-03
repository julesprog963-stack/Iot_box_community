/* Capture publication screenshots using disposable Odoo demo data. */
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const baseUrl = process.env.ODOO_BASE_URL;
const database = process.env.ODOO_DATABASE;
const login = process.env.ODOO_LOGIN;
const password = process.env.ODOO_PASSWORD;
const outputDir = process.env.ODOO_SCREENSHOT_DIR;

if (![baseUrl, database, login, password, outputDir].every(Boolean)) {
    throw new Error("Missing required ODOO_* screenshot environment variables.");
}

const errors = [];
const actionIds = {};

async function xmlId(page, name) {
    if (actionIds[name]) return actionIds[name];
    const result = await page.evaluate(async (xmlName) => {
        const response = await fetch("/web/dataset/call_kw/ir.model.data/search_read", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: "ir.model.data",
                    method: "search_read",
                    args: [[
                        ["module", "=", "community_iot_box"],
                        ["name", "=", xmlName],
                    ]],
                    kwargs: { fields: ["res_id"], limit: 1 },
                },
                id: 1,
            }),
        });
        const payload = await response.json();
        return payload.result && payload.result[0] && payload.result[0].res_id;
    }, name);
    if (!result) throw new Error(`Could not resolve action ${name}.`);
    actionIds[name] = result;
    return result;
}

async function captureAction(page, name, fileName, selector) {
    const id = await xmlId(page, name);
    await page.goto(`${baseUrl}/web#action=${id}`, { waitUntil: "domcontentloaded" });
    await page.locator(selector).first().waitFor({ state: "visible", timeout: 15000 });
    const target = path.join(outputDir, fileName);
    await page.screenshot({ path: target, fullPage: true });
    console.log(`Captured ${target}`);
}

(async () => {
    fs.mkdirSync(outputDir, { recursive: true });
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 1 });
    page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
        if (message.type() === "error") errors.push(`console: ${message.text()}`);
    });
    page.on("response", (response) => {
        if (response.status() >= 400) errors.push(`http ${response.status()}: ${response.url()}`);
    });

    await page.goto(`${baseUrl}/web/login?db=${encodeURIComponent(database)}`, { waitUntil: "domcontentloaded" });
    await page.locator('input[name="login"]').fill(login);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/\/web/, { timeout: 15000 });

    await captureAction(page, "action_community_iot_dashboard", "main_screenshot.png", ".o_ciot_dashboard");
    await captureAction(page, "action_community_iot_boxes", "iot_boxes.png", ".o_community_iot_box_kanban");
    await page.getByText("Store Front", { exact: true }).first().click();
    await page.locator(".o_form_view").first().waitFor({ state: "visible", timeout: 15000 });
    const configurationTarget = path.join(outputDir, "iot_box_configuration.png");
    await page.screenshot({ path: configurationTarget, fullPage: true });
    console.log(`Captured ${configurationTarget}`);
    await captureAction(page, "action_community_iot_devices", "iot_devices.png", ".o_list_view, .o_view_controller");
    await captureAction(page, "action_community_iot_jobs", "iot_jobs.png", ".o_list_view, .o_view_controller");

    await browser.close();
    if (errors.length) throw new Error(errors.join("\n"));
})();
